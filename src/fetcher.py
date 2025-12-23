import investpy
import yfinance as yf
import pandas as pd
import time
from datetime import datetime
from config.db import get_db_engine
from sqlalchemy import text

# --- CONFIGURACIÓN DE ACTIVOS ---
ACTIVOS = [
    # AZÚCAR (LONDRES #5 y EEUU #11)
    {'ticker': 'White Sugar', 'tipo': 'commodity', 'nombre_investpy': 'London Sugar', 'pais': 'united kingdom', 'yfinance': 'SF=F'},
    {'ticker': 'US Sugar #11', 'tipo': 'commodity', 'nombre_investpy': 'US Sugar #11', 'pais': 'united states', 'yfinance': 'SB=F'},
    
    # MONEDAS
    {'ticker': 'USD/ARS', 'tipo': 'currency_cross', 'nombre_investpy': 'USD/ARS', 'pais': None, 'yfinance': 'ARS=X'},
    {'ticker': 'USD/BRL', 'tipo': 'currency_cross', 'nombre_investpy': 'USD/BRL', 'pais': None, 'yfinance': 'BRL=X'},
    {'ticker': 'US Dollar Index', 'tipo': 'index', 'nombre_investpy': 'US Dollar Index', 'pais': 'united states', 'yfinance': 'DX-Y.NYB'},
    
    # PETRÓLEO
    {'ticker': 'Crude Oil WTI', 'tipo': 'commodity', 'nombre_investpy': 'Crude Oil WTI', 'pais': 'united states', 'yfinance': 'CL=F'},
    {'ticker': 'Brent Oil', 'tipo': 'commodity', 'nombre_investpy': 'Brent Oil', 'pais': 'united kingdom', 'yfinance': 'BZ=F'},
    
    # GAS
    {'ticker': 'Natural Gas', 'tipo': 'commodity', 'nombre_investpy': 'Natural Gas', 'pais': 'united states', 'yfinance': 'NG=F'},
    {'ticker': 'Dutch TTF Gas', 'tipo': 'commodity', 'nombre_investpy': 'Dutch TTF Natural Gas Futures', 'pais': 'netherlands', 'yfinance': 'TTF=F'},
    
    # ETANOL
    {'ticker': 'Ethanol Futures', 'tipo': 'commodity', 'nombre_investpy': 'Ethanol', 'pais': 'united states', 'yfinance': 'EH=F'}
]

def obtener_datos_yfinance(activo, fecha_inicio_dt, fecha_fin_dt):
    """Descarga datos usando yfinance como fallback."""
    try:
        if 'yfinance' not in activo or not activo['yfinance']:
            return None
            
        yf_ticker = activo['yfinance']
        print(f"   🔄 Intentando con yfinance: {yf_ticker}")
        
        ticker_obj = yf.Ticker(yf_ticker)
        df = ticker_obj.history(start=fecha_inicio_dt, end=fecha_fin_dt)
        
        if df is not None and not df.empty:
            # Estandarización para la DB
            df['ticker'] = activo['ticker']
            df.reset_index(inplace=True)
            
            # Renombrar columnas
            df.rename(columns={
                'Date': 'date', 'Open': 'open', 'High': 'high',
                'Low': 'low', 'Close': 'close'
            }, inplace=True)
            
            # Agregar currency (yfinance no siempre la provee)
            if 'currency' not in df.columns:
                df['currency'] = 'USD'  # Asumimos USD por defecto
            
            # Seleccionar columnas
            cols = ['date', 'ticker', 'open', 'high', 'low', 'close', 'currency']
            cols_existentes = [c for c in cols if c in df.columns]
            
            return df[cols_existentes]
            
    except Exception as e:
        print(f"   ❌ Error con yfinance: {e}")
        return None

