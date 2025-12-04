import pandas as pd
from sqlalchemy import text
from config.db import get_db_engine

# Mapeo de Tickers Raw -> Nombres Base en DB
TICKER_MAP = {
    'US Sugar #11': 'sugar_11',
    'White Sugar': 'sugar_5',
    'USD/ARS': 'fx_ars_usd',
    'USD/BRL': 'fx_brl_usd',
    'US Dollar Index': 'fx_dxy',
    'US Dollar Index Future': 'fx_dx_future',
    'Crude Oil WTI': 'oil_wti',
    'Brent Oil': 'oil_brent',
    'Natural Gas': 'natgas_hh',
}

def run_dataset_creation():
    print("\n--- [2/3] PROCESANDO Y CREANDO MAESTRO (PROCESSOR V2) ---")
    engine = get_db_engine()
    
    try:
        # 1. Leer datos crudos
        print("   📖 Leyendo datos crudos...")
        query = "SELECT date, ticker, close, high, low FROM raw_market_data ORDER BY date ASC"
        df_raw = pd.read_sql(query, engine)
        
        if df_raw.empty:
            print("   ⚠️ No hay datos crudos para procesar.")
            return False

        # 2. Pivotar múltiples valores (Close, High, Low)
        print("   🔄 Pivotando precios (Close, High, Low)...")
        df_raw['date'] = pd.to_datetime(df_raw['date'])
        
        # Esto crea columnas con índice múltiple: (precio, ticker)
        df_pivot = df_raw.pivot_table(index='date', columns='ticker', values=['close', 'high', 'low'])
        
        # 3. Aplanar y Renombrar columnas
        new_columns = []
        # df_pivot.columns es un MultiIndex. Ejemplo: ('close', 'US Sugar #11')
        for price_type, ticker in df_pivot.columns:
            base_name = TICKER_MAP.get(ticker)
            if not base_name:
                continue # Ignoramos tickers que no estén en el mapa
            
            if price_type == 'close':
                new_columns.append(base_name)        # ej: sugar_11
            else:
                new_columns.append(f"{base_name}_{price_type}") # ej: sugar_11_high
        
        df_pivot.columns = new_columns
        
        # 4. Limpieza y Relleno
        # Rellenamos huecos hacia adelante y atrás
        df_pivot = df_pivot.ffill().bfill()
        
        # 5. Guardar
        df_final = df_pivot.reset_index()
        
        # Seleccionar solo columnas que existen en la DB (para evitar errores si falta alguna)
        # Hacemos una consulta dummy para ver las columnas reales
        with engine.connect() as con:
            db_cols = pd.read_sql("SELECT * FROM market_metrics LIMIT 0", con).columns.tolist()
        
        cols_to_save = [c for c in df_final.columns if c in db_cols]
        df_final = df_final[cols_to_save]

        # Borrar y reescribir tabla maestra
        with engine.connect() as con:
            con.execute(text("TRUNCATE TABLE market_metrics RESTART IDENTITY"))
            con.commit()
            
        print(f"   💾 Guardando {len(df_final)} filas (con High/Low) en 'market_metrics'...")
        df_final.to_sql('market_metrics', engine, if_exists='append', index=False)
        
        print("   ✅ ¡Dataset Maestro V2 actualizado!")
        return True

    except Exception as e:
        print(f"   ❌ Error en el procesador: {e}")
        import traceback
        traceback.print_exc()
        return False