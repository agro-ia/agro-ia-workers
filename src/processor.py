import pandas as pd
from sqlalchemy import text
from config.db import get_db_engine

# Mapeo: Nombre en 'raw_market_data' (ticker) -> Nombre de columna en 'market_metrics'
TICKER_MAP = {
    'US Sugar #11': 'sugar_11',
    'White Sugar': 'sugar_5',
    'USD/ARS': 'fx_ars_usd',
    'USD/BRL': 'fx_brl_usd',
    'US Dollar Index': 'fx_dxy',
    'Crude Oil WTI': 'oil_wti',
    'Brent Oil': 'oil_brent',
    'Natural Gas': 'natgas_hh',
    'Dutch TTF Gas': 'natgas_ttf',
    'Ethanol Futures': 'ethanol'
}

def run_dataset_creation():
    print("\n--- [2/3] PROCESANDO Y CREANDO MAESTRO (PROCESSOR) ---")
    engine = get_db_engine()
    
    try:
        # 1. Leer datos crudos desde SQL
        print("   📖 Leyendo datos crudos...")
        query = "SELECT date, ticker, close FROM raw_market_data ORDER BY date ASC"
        df_raw = pd.read_sql(query, engine)
        
        if df_raw.empty:
            print("   ⚠️ No hay datos crudos para procesar.")
            return False

        # 2. Pivotar la tabla (Transformación clave)
        # Convertimos filas (ticker) en columnas
        print("   🔄 Pivotando y limpiando...")
        df_raw['date'] = pd.to_datetime(df_raw['date'])
        
        # Pivot: Índice=Fecha, Columnas=Ticker, Valores=Close
        df_pivot = df_raw.pivot_table(index='date', columns='ticker', values='close')
        
        # 3. Renombrar columnas según nuestro esquema
        df_pivot.rename(columns=TICKER_MAP, inplace=True)
        
        # 4. Rellenar huecos (Imputación)
        # ffill: Rellena con el valor de ayer (útil para feriados)
        # bfill: Rellena con el valor de mañana (para huecos al inicio)
        df_pivot = df_pivot.ffill()
        df_pivot = df_pivot.bfill()
        
        # 5. Preparar para guardar
        df_final = df_pivot.reset_index() # 'date' vuelve a ser columna
        
        # Seleccionar solo las columnas que existen en nuestro mapa (para evitar errores)
        cols_validas = ['date'] + [col for col in TICKER_MAP.values() if col in df_final.columns]
        df_final = df_final[cols_validas]

        # 6. Guardar en 'market_metrics' (Upsert o Replace)
        # Para simplificar, usaremos 'replace' (borra y crea) o limpiamos la tabla antes.
        # Dado que pandas 'replace' borra la tabla y sus tipos, es mejor borrar los datos
        # y usar 'append'.
        
        with engine.connect() as con:
            con.execute(text("TRUNCATE TABLE market_metrics RESTART IDENTITY"))
            con.commit()
            
        print(f"   💾 Guardando {len(df_final)} filas en 'market_metrics'...")
        df_final.to_sql('market_metrics', engine, if_exists='append', index=False)
        
        print("   ✅ ¡Dataset Maestro actualizado exitosamente!")
        return True

    except Exception as e:
        print(f"   ❌ Error en el procesador: {e}")
        import traceback
        traceback.print_exc()
        return False