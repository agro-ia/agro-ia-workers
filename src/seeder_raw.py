import pandas as pd
import os
import sys

# --- CORRECCIÓN DE RUTAS (LA BRÚJULA) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from sqlalchemy import text
from config.db import get_db_engine

# --- Definir dónde están los datos ---
# Usamos project_root que ya calculamos arriba
DATA_DIR = os.path.join(project_root, 'data') 

FILES_TO_TICKERS = {
    'Futuros azúcar Nº11 EE.UU.csv': 'US Sugar #11',
    'Futuros petróleo Brent.csv': 'Brent Oil',
    'Futuros petróleo crudo WTI.csv': 'Crude Oil WTI',
    'Índice dólar(DXY).csv': 'US Dollar Index',
    'Futuros Índice dólar-diciembre(DXZ5).csv': 'US Dollar Index Future',
    'Micro Henry Hub Natural Gas Futures.csv': 'Natural Gas',
    'USD_ARS.csv': 'USD/ARS',
    'USD_BRL.csv': 'USD/BRL'
}

def run_raw_seeder():
    print(f"\n--- 🌱 SEMBRANDO DATOS DESDE: {DATA_DIR} ---")
    
    # Verificación de seguridad
    if not os.path.exists(DATA_DIR):
        print(f"❌ Error crítico: No existe la carpeta '{DATA_DIR}'")
        print("   Por favor crea la carpeta 'datos' en la raíz y mueve los CSV ahí.")
        return

    engine = get_db_engine()
    
    # 1. Limpiar tabla raw existente
    print("   🧹 Limpiando tabla 'raw_market_data'...")
    with engine.connect() as con:
        con.execute(text("TRUNCATE TABLE raw_market_data RESTART IDENTITY"))
        con.commit()

    total_inserted = 0
    
    for filename, ticker in FILES_TO_TICKERS.items():
        filepath = os.path.join(DATA_DIR, filename)
        
        if not os.path.exists(filepath):
            print(f"   ⚠️ Archivo no encontrado: {filename} (Saltando)")
            continue
            
        try:
            print(f"   📖 Procesando {ticker}...")
            df = pd.read_csv(filepath)
            
            # Normalización
            df.columns = [c.lower() for c in df.columns]
            df['ticker'] = ticker
            valid_cols = ['date', 'ticker', 'open', 'high', 'low', 'close', 'currency']
            cols_to_use = [c for c in valid_cols if c in df.columns]
            df_final = df[cols_to_use].copy() 
            
            # Formato fecha día/mes/año (común en latam) o estándar
            # dayfirst=True ayuda si tienes fechas como 01/02/2024 (1 de feb)
            df_final['date'] = pd.to_datetime(df_final['date'], dayfirst=True, errors='coerce')
            df_final.dropna(subset=['date'], inplace=True) # Borrar si falla la fecha

            df_final.to_sql('raw_market_data', engine, if_exists='append', index=False)
            
            rows = len(df_final)
            total_inserted += rows
            print(f"      ✅ Insertadas {rows} filas.")
            
        except Exception as e:
            print(f"      ❌ Error procesando {filename}: {e}")

    print(f"\n✨ SEMILLA COMPLETADA. Total filas insertadas: {total_inserted}")
    print("   👉 Ahora ejecuta 'python main.py' para procesar estos datos.")

if __name__ == "__main__":
    run_raw_seeder()