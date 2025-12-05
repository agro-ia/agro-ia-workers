import pandas as pd
import numpy as np
import os
import sys
import pickle
import math
from datetime import date, timedelta
from sqlalchemy import text
import copy 
import logging

# Configuración de Logging para un output más limpio
logging.getLogger('pandas.io.sql').setLevel(logging.ERROR) 

# Brújula para imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from config.db import get_db_engine

# --- 0. CONFIGURACIÓN Y CONSTANTES ---
MODELOS_DIR = os.path.join(project_root, 'modelos')
CHAMPION_MODEL_CONSUMO_PATH = os.path.join(MODELOS_DIR, 'modelo_consumo_sarima.pkl')

# Constantes de Costos y Factores 
AJUSTE_CONTRATO_5 = 40.0 
TASA_IVA_ARG = 1.21      
COSTO_COMEX_USD_TN = 55.0 
COSTO_CIF_SANTIAGO_USD_TN = 60.0 
TN_POR_BOLSA = 0.05 

# Parámetros Óptimos para el PRD 
BEST_PRD_PARAMS = {
    'K_MIN': 0.15, 
    'K_MAX': 0.5, 
    'UMBRAL_DESVIACION': 0.14, 
    'PENDIENTE_SIGMOIDE': 10
}

# --- 1. MÓDULO DE SOPORTE A DECISIONES (Paridad y Comparador) ---

def get_latest_market_data(engine):
    """Obtiene los últimos precios y tipos de cambio necesarios para la paridad."""
    query = """
    SELECT date, sugar_5, fx_ars_usd
    FROM market_metrics
    ORDER BY date DESC
    LIMIT 1
    """
    df = pd.read_sql(query, engine)
    if df.empty:
        # Esto solo debería ocurrir si el fetcher falló.
        return {'sugar_5': 20.0, 'fx_ars_usd': 900.0} 
    return df.iloc[0].to_dict()

def calcular_precio_paridad_exportacion(engine):
    """Calcula el Precio de Paridad de Exportación en ARS por bolsa de 50kg."""
    data = get_latest_market_data(engine)
    
    precio_contrato_5 = data.get('sugar_5', 0)
    tipo_cambio_ars = data.get('fx_ars_usd', 1.0)
    costo_exportacion = COSTO_COMEX_USD_TN
    
    precio_paridad_usd_tn = (precio_contrato_5 - AJUSTE_CONTRATO_5) - costo_exportacion
    precio_paridad_ars_50kg = (precio_paridad_usd_tn * tipo_cambio_ars * TN_POR_BOLSA)
    
    return {
        'precio_paridad_ars_50kg': precio_paridad_ars_50kg,
        'precio_paridad_usd_tn': precio_paridad_usd_tn
    }

def comparar_mercados(engine, precio_interno_ars_50kg_con_iva):
    """Compara la rentabilidad local vs. exportación."""
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

# --- 2. LÓGICA DE PROYECCIÓN SARIMAX PARA EL PRD ---

def load_sarimax_model():
    """Carga el modelo SARIMAX de consumo entrenado desde disco."""
    try:
        with open(CHAMPION_MODEL_CONSUMO_PATH, 'rb') as pfile:
            model_data = pickle.load(pfile)
            # Retorna el modelo y la fecha de entrenamiento para evitar fallos
            return model_data
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"   ❌ ERROR PRD: Fallo al cargar el modelo SARIMAX: {e}")
        return None

