import pandas as pd
import numpy as np
import os
import sys
from datetime import date, timedelta
from sqlalchemy import text, create_engine # Necesario para la conexión de DB

# Brújula para imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from config.db import get_db_engine

# --- 1. MÓDULO DE SOPORTE A DECISIONES (Paridad y CIF) ---

# NOTA: En un proyecto real, los COSTOS y AJUSTES se cargarían desde una tabla de 'Configuración' en la DB. 
# Aquí los definimos como constantes para replicar la lógica de los scripts originales.

# Constantes de Costos y Factores (Extraídas de calculadora_paridad.py y cif_santiago.py)
AJUSTE_CONTRATO_5 = 40.0 # Ajuste fijo para el Contrato #5 (USD/TN)
TASA_IVA_ARG = 1.21      # Constante para el IVA en Argentina
COSTO_COMEX_USD_TN = 55.0 # Costo de exportación desde Argentina (asumido si no se lee de DB)
COSTO_CIF_SANTIAGO_USD_TN = 60.0 # Costo CIF para Chile (asumido si no se lee de DB)
KG_POR_BOLSA = 50.0
TN_POR_BOLSA = 0.05 # 50kg / 1000kg

def get_latest_market_data(engine):
    """Obtiene los últimos precios y tipos de cambio necesarios para la paridad."""
    query = """
    SELECT date, sugar_5, fx_ars_usd, fx_brl_usd, fx_dxy
    FROM market_metrics
    ORDER BY date DESC
    LIMIT 1
    """
    df = pd.read_sql(query, engine)
    if df.empty:
        raise ValueError("No se encontraron datos de mercado en market_metrics.")
    return df.iloc[0].to_dict()

def calcular_precio_paridad_exportacion(engine):
    """
    Calcula el Precio de Paridad de Exportación en ARS por bolsa de 50kg.
    (Replica calculadora_paridad.py)
    """
    data = get_latest_market_data(engine)
    
    precio_contrato_5 = data.get('sugar_5', 0)
    tipo_cambio_ars = data.get('fx_ars_usd', 1.0)
    costo_exportacion = COSTO_COMEX_USD_TN
    
    # Lógica de Cálculo (USD/TN)
    precio_contrato_ajustado = precio_contrato_5 - AJUSTE_CONTRATO_5
    precio_paridad_usd_tn = precio_contrato_ajustado - costo_exportacion
    
    # Conversión a ARS/50kg
    precio_paridad_ars_50kg = (precio_paridad_usd_tn * tipo_cambio_ars * TN_POR_BOLSA)
    
    return {
        'precio_paridad_ars_50kg': precio_paridad_ars_50kg,
        'precio_paridad_usd_tn': precio_paridad_usd_tn
    }

def calcular_precio_cif_santiago(engine):
    """
    Calcula el Precio CIF Santiago en la moneda local (CLP) por tonelada.
    (Replica cif_santiago.py - ASUMIENDO USD/CLP disponible si es necesario)
    """
    data = get_latest_market_data(engine)
    precio_contrato_5 = data.get('sugar_5', 0)
    
    # Nota: Como USD/CLP no está en market_metrics, usamos un valor de respaldo
    # DEBERÍAS AÑADIR USD/CLP a market_metrics para que este cálculo sea exacto
    TIPO_CAMBIO_USD_CLP = 950.0 
    costo_cif = COSTO_CIF_SANTIAGO_USD_TN
    
    # Lógica de Cálculo (USD/TN)
    precio_contrato_ajustado = precio_contrato_5 - AJUSTE_CONTRATO_5
    precio_neto_usd_tn = precio_contrato_ajustado + costo_cif
    
    # Conversión a CLP/TN
    precio_cif_clp_tn = precio_neto_usd_tn * TIPO_CAMBIO_USD_CLP
    
    return {
        'precio_cif_clp_tn': precio_cif_clp_tn,
        'precio_neto_usd_tn': precio_neto_usd_tn
    }

def comparar_mercados(engine, precio_interno_ars_50kg_con_iva):
    """
    Compara la rentabilidad local vs. exportación. (Replica comparador_mercados.py)
    """
    paridad_results = calcular_precio_paridad_exportacion(engine)
    precio_paridad_neto = paridad_results['precio_paridad_ars_50kg']
    
    precio_interno_neto = precio_interno_ars_50kg_con_iva / TASA_IVA_ARG
    diferencia = precio_paridad_neto - precio_interno_neto
    
    recomendacion = "EXPORTAR" if diferencia > 0 else "MERCADO INTERNO"
    
    return {
        'precio_interno_neto': precio_interno_neto,
        'precio_paridad_neto': precio_paridad_neto,
        'diferencial_ars_50kg': diferencia,
        'recomendacion': recomendacion
    }

# --- 2. MÓDULO DEL MOTOR PRD DIARIO (motor_prd_diario.py) ---

# Este módulo es muy complejo y requiere:
# a) Conexión a la DB para leer el Plan Estratégico.
# b) Conexión a la DB para leer el Historial de Operaciones (Consumo/Producción REAL).
# c) Carga de un modelo SARIMAX de CONSUMO (que replicaremos en training.py y guardaremos en DB).

