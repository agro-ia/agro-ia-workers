import pandas as pd
import numpy as np
import os
import sys
from datetime import date, timedelta
from sqlalchemy import text

# --- 0. Configuración de Rutas y DB ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from config.db import get_db_engine

# --- Parámetros y Constantes de Simulación ---
DATA_DIR = os.path.join(project_root, 'data')
BALANCE_FILE = os.path.join(DATA_DIR, 'Balance Azucarero - Hoja 1.csv')

VARIACION_CONSUMO = 0.15 
VARIACION_PRODUCCION = 0.10 

patron_zafra = {
    1: 0.00, 2: 0.00, 3: 0.00, 4: 0.05, 5: 0.10, 6: 0.20,
    7: 0.25, 8: 0.25, 9: 0.10, 10: 0.05, 11: 0.00, 12: 0.00
}

# --- 1. Funciones de Carga de Supuestos ---

def cargar_supuestos_anuales(year):
    """Carga los supuestos anuales para un año específico."""
    try:
        # Busca en DATA_DIR, ya que main.py usa la brújula y la carpeta data
        file_path = os.path.join(DATA_DIR, 'Balance Azucarero - Hoja 1.csv') 

        df = pd.read_csv(file_path, skiprows=3, header=None, encoding='utf-8-sig')
        df.columns = ['Fecha', 'stock_inicial', 'produccion_tucuman', 'produccion_salta_jujuy', 'consumo_azucar', 'consumo_alcohol', 'exportacion', 'stock_final']
        df['Fecha'] = pd.to_datetime(df['Fecha'], format='%d-%m-%y', errors='coerce')
        df.dropna(subset=['Fecha'], inplace=True)
        
        fila_año = df[df['Fecha'].dt.year == year].iloc[0]
        
        produccion_anual = pd.to_numeric(fila_año['produccion_tucuman'], errors='coerce') + pd.to_numeric(fila_año['produccion_salta_jujuy'], errors='coerce')
        consumo_anual = pd.to_numeric(fila_año['consumo_azucar'], errors='coerce') + pd.to_numeric(fila_año['consumo_alcohol'], errors='coerce')
        stock_inicial = pd.to_numeric(fila_año['stock_inicial'], errors='coerce')
            
        return {"produccion_anual": produccion_anual, "consumo_anual": consumo_anual, "stock_inicial": stock_inicial}
    except Exception as e:
        print(f"ADVERTENCIA: Fallo al cargar supuestos del año {year}. Usando datos de respaldo. Error: {e}")
        return {"produccion_anual": 2_610_000, "consumo_anual": 1_950_000, "stock_inicial": 400_000}


# --- 2. Funciones de Generación (Genera Consumo Real Simulado) ---

def generar_datos_balance_real_simulado(year, supuestos):
    """Genera un DataFrame con el CONSUMO/PRODUCCIÓN REAL diario simulado."""
    
    consumo_mensual_promedio = supuestos['consumo_anual'] / 12
    objetivos_mensuales = {
        mes: {
            "produccion": supuestos['produccion_anual'] * patron_zafra[mes],
            "consumo": consumo_mensual_promedio
        } for mes in range(1, 13)
    }
    
    historial_anual = []
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)
    stock_inicial_mes = supuestos['stock_inicial'] 

    for i in range((end_date - start_date).days + 1):
        current_date = start_date + timedelta(days=i)
        mes = current_date.month
        dias_en_mes = pd.Timestamp(current_date).days_in_month
        
        produccion_diaria_base = objetivos_mensuales[mes]['produccion'] / dias_en_mes
        consumo_diario_base = objetivos_mensuales[mes]['consumo'] / dias_en_mes
        
        # Aplicar variación aleatoria (SIMULACIÓN REAL)
        produccion_real_diaria = round(max(0, produccion_diaria_base * (1 + np.random.uniform(-VARIACION_PRODUCCION, VARIACION_PRODUCCION))), 3)
        consumo_real_diario = round(max(0, consumo_diario_base * (1 + np.random.uniform(-VARIACION_CONSUMO, VARIACION_CONSUMO))), 3)
            
        historial_anual.append({
            'date': current_date,
            'consumo_real_diaria': consumo_real_diario,
            'produccion_real_diaria': produccion_real_diaria,
            'stock_inicial_mes': stock_inicial_mes if current_date.day == 1 else np.nan # Solo el día 1
        })
        
    return pd.DataFrame(historial_anual)

# --- 3. Funciones de Generación (Genera Plan Estratégico Objetivo) ---

