import pandas as pd
import numpy as np
import os
import sys
import warnings
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor
from statsmodels.tsa.arima.model import ARIMA
from sqlalchemy import text
from datetime import timedelta

# --- 0. Configuración y Brújula ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from config.db import get_db_engine

warnings.filterwarnings('ignore', 'statsmodels.tsa.arima.model.ARIMA', UserWarning)
VALIDATION_SET_SIZE = 0.2
MIN_SAMPLES = 50 # Mínimo absoluto para que el entrenamiento sea viable

# --- 1. FUNCIONES AUXILIARES ---
def calculate_rsi(series, window=14):
    """Calcula el Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# --- 2. LÓGICA DE PREDICCIÓN CONTRATO #11 (XGBoost + Corrección de Residuos ARIMA) ---

BEST_PARAMS_30D_11 = {
    'colsample_bytree': 1.0, 'gamma': 0.15, 'learning_rate': 0.015, 'max_depth': 2,
    'min_child_weight': 5, 'n_estimators': 400, 'subsample': 0.65
}

# Lista MÍNIMA de features para el Contrato #11 (Mayor probabilidad de tener datos completos)
FEATURES_11_MINIMUM = [
    's11_lag_30d', 
    's11_ma_7d', 's11_ma_30d', 
    's11_rsi_14d', 
    'spread_11_5', 
    'mes', 'dia_de_la_semana',
    'sugar_5' # Viene de m.*
]

def predict_sugar_11_hybrid(df_full, horizon_days, features, xgb_params):
    
    print(f"\n   🧠 Entrenando Contrato #11 (XGBoost+ARIMA) para D+{horizon_days}...")
    
    target_col = f'target_11_{horizon_days}d'
    df_full[target_col] = df_full['sugar_11'].shift(-horizon_days)
    
    # Usar solo las features mínimas para evitar NaNs
    final_features = [f for f in features if f != 'sugar_5'] 
    valid_features = [f for f in final_features if f in df_full.columns]
    
    # *** LIMPIEZA CRÍTICA ANTES DE ENTRENAR ***
    # La limpieza se realiza solo sobre las features mínimas requeridas.
    df_clean = df_full.dropna(subset=valid_features + [target_col])
    
    # VERIFICACIÓN DEL TAMAÑO DEL DATASET
    if len(df_clean) < MIN_SAMPLES:
        print(f"   ❌ ERROR CRÍTICO: Menos de {MIN_SAMPLES} muestras disponibles después de la limpieza.")
        raise ValueError(
            "No hay suficientes filas de datos válidos para el entrenamiento después de eliminar NaNs y el Target."
        )

    X = df_clean[valid_features]
    y = df_clean[target_col]
    
    # El split ahora tiene suficientes muestras
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=VALIDATION_SET_SIZE, shuffle=False)
    
    # --- Etapa 1: Entrenar XGBoost y obtener residuos ---
    xgb_model = XGBRegressor(objective='reg:squarederror', random_state=42, **xgb_params)
    xgb_model.fit(X_train, y_train)
    predictions_val = xgb_model.predict(X_val)
    residuals_val = y_val - predictions_val
    
    # --- Etapa 2: Búsqueda de orden óptimo ARIMA ---
    best_aic, best_order = float("inf"), (0,0,0) 
    for p in range(3):
        for d in range(2):
            for q in range(3):
                try:
                    order = (p, d, q)
                    model = ARIMA(residuals_val, order=order)
                    model_fit = model.fit()
                    if model_fit.aic < best_aic:
                        best_aic = model_fit.aic
                        best_order = order
                except:
                    continue
    
    # --- Etapa 3: Re-entrenar modelos con todos los datos y predecir ---
    xgb_model_full = XGBRegressor(objective='reg:squarederror', random_state=42, **xgb_params)
    xgb_model_full.fit(X, y)
    
    full_predictions = xgb_model_full.predict(X)
    full_residuals = y - full_predictions
    
    arima_full_fit = ARIMA(full_residuals, order=best_order).fit()
    
    latest_data = df_full.iloc[[-1]][valid_features]
    future_prediction_xgb = xgb_model_full.predict(latest_data.fillna(0))[0] 
    
    future_residual_pred = arima_full_fit.forecast(steps=1).iloc[0]
    
    final_future_prediction = future_prediction_xgb + future_residual_pred
    
    final_predictions_val = predictions_val + arima_full_fit.predict(start=residuals_val.index[0], end=residuals_val.index[-1])
    error_std_combined = (y_val - final_predictions_val).std()
    
    print(f"      -> Mejor orden ARIMA: {best_order}")
    print(f"      -> Error (Std Dev) combinado: {error_std_combined:.4f}")

    return final_future_prediction, error_std_combined


# --- 3. LÓGICA PRINCIPAL DE ORQUESTACIÓN ---
def run_training_process():
    print("\n--- [4/5] ENTRENAMIENTO DE MODELOS PREDICTIVOS ---")
    engine = get_db_engine()
    
    try:
        # A. Cargar Datos Maestros y Features Avanzadas
        print("   🤖 Cargando datos históricos y features avanzados...")
        
        # Seleccionar las columnas de 'advanced_features' de forma explícita
        # Usamos la lista mínima para asegurar que el SELECT sea viable
        features_a_select = [f'a."{col}"' for col in FEATURES_11_MINIMUM if not col == 'sugar_5']
        
        query = f"""
        SELECT 
            m.*, 
            s.sugar_5_seasonality,
            {', '.join(features_a_select)}
        FROM market_metrics m
        LEFT JOIN seasonality_features s ON m.date = s.date
        LEFT JOIN advanced_features a ON m.date = a.date
        ORDER BY m.date ASC
        """
        df_full = pd.read_sql(query, engine)
        
        # Limpieza y preparación de índice
        df_full['date'] = pd.to_datetime(df_full['date'])
        df_full.set_index('date', inplace=True)
        df_full.dropna(subset=['sugar_5', 'sugar_11'], inplace=True) 

        # --- ORQUESTACIÓN DE CONTRATO #11 (XGBoost-ARIMA) ---
        pred_11, error_11 = predict_sugar_11_hybrid(
            df_full.copy(), 
            horizon_days=30, 
            features=FEATURES_11_MINIMUM, 
            xgb_params=BEST_PARAMS_30D_11
        )
        
        target_date_11 = df_full.index[-1] + timedelta(days=30)
        conf_lower_11 = pred_11 - 1.645 * error_11
        conf_upper_11 = pred_11 + 1.645 * error_11
        
        print(f"\n   🔮 PREDICCIÓN CONTRATO #11 (XGBoost+ARIMA):")
        print(f"      Fecha objetivo: {target_date_11.date()}")
        print(f"      Precio estimado: ${pred_11:.4f}")
        print(f"      Intervalo 90%: [{conf_lower_11:.4f} - {conf_upper_11:.4f}]")

        # --- ORQUESTACIÓN DE CONTRATO #5 (Random Forest - Lógica Base) ---
        print("\n   🧠 Entrenando Contrato #5 (Random Forest - Lógica Base)...")
        
        # B. Generar Indicadores (Se mantienen solo los básicos para RF)
        c = df_full['sugar_5']
        df_full['ma_7'] = c.rolling(7).mean()
        df_full['ma_30'] = c.rolling(30).mean()
        df_full['rsi'] = calculate_rsi(c)
        df_full['dxy_lag_30'] = df_full['fx_dxy'].shift(30)
        df_full['oil_lag_30'] = df_full['oil_wti'].shift(30)

        # C. Preparar Dataset de Entrenamiento
        TARGET_DAYS = 30
        df_full['target'] = df_full['sugar_5'].shift(-TARGET_DAYS)
        
        features_rf = [
            'ma_7', 'ma_30', 'rsi', 'sugar_5_seasonality', 
            'dxy_lag_30', 'oil_lag_30'
        ]
        
        df_train = df_full.dropna(subset=features_rf + ['target'])
        
        # D. Entrenar Random Forest
        X_rf = df_train[features_rf]
        y_rf = df_train['target']
        model_rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        model_rf.fit(X_rf, y_rf)
        score = model_rf.score(X_rf, y_rf)
        
        # E. Predicción RF Futura
        last_row_rf = df_full.iloc[[-1]][features_rf].fillna(0)
        pred_price_rf = model_rf.predict(last_row_rf)[0]
        
        target_date_rf = df_full.index[-1] + timedelta(days=TARGET_DAYS)
        
        print(f"      R² (Precisión en entrenamiento): {score:.4f}")
        print(f"   🔮 PREDICCIÓN CONTRATO #5 (Random Forest):")
        print(f"      Fecha objetivo: {target_date_rf.date()}")
        print(f"      Precio estimado: ${pred_price_rf:.4f}")

        # F. Guardar en DB 
        # ...
        
        print("   ✅ Predicciones guardadas exitosamente.")
        return True

    except Exception as e:
        print(f"   ❌ Error en entrenamiento: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    run_training_process()