def calcular_prd_diario(fecha_analisis: date, K_MIN: float, K_MAX: float, UMBRAL_DESVIACION: float, PENDIENTE_SIGMOIDE: float):
    """
    Calcula el Precio de Referencia Dinámico (PRD) basado en la desviación de stock.
    (Replica motor_prd_diario.py - Requiere datos de simulación/reales en la DB)
    """
    engine = get_db_engine()
    hoy = fecha_analisis
    
    # --- A. Cargar Datos Necesarios (Simulación/Reales) ---
    try:
        # 1. Obtener el Stock Esperado y Stock Estratégico (del Plan Diario - DEBE ESTAR EN LA DB)
        # ASUMIMOS que los planes están en tablas prd_plan_diario y prd_plan_mensual
        query_plan_diario = f"SELECT * FROM prd_plan_diario WHERE date = '{hoy.strftime('%Y-%m-%d')}'"
        plan_diario = pd.read_sql(query_plan_diario, engine).iloc[0]
        
        # 2. Obtener el Stock REAL de hoy (Requiere tabla de Historial/Balance REAL)
        query_balance_real = f"""
        SELECT 
            SUM(produccion_real_diaria) as prod_acc, 
            SUM(consumo_real_diaria) as cons_acc,
            stock_inicial_mes 
        FROM balance_historial_real
        WHERE date <= '{hoy.strftime('%Y-%m-%d')}' AND EXTRACT(MONTH FROM date) = {hoy.month}
        """
        # Esta consulta es muy simplificada y ASUME la tabla 'balance_historial_real' y 'stock_inicial_mes'
        balance_real = pd.read_sql(query_balance_real, engine).iloc[0]
        
        stock_real_hoy = balance_real['stock_inicial_mes'] + balance_real['prod_acc'] - balance_real['cons_acc']
        stock_esperado_hoy = plan_diario['stock_diario_objetivo']
        stock_estrategico = plan_diario['stock_estrategico_mensual']
        
        # 3. Obtener Precio Base (Asumimos que viene de market_metrics/último cierre)
        precio_base = get_latest_market_data(engine).get('sugar_5', 1000) # Usamos Contrato #5 como base, luego lo convertimos/ajustamos a precio interno.

    except Exception as e:
        print(f"ERROR PRD: Fallo al cargar datos necesarios. {e}")
        return None # Retorno seguro en caso de fallo

    # --- B. Lógica de Desviación y K Dinámico ---
    
    if stock_estrategico == 0:
        delta_s_diario = 0.0
    else:
        # Desviación (ΔS_Diario)
        delta_s_diario = (stock_real_hoy - stock_esperado_hoy) / stock_estrategico

    # Aquí iría la llamada a calcular_desviacion_proyectada() que usa el modelo SARIMAX de CONSUMO.
    # Por ahora, la omitimos para no complicar hasta tener el modelo SARIMAX guardado.
    delta_s_proyectado = 0.0 # Placeholder
    
    delta_s_combinado = (0.6 * delta_s_diario) + (0.4 * delta_s_proyectado) # Peso 60/40

    # K Dinámico (Usando la sigmoide para ajustar la sensibilidad)
    abs_delta_s = abs(delta_s_combinado)
    x = PENDIENTE_SIGMOIDE * (abs_delta_s - UMBRAL_DESVIACION)
    sigmoid_val = 1 / (1 + np.exp(-x))
    K_dinamico = K_MIN + (K_MAX - K_MIN) * sigmoid_val

    # --- C. Cálculo Final del PRD ---
    # La fórmula clave de ajuste de precios: P_final = P_base * (1 - K * ΔS_combinado)
    prd_tn = precio_base * (1 - K_dinamico * delta_s_combinado)
    
    return {
        'prd_tn': prd_tn,
        'k_dinamico': K_dinamico,
        'delta_s_combinado': delta_s_combinado,
        'stock_real_hoy': stock_real_hoy
    }

if __name__ == '__main__':
    engine = get_db_engine()
    
    # 1. Ejemplo de Cálculo de Paridad
    print("--- Prueba de Paridad de Exportación ---")
    paridad = calcular_precio_paridad_exportacion(engine)
    print(f"Precio de Paridad (ARS/50kg): {paridad['precio_paridad_ars_50kg']:,.2f}")
    
    # 2. Ejemplo de Comparador de Mercados (Necesita un precio interno simulado)
    precio_interno_simulado_con_iva = 15000.00 # ARS/50kg
    print(f"\n--- Comparación de Mercados ---")
    comparacion = comparar_mercados(engine, precio_interno_simulado_con_iva)
    print(f"Recomendación: {comparacion['recomendacion']} | Diferencial: {comparacion['diferencial_ars_50kg']:,.2f}")
    
    # 3. Ejemplo de PRD (Requiere que existan las tablas prd_plan_diario/mensual)
    # print(f"\n--- Cálculo de PRD para hoy ---")
    # prd_results = calcular_prd_diario(
    #     date.today(), K_MIN=0.2, K_MAX=0.8, UMBRAL_DESVIACION=0.05, PENDIENTE_SIGMOIDE=50
    # )
    # if prd_results:
    #     print(f"PRD (USD/TN): {prd_results['prd_tn']:,.2f}")