def obtener_datos(activo, fecha_inicio):
    """Descarga datos de un solo activo usando investpy con fallback a yfinance."""
    fecha_fin = datetime.now().strftime('%d/%m/%Y')
    print(f"   ⬇️ Descargando {activo['ticker']} ({fecha_inicio} - {fecha_fin})...")
    
    # Intentar con investpy primero
    try:
        df = None
        # Selección de función según tipo
        if activo['tipo'] == 'commodity':
            df = investpy.get_commodity_historical_data(commodity=activo['nombre_investpy'], country=activo['pais'], from_date=fecha_inicio, to_date=fecha_fin)
        elif activo['tipo'] == 'currency_cross':
            df = investpy.get_currency_cross_historical_data(currency_cross=activo['nombre_investpy'], from_date=fecha_inicio, to_date=fecha_fin)
        elif activo['tipo'] == 'index':
            df = investpy.get_index_historical_data(index=activo['nombre_investpy'], country=activo['pais'], from_date=fecha_inicio, to_date=fecha_fin)
        
        if df is not None and not df.empty:
            # Estandarización mínima para la DB
            df['ticker'] = activo['ticker'] # Añadimos columna para identificar de qué activo es
            df.reset_index(inplace=True)    # Sacamos 'Date' del índice para que sea columna
            
            # Renombramos columnas a minúsculas para SQL estándar
            df.rename(columns={
                'Date': 'date', 'Open': 'open', 'High': 'high', 
                'Low': 'low', 'Close': 'close', 'Currency': 'currency'
            }, inplace=True)
            
            # Seleccionamos solo columnas útiles (ignoramos Volume si no siempre viene)
            cols = ['date', 'ticker', 'open', 'high', 'low', 'close', 'currency']
            # Filtramos solo las que existan (por si currency no viene en índices)
            cols_existentes = [c for c in cols if c in df.columns]
            
            print(f"   ✅ Obtenido con investpy")
            return df[cols_existentes]
            
    except Exception as e:
        print(f"   ⚠️ Error con investpy: {e}")
    
    # Fallback a yfinance si investpy falló
    print(f"   🔄 Usando yfinance como fallback...")
    fecha_inicio_dt = datetime.strptime(fecha_inicio, '%d/%m/%Y')
    fecha_fin_dt = datetime.now()
    
    df = obtener_datos_yfinance(activo, fecha_inicio_dt, fecha_fin_dt)
    if df is not None and not df.empty:
        print(f"   ✅ Obtenido con yfinance")
        return df
    
    print(f"   ❌ No se pudo obtener datos ni con investpy ni con yfinance")
    return None

def run_fetch_process():
    print("\n--- [1/3] INICIANDO DESCARGA DE DATOS (A DB) ---")
    
    engine = get_db_engine()
    FECHA_INICIO = '01/01/2024'
    TABLE_NAME = 'raw_market_data'
    
    exitos = 0
    total_filas = 0

    for activo in ACTIVOS:
        df = obtener_datos(activo, FECHA_INICIO)
        
        if df is not None and not df.empty:
            try:
                # Guardamos en la tabla 'raw_market_data'.
                # if_exists='append': Agregamos los datos. 
                # NOTA: En producción ideal, manejaríamos duplicados (upsert), 
                # pero para este MVP, 'append' está bien si limpiamos antes o si es carga inicial.
                # Para evitar duplicados rápidos en pruebas, borraremos los datos de ese ticker antes de insertar.
                
                with engine.connect() as con:
                    con.execute(text(f"DELETE FROM {TABLE_NAME} WHERE ticker = :tick AND date >= :fecha"), 
                                {"tick": activo['ticker'], "fecha": datetime.strptime(FECHA_INICIO, '%d/%m/%Y')})
                    con.commit()

                df.to_sql(TABLE_NAME, engine, if_exists='append', index=False)
                
                print(f"   ✅ {activo['ticker']}: {len(df)} filas insertadas en '{TABLE_NAME}'.")
                exitos += 1
                total_filas += len(df)
            except Exception as e:
                print(f"   ❌ Error guardando SQL {activo['ticker']}: {e}")
        
        time.sleep(1)

    print(f"--- Fin de descarga. Actualizados: {exitos} activos. Filas totales: {total_filas} ---")
    return exitos > 0