def project_consumption_sarimax(engine, hoy: date, n_days=7):
    """Genera un pronóstico de consumo diario para los próximos N días usando el modelo SARIMAX."""
    model_data = load_sarimax_model()
    if model_data is None: return None
    
    modelo_sarima_consumo = model_data['model']
    
    # 1. Preparar fechas y obtener Feature Exógena (Estacionalidad)
    forecast_start_date = pd.Timestamp(hoy) + timedelta(days=1)
    forecast_dates = pd.date_range(start=forecast_start_date, periods=n_days, freq='D')
    
    query_seasonality = "SELECT date, sugar_5_seasonality FROM seasonality_features ORDER BY date ASC"
    df_seasonality = pd.read_sql(query_seasonality, engine)
    df_seasonality['date'] = pd.to_datetime(df_seasonality['date'])
    df_seasonality.set_index('date', inplace=True)
    
    # Proyectar la estacionalidad del año anterior para el futuro
    past_dates = [d - pd.DateOffset(years=1) for d in forecast_dates]
    X_forecast = df_seasonality.reindex(past_dates).ffill().bfill()
    X_forecast.index = forecast_dates 
    
    # 3. Pronosticar 
    try:
        forecast_result = modelo_sarima_consumo.predict(
            n_periods=n_days,
            X=X_forecast
        )
        forecast_result = forecast_result.apply(lambda x: max(0, x))
        
        return pd.Series(forecast_result.values, index=forecast_dates, name='consumo_pronosticado')
        
    except Exception as e:
        print(f"   ❌ ERROR PRD: Fallo en la proyección SARIMAX: {e}")
        return None


# --- 3. MOTOR PRD DIARIO (motor_prd_diario.py) ---

def calcular_prd_diario(fecha_analisis: date):
    """Calcula el Precio de Referencia Dinámico (PRD) para una fecha específica."""
    engine = get_db_engine()
    hoy = fecha_analisis
    params = BEST_PRD_PARAMS 

    # --- A. Cargar Datos Necesarios (Balance y Precio Base) ---
    try:
        # 1. Stock Real Acumulado y Stock Inicial del Mes
        query_balance_acc = f"""
        SELECT 
            SUM(produccion_real_diaria) AS prod_acc, 
            SUM(consumo_real_diaria) AS cons_acc,
            MAX(stock_inicial_mes) AS stock_inicial 
        FROM balance_historial_real
        WHERE date <= '{hoy.strftime('%Y-%m-%d')}' AND EXTRACT(MONTH FROM date) = {hoy.month}
        """
        balance_acc = pd.read_sql(query_balance_acc, engine).iloc[0]
        
        if balance_acc.isnull().any():
             raise ValueError("Datos de balance real incompletos o tabla vacía para la fecha.")
             
        stock_inicial_anual = balance_acc['stock_inicial'] 
        stock_real_hoy = stock_inicial_anual + balance_acc['prod_acc'] - balance_acc['cons_acc']

        # 2. Stock Esperado y Estratégico (Del Plan Diario)
        query_plan_diario = f"SELECT * FROM prd_plan_diario WHERE date = '{hoy.strftime('%Y-%m-%d')}'"
        plan_diario = pd.read_sql(query_plan_diario, engine)
        
        if plan_diario.empty:
            raise ValueError(f"No se encontró plan estratégico diario para {hoy.strftime('%Y-%m-%d')}.")
        
        plan_diario = plan_diario.iloc[0]
        stock_esperado_hoy = plan_diario['stock_diario_objetivo']
        stock_estrategico = plan_diario['stock_estrategico_mensual']

        # 3. Precio Base
        precio_base_tn = get_latest_market_data(engine).get('sugar_5', 1000)

    except Exception as e:
        print(f"   ❌ ERROR PRD (Carga de Datos): {e}")
        return None

    # --- B. Cálculo de Desviación Diaria y Proyectada ---
    
    delta_s_diario = (stock_real_hoy - stock_esperado_hoy) / stock_estrategico if stock_estrategico else 0.0

    consumo_pronosticado_7d = project_consumption_sarimax(engine, hoy, n_days=7)

    if consumo_pronosticado_7d is None:
        delta_s_proyectado = 0.0
        print("   ⚠️ PRD calculado sin proyección de consumo futuro (SARIMAX no disponible).")
    else:
        # Simular stock para los próximos 7 días (usando el plan de producción)
        stock_proyectado = stock_real_hoy
        for i, consumo_pron in enumerate(consumo_pronosticado_7d):
            fecha_futura = pd.Timestamp(hoy) + timedelta(days=i + 1)
            
            # Obtener el objetivo de producción del plan para la fecha futura
            query_prod = f"SELECT produccion_diaria_objetivo FROM prd_plan_diario WHERE date = '{fecha_futura.strftime('%Y-%m-%d')}'"
            df_prod = pd.read_sql(query_prod, engine)
            
            prod_objetivo = df_prod.iloc[0]['produccion_diaria_objetivo'] if not df_prod.empty else 0.0
            stock_proyectado += prod_objetivo - consumo_pron
        
        # Obtener el stock objetivo para dentro de 7 días
        fecha_objetivo_7d = (pd.Timestamp(hoy) + timedelta(days=7)).strftime('%Y-%m-%d')
        query_obj = f"SELECT stock_diario_objetivo FROM prd_plan_diario WHERE date = '{fecha_objetivo_7d}'"
        df_obj = pd.read_sql(query_obj, engine)

        stock_objetivo_7d = df_obj.iloc[0]['stock_diario_objetivo'] if not df_obj.empty else stock_esperado_hoy
        
        # Calcular la desviación proyectada
        delta_s_proyectado = (stock_proyectado - stock_objetivo_7d) / stock_estrategico if stock_estrategico else 0.0

    # --- D. Cálculo del PRD Final ---
    delta_s_combinado = (0.6 * delta_s_diario) + (0.4 * delta_s_proyectado)
    
    K_dinamico = params['K_MIN'] + (params['K_MAX'] - params['K_MIN']) * (1 / (1 + math.exp(-params['PENDIENTE_SIGMOIDE'] * (abs(delta_s_combinado) - params['UMBRAL_DESVIACION']))))
    
    prd_tn = precio_base_tn * (1 - K_dinamico * delta_s_combinado)
    
    analisis_texto = "El PRD subió para moderar la demanda." if delta_s_combinado < 0 else "El PRD bajó para incentivar la demanda."
    
    return {
        'prd_tn': prd_tn,
        'k_dinamico': K_dinamico,
        'delta_s_combinado': delta_s_combinado,
        'stock_real_hoy': stock_real_hoy,
        'analisis_texto': analisis_texto
    }