def generar_plan_estrategico_diario(year, supuestos):
    """Genera el plan diario de stock, producción y consumo objetivo."""
    
    produccion_anual_estimada = supuestos['produccion_anual']
    consumo_anual_estimado = supuestos['consumo_anual']
    stock_inicial_anual = supuestos['stock_inicial']

    consumo_mensual_estimado = consumo_anual_estimado / 12
    stock_estrategico_objetivo = consumo_mensual_estimado * 2.5 

    # SIMULACIÓN MENSUAL
    resultados_mensuales = []
    stock_inicial_mes = stock_inicial_anual

    for mes_num in range(1, 13):
        produccion_mes = produccion_anual_estimada * patron_zafra[mes_num]
        consumo_mes = consumo_mensual_estimado
        stock_proyectado_sin_exportar = stock_inicial_mes + produccion_mes - consumo_mes
        exportacion_sugerida = max(0, stock_proyectado_sin_exportar - stock_estrategico_objetivo)
        stock_final_mes = stock_proyectado_sin_exportar - exportacion_sugerida
        
        resultados_mensuales.append({
            'Mes': mes_num,
            'Stock Inicial (TN)': stock_inicial_mes,
            'Consumo (TN)': consumo_mes,
            'Producción (TN)': produccion_mes,
            'Stock Final (TN)': stock_final_mes
        })
        stock_inicial_mes = stock_final_mes 

    df_simulacion = pd.DataFrame(resultados_mensuales)
    
    # GENERACIÓN DEL PLAN DIARIO
    daily_goals_list = []
    
    for index, row in df_simulacion.iterrows():
        mes_num = int(row['Mes'])
        first_day_of_month = pd.Timestamp(year, mes_num, 1)
        dias_en_mes = first_day_of_month.days_in_month

        consumo_diario_objetivo = row['Consumo (TN)'] / dias_en_mes
        produccion_diaria_objetivo = row['Producción (TN)'] / dias_en_mes
        stock_inicial_mes_obj = row['Stock Inicial (TN)']
        stock_final_mes_objetivo = row['Stock Final (TN)'] 
        
        fechas_del_mes = pd.date_range(start=first_day_of_month, periods=dias_en_mes, freq='D')

        for i, fecha_diaria in enumerate(fechas_del_mes):
            stock_diario_objetivo = stock_inicial_mes_obj + \
                                    (stock_final_mes_objetivo - stock_inicial_mes_obj) * \
                                    ((i + 1) / dias_en_mes)
            
            daily_goals_list.append({
                'date': fecha_diaria.date(),
                'consumo_diario_objetivo': consumo_diario_objetivo,
                'produccion_diaria_objetivo': produccion_diaria_objetivo,
                'stock_diario_objetivo': stock_diario_objetivo,
                'stock_estrategico_mensual': stock_estrategico_objetivo 
            })
    
    return pd.DataFrame(daily_goals_list)

# --- 4. Función Principal del Seeder ---

def run_balance_seeder():
    print("\n--- 🌱 SEMBRANDO DATOS DE BALANCE REAL Y PLAN ESTRATÉGICO ---")
    
    engine = get_db_engine()
    
    # 1. GENERAR DATOS
    historial_total = []
    plan_diario_total = []
    
    for year in [2024, 2025]:
        supuestos = cargar_supuestos_anuales(year)
        
        # Generar Historial REAL Simulado (para balance_historial_real)
        df_real = generar_datos_balance_real_simulado(year, supuestos)
        historial_total.append(df_real)
        
        # Generar Plan ESTRATÉGICO Objetivo (para prd_plan_diario)
        df_plan = generar_plan_estrategico_diario(year, supuestos)
        plan_diario_total.append(df_plan)


    df_historial_final = pd.concat(historial_total, ignore_index=True)
    df_plan_final = pd.concat(plan_diario_total, ignore_index=True)

    # Rellenar el Stock Inicial del Mes
    df_historial_final['stock_inicial_mes'] = df_historial_final['stock_inicial_mes'].ffill() 
    df_historial_final.dropna(subset=['consumo_real_diaria'], inplace=True)
    
    # 2. LIMPIAR Y SEMBRAR TABLA: balance_historial_real
    print("   🧹 Limpiando y sembrando 'balance_historial_real'...")
    with engine.connect() as con:
        con.execute(text("TRUNCATE TABLE balance_historial_real RESTART IDENTITY"))
        con.commit()

    try:
        df_historial_final.to_sql('balance_historial_real', engine, if_exists='append', index=False)
        print(f"   ✅ Semilla de Historial Real completada. Total: {len(df_historial_final)} filas.")
    except Exception as e:
        print(f"   ❌ ERROR al guardar el balance real: {e}")
        return False
        
    # 3. LIMPIAR Y SEMBRAR TABLA: prd_plan_diario
    print("   🧹 Limpiando y sembrando 'prd_plan_diario'...")
    with engine.connect() as con:
        con.execute(text("TRUNCATE TABLE prd_plan_diario RESTART IDENTITY"))
        con.commit()
    
    try:
        df_plan_final.to_sql('prd_plan_diario', engine, if_exists='append', index=False)
        print(f"   ✅ Semilla de Plan Estratégico completada. Total: {len(df_plan_final)} filas.")
        return True
    except Exception as e:
        print(f"   ❌ ERROR al guardar el plan estratégico: {e}")
        return False

if __name__ == "__main__":
    run_balance_seeder()