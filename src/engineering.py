import pandas as pd
from statsmodels.tsa.api import STL
from sqlalchemy import text
from config.db import get_db_engine

def run_feature_engineering():
    print("\n--- [3/3] INGENIERÍA DE FEATURES (ENGINEERING) ---")
    engine = get_db_engine()
    
    try:
        # 1. Leer datos limpios (Solo necesitamos fecha y el precio a analizar)
        # Analizaremos la estacionalidad del Azúcar #5 ('sugar_5')
        print("   🧠 Leyendo histórico de Azúcar #5...")
        query = "SELECT date, sugar_5 FROM market_metrics ORDER BY date ASC"
        df = pd.read_sql(query, engine)
        
        if df.empty or 'sugar_5' not in df.columns:
            print("   ⚠️ No hay suficientes datos en market_metrics.")
            return False

        # Preparar índice temporal
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        # Asegurar frecuencia diaria (rellenando huecos si quedó alguno)
        series = df['sugar_5'].asfreq('D').ffill().bfill()

        # 2. Configurar STL (Descomposición)
        n_obs = len(series)
        
        # Lógica adaptativa: STL necesita 2 ciclos completos.
        # Si tenemos > 2 años (730 días), buscamos patrón anual.
        # Si no, buscamos patrón semanal (para que el código corra en pruebas).
        if n_obs > 730:
            print(f"   📉 Detectando estacionalidad ANUAL con {n_obs} datos...")
            periodo = 365
        else:
            print(f"   ⚠️ Pocos datos ({n_obs}). Usando estacionalidad SEMANAL para prueba...")
            periodo = 7 # Semanal

        # 3. Calcular Estacionalidad
        stl = STL(series, period=periodo, seasonal=13)
        res = stl.fit()
        
        # Extraemos solo el componente estacional
        seasonality = res.seasonal
        
        # 4. Preparar DataFrame para guardar
        df_features = pd.DataFrame(seasonality)
        df_features.columns = ['sugar_5_seasonality']
        df_features.reset_index(inplace=True)
        
        # 5. Guardar en SQL
        # Limpiamos tabla previa para evitar duplicados en esta prueba
        with engine.connect() as con:
            con.execute(text("TRUNCATE TABLE seasonality_features RESTART IDENTITY"))
            con.commit()

        print(f"   💾 Guardando {len(df_features)} features en 'seasonality_features'...")
        df_features.to_sql('seasonality_features', engine, if_exists='append', index=False)
        
        print("   ✅ ¡Features calculadas exitosamente!")
        return True

    except Exception as e:
        print(f"   ❌ Error calculando features: {e}")
        return False