# --- 4. FUNCIÓN DE ORQUESTACIÓN DEL WORKER (Punto de entrada para main.py) ---

def run_pricing_and_decision(fecha_analisis: date = date.today()):
    """Orquesta la ejecución de la paridad y el PRD (Paso [5/5])."""
    print("\n--- [5/5] CÁLCULO DE PRECIOS Y DECISIONES ---")
    engine = get_db_engine()
    
    # Usaremos la fecha del último dato sembrado para la simulación
    query_last_date = "SELECT MAX(date) AS max_date FROM balance_historial_real"
    last_date_df = pd.read_sql(query_last_date, engine)
    
    # Asume la fecha del último dato sembrado (2025-12-31 en la simulación)
    if last_date_df['max_date'].isnull().iloc[0]:
         print("   ❌ ERROR: La tabla balance_historial_real está vacía. No se puede calcular PRD.")
         return None
         
    fecha_analisis_final = last_date_df.iloc[0]['max_date']
    
    print(f"   Analizando fecha: {fecha_analisis_final.strftime('%Y-%m-%d')}")
    
    # 1. Calcular PRD 
    prd_results = calcular_prd_diario(fecha_analisis_final)

    if prd_results:
        print("\n--- INFORME PRD TÁCTICO ---")
        print(f"  PRD (USD/TN): ${prd_results['prd_tn']:,.2f}")
        print(f"  ΔS Combinado: {prd_results['delta_s_combinado']:.2%}")
        print(f"  Análisis: {prd_results['analisis_texto']}")
        
    # 2. Comparación de Mercados 
    PRECIO_INTERNO_ACTUAL_CON_IVA = 15000.00 # ARS/50kg CON IVA (Simulado)
    
    comparacion = comparar_mercados(engine, PRECIO_INTERNO_ACTUAL_CON_IVA)
    
    print("\n--- RECOMENDACIÓN ESTRATÉGICA ---")
    print(f"  Paridad de Exportación (ARS/50kg Neto): ${comparacion['precio_paridad_neto']:,.2f}")
    print(f"  Precio Interno Neto (ARS/50kg): ${comparacion['precio_interno_neto']:,.2f}")
    print(f"  Decisión: {comparacion['recomendacion']} | Diferencial: ${comparacion['diferencial_ars_50kg']:,.2f} ARS/50kg")
    
    return prd_results, comparacion

if __name__ == '__main__':
    # Para probar el PRD en una fecha de tu histórico simulado (ej. 2025-06-15)
    run_pricing_and_decision(date(2025, 6, 15))