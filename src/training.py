import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sqlalchemy import text
from datetime import timedelta
import sys
import os

# Brújula para imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from config.db import get_db_engine

# --- 1. FUNCIONES DE INDICADORES TÉCNICOS (Copiadas de tu script) ---
def calculate_rsi(series, window=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_bollinger_bands(series, window=20):
    sma = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    upper = sma + (std * 2)
    lower = sma - (std * 2)
    return upper, lower, sma

def calculate_stochastic(close, high, low, window=14, smooth_k=3):
    low_min = low.rolling(window=window).min()
    high_max = high.rolling(window=window).max()
    k_percent = 100 * ((close - low_min) / (high_max - low_min))
    d_percent = k_percent.rolling(window=smooth_k).mean()
    return k_percent, d_percent

def calculate_atr(high, low, close, window=14):
    high_low = high - low
    high_close = np.abs(high - close.shift())
    low_close = np.abs(low - close.shift())
    tr = pd.DataFrame({'hl': high_low, 'hc': high_close, 'lc': low_close}).max(axis=1)
    atr = tr.rolling(window=window).mean()
    return atr

def calculate_ichimoku(high, low, close):
    # Tenkan-sen (Conversion Line): (9-period high + 9-period low)/2
    nine_high = high.rolling(window=9).max()
    nine_low = low.rolling(window=9).min()
    tenkan = (nine_high + nine_low) / 2
    
    # Kijun-sen (Base Line): (26-period high + 26-period low)/2
    twenty_six_high = high.rolling(window=26).max()
    twenty_six_low = low.rolling(window=26).min()
    kijun = (twenty_six_high + twenty_six_low) / 2
    
    # Senkou Span A (Leading Span A): (Conversion Line + Base Line)/2
    senkou_a = ((tenkan + kijun) / 2).shift(26)
    
    # Senkou Span B (Leading Span B): (52-period high + 52-period low)/2
    fifty_two_high = high.rolling(window=52).max()
    fifty_two_low = low.rolling(window=52).min()
    senkou_b = ((fifty_two_high + fifty_two_low) / 2).shift(26)
    
    # Chikou Span (Lagging Span): Close plotted 26 days in the past
    chikou = close.shift(-26)
    
    return tenkan, kijun, senkou_a, senkou_b, chikou

# --- 2. LÓGICA PRINCIPAL ---
def run_training_process():
    print("\n--- [4/4] ENTRENAMIENTO DE MODELO CAMPEÓN (ML) ---")
    engine = get_db_engine()
    
    try:
        # A. Cargar Datos
        print("   🤖 Cargando datos históricos...")
        # Traemos todo lo necesario para los indicadores
        query = """
        SELECT * FROM market_metrics ORDER BY date ASC
        """
        df = pd.read_sql(query, engine)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # B. Generar Indicadores (Ingeniería de Features)
        print("   📐 Calculando indicadores técnicos (RSI, Bollinger, Ichimoku)...")
        
        # Sugar #5 (Londres) - El que nos interesa predecir
        c, h, l = df['sugar_5'], df['sugar_5_high'], df['sugar_5_low']
        
        # Rellenar High/Low si son nulos (usando Close) para que no fallen las fórmulas
        h.fillna(c, inplace=True)
        l.fillna(c, inplace=True)

        # Medias Móviles y Lags
        df['ma_7'] = c.rolling(7).mean()
        df['ma_30'] = c.rolling(30).mean()
        df['rsi'] = calculate_rsi(c)
        
        # Bollinger
        upper, lower, sma = calculate_bollinger_bands(c)
        df['bb_width'] = (upper - lower) / sma
        df['bb_percent'] = (c - lower) / (upper - lower)
        
        # Ichimoku
        df['tenkan'], df['kijun'], df['senkou_a'], df['senkou_b'], df['chikou'] = calculate_ichimoku(h, l, c)
        
        # Lags de Referencia (Dólar y Petróleo)
        df['dxy_lag_30'] = df['fx_dxy'].shift(30)
        df['oil_lag_30'] = df['oil_wti'].shift(30)

        # C. Preparar Dataset de Entrenamiento
        # Objetivo: Predecir a 30 días (como el script original)
        TARGET_DAYS = 30
        df['target'] = df['sugar_5'].shift(-TARGET_DAYS)
        
        # Features finales
        features = [
            'ma_7', 'ma_30', 'rsi', 
            'bb_width', 'bb_percent',
            'tenkan', 'kijun', 'senkou_a', 'senkou_b',
            'dxy_lag_30', 'oil_lag_30'
        ]
        
        # Limpiar datos para entrenar (borrar filas con NaNs generados por lags/indicadores)
        df_train = df.dropna(subset=features + ['target'])
        
        if len(df_train) < 100:
            print(f"   ⚠️ Pocos datos para entrenar ({len(df_train)}). Se necesitan más de 100.")
            return False
            
        # D. Entrenar Random Forest
        print(f"   🧠 Entrenando Random Forest con {len(df_train)} registros históricos...")
        X = df_train[features]
        y = df_train['target']
        
        model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        model.fit(X, y)
        
        score = model.score(X, y)
        print(f"      R² (Precisión en entrenamiento): {score:.4f}")

        # E. Predicción Futura
        # Tomamos la ÚLTIMA fila disponible (hoy) para predecir a futuro
        last_row = df.iloc[[-1]][features]
        
        # Verificar si tenemos datos completos hoy (sin NaNs en features)
        if last_row.isnull().values.any():
            print("   ⚠️ No se puede predecir hoy: Faltan datos recientes para calcular indicadores.")
            # Intentamos con la ante-última si la última está incompleta
            last_row = df.iloc[[-2]][features] 
        
        pred_price = model.predict(last_row)[0]
        
        today = df.index[-1]
        target_date = today + timedelta(days=TARGET_DAYS)
        
        print(f"   🔮 PREDICCIÓN (Sugar #5):")
        print(f"      Fecha objetivo: {target_date.date()}")
        print(f"      Precio estimado: ${pred_price:.2f}")

        # F. Guardar en DB
        with engine.connect() as con:
            # Borramos predicción anterior para la misma fecha si existe
            con.execute(text(f"DELETE FROM price_predictions WHERE generated_at = '{today.date()}'"))
            con.commit()
            
        df_pred = pd.DataFrame([{
            'generated_at': today.date(),
            'target_date': target_date.date(),
            'model_name': 'RandomForest_Campeon_30d',
            'predicted_price': pred_price,
            'confidence_interval_lower': pred_price * 0.90, # Bandas estimadas
            'confidence_interval_upper': pred_price * 1.10
        }])
        
        df_pred.to_sql('price_predictions', engine, if_exists='append', index=False)
        print("   ✅ Predicción guardada exitosamente.")
        return True

    except Exception as e:
        print(f"   ❌ Error en entrenamiento: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    run_training_process()