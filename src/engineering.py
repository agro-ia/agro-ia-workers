import pandas as pd
import numpy as np
import os
import sys
from statsmodels.tsa.api import STL
from sqlalchemy import text
from config.db import get_db_engine
from datetime import date 

# --- FUNCIONES DE INDICADORES TÉCNICOS (Mantenidas) ---
def calculate_rsi(series, window=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(series, short_window=12, long_window=26, signal_window=9):
    ema_short = series.ewm(span=short_window, adjust=False).mean()
    ema_long = series.ewm(span=long_window, adjust=False).mean()
    macd_line = ema_short - ema_long
    signal_line = macd_line.ewm(span=signal_window, adjust=False).mean()
    return macd_line, macd_line - signal_line

def calculate_bollinger_bands(series, window=20, num_std=2):
    rolling_mean = series.rolling(window=window).mean()
    rolling_std = series.rolling(window=window).std()
    upper_band = rolling_mean + (rolling_std * num_std)
    lower_band = rolling_mean - (rolling_std * num_std)
    return upper_band, lower_band

def calculate_atr(high, low, close, window=14):
    high_low = high - low
    high_close = np.abs(high - close.shift())
    low_close = np.abs(low - close.shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.ewm(alpha=1/window, adjust=False).mean()
# --------------------------------------------------------------------------------

def run_feature_engineering():
    print("\n--- [3/5] INGENIERÍA DE FEATURES AVANZADAS Y ESTACIONALIDAD ---")
    engine = get_db_engine()
    
    try:
        # 1. Leer datos limpios
        print("   🧠 Leyendo histórico completo desde 'market_metrics'...")
        
        # *** FILTRAR DATOS HASTA HOY ***
        today_date = date.today().strftime('%Y-%m-%d')
        
        query = f"""
        SELECT * FROM market_metrics 
        WHERE date <= '{today_date}' 
        ORDER BY date ASC
        """
        df = pd.read_sql(query, engine)
        
        if df.empty or 'sugar_5' not in df.columns or 'sugar_11' not in df.columns:
            print("   ⚠️ No hay suficientes datos o faltan columnas clave (sugar_5, sugar_11).")
            return False

        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df.sort_index(inplace=True)
        
        df = df.ffill().bfill() 
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        
        # --- SECCIÓN A: FEATURES AVANZADAS ---
        s11 = df['sugar_11']
        s5 = df['sugar_5']
        
        # 2. Lags de Referencia (30, 60, 90 días)
        for lag in [30, 60, 90]:
            df[f's11_lag_{lag}d'] = s11.shift(lag)
            df[f'oil_wti_lag_{lag}d'] = df['oil_wti'].shift(lag)
            if 'ethanol' in df.columns:
                 df[f'ethanol_lag_{lag}d'] = df['ethanol'].shift(lag)
            
        # 3. Medias Móviles y Volatilidad
        for window in [7, 30, 90]:
            df[f's11_ma_{window}d'] = s11.rolling(window=window).mean()
        
        df['s11_rsi_14d'] = calculate_rsi(s11)
        df['s11_volatilidad_30d'] = s11.rolling(window=30).std()
        
        # 4. Indicadores Adicionales
        df['s11_macd'], df['s11_macd_hist'] = calculate_macd(s11)
        df['s11_bollinger_upper'], df['s11_bollinger_lower'] = calculate_bollinger_bands(s11)
        if all(col in df.columns for col in ['sugar_11_high', 'sugar_11_low']):
            df['s11_atr'] = calculate_atr(df['sugar_11_high'], df['sugar_11_low'], s11)
        
        # 5. Features de Spread/Relación
        df['spread_11_5'] = s11 - s5
        df['spread_ma_30d'] = df['spread_11_5'].rolling(window=30).mean()
        df['ratio_11_5'] = s11 / s5
        df['spread_vol_30d'] = df['spread_11_5'].rolling(window=30).std()
        
        # 6. Features de Correlación
        for window in [30, 60, 90]:
            df[f'corr_11_5_{window}d'] = s11.rolling(window=window).corr(s5)
            df[f'corr_11_oil_{window}d'] = s11.rolling(window=window).corr(df['oil_wti'])
            if 'ethanol' in df.columns:
                 df[f'corr_11_eth_{window}d'] = s11.rolling(window=window).corr(df['ethanol'])
                 
        # 7. Features de Tiempo
        df['mes'] = df.index.month
        df['dia_de_la_semana'] = df.index.dayofweek
        
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        
        # 8. Guardar Features Avanzadas en nueva tabla
        
        # Seleccionar solo las features CALCULADAS
        features_to_save = [c for c in df.columns if any(p in c for p in ['s11_', 'oil_wti_lag_', 'ethanol_lag_', 'spread_', 'corr_', 'ratio_', 'mes', 'dia_de_la_semana'])]
        
        EXCLUDE_BASE_COLS = [
            'sugar_11', 'sugar_5', 'oil_wti', 'oil_brent', 'natgas_hh', 'natgas_ttf', 'ethanol', 
            'oil_wti_high', 'oil_wti_low', 'oil_brent_high', 'oil_brent_low', 'ethanol_high', 'ethanol_low'
        ]
        
        features_cols = [c for c in features_to_save if c not in EXCLUDE_BASE_COLS]
        
        # *** FILTRADO CRÍTICO FINAL: MÍNIMA DEPENDENCIA ***
        # Solo necesitamos que el lag de la variable objetivo exista.
        CRITICAL_LAG_FEATURES = ['s11_lag_30d'] 

        # Aplicamos el filtro al DataFrame. 
        df_advanced_features = df[features_cols].dropna(subset=CRITICAL_LAG_FEATURES).copy()
        df_advanced_features.reset_index(inplace=True)
        
        print(f"   💾 Guardando {len(df_advanced_features)} features avanzadas en 'advanced_features'...")
        
        # CORRECCIÓN: Usar engine.connect() para ejecutar TRUNCATE
        with engine.connect() as con:
            con.execute(text("TRUNCATE TABLE advanced_features RESTART IDENTITY"))
            con.commit()

        if not df_advanced_features.empty:
            df_advanced_features.to_sql('advanced_features', engine, if_exists='append', index=False)
            print("   ✅ Features Avanzadas calculadas y guardadas.")
        else:
             print("   ❌ ERROR CRÍTICO: No se guardó ninguna feature avanzada (DataFrame vacío).")
             return False 

        # --- SECCIÓN B: ESTACIONALIDAD STL (Contrato #5) ---
        print("\n   📉 Calculando componente de Estacionalidad (STL) para Azúcar #5...")
        series = df['sugar_5'].asfreq('D').interpolate(method='linear') 
        n_obs = len(series)
        periodo = 365 if n_obs > 730 else 7 

        stl = STL(series.dropna(), period=periodo, seasonal=13) 
        res = stl.fit()
        
        df_seasonality = pd.DataFrame(res.seasonal)
        df_seasonality.columns = ['sugar_5_seasonality']
        df_seasonality.reset_index(inplace=True)
        df_seasonality.rename(columns={'index': 'date'}, inplace=True)

        with engine.connect() as con:
            con.execute(text("TRUNCATE TABLE seasonality_features RESTART IDENTITY"))
            con.commit()
            
        df_seasonality.to_sql('seasonality_features', engine, if_exists='append', index=False)
        print("   ✅ Componente de Estacionalidad guardado.")
        
        print("\n✨ INGENIERÍA DE FEATURES COMPLETADA. Listas para el entrenamiento.")
        return True

    except Exception as e:
        print(f"   ❌ Error crítico calculando features: {e}")
        import traceback
        traceback.print_exc()
        return False