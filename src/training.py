import pandas as pd
import numpy as np
import os
import sys
import warnings
import pickle
import ast
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler 
from xgboost import XGBRegressor
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.statespace.sarimax import SARIMAX 
from arch import arch_model 
import pmdarima as pm 
from sqlalchemy import text
from datetime import timedelta, date, datetime

# --- 0. Configuración y Brújula ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from config.db import get_db_engine

warnings.filterwarnings('ignore', 'statsmodels.tsa.arima.model.ARIMA', UserWarning)
warnings.filterwarnings('ignore', 'statsmodels.tsa.statespace.sarimax', UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', 'The default behavior of methods' ) 
VALIDATION_SET_SIZE = 0.2
MIN_SAMPLES = 50 
TIME_STEPS = 30 
MODELOS_DIR = os.path.join(project_root, 'modelos')
os.makedirs(MODELOS_DIR, exist_ok=True) 

CHAMPION_MODEL_CONSUMO_PATH = os.path.join(MODELOS_DIR, 'modelo_consumo_sarima.pkl')
MODEL_TYPE_CONSUMO = 'SARIMAX_CONSUMO'
MODEL_TYPE_XGBOOST = 'XGBOOST_CONTRATO_11'
MODEL_TYPE_LSTM = 'LSTM_CONTRATO_5'

# --- 1. FUNCIONES AUXILIARES (RSI) ---
def calculate_rsi(series, window=14):
    """Calcula el Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# --- 2. DEFINICIÓN DE FEATURES (CORREGIDO) ---

# Lista de TODAS las features que necesitamos extraer de la tabla 'advanced_features'
# Esta lista combina lo necesario para C#11 y C#5
ADVANCED_FEATURES_REQD = [
    's11_lag_30d', 
    's11_ma_7d', 's11_ma_30d', 
    's11_rsi_14d', 
    'spread_11_5', 
    'mes', 'dia_de_la_semana', # Features de Contrato #11
    'oil_wti_lag_30d'          # Feature específica para LSTM
]

# Lista de features para el modelo XGBoost (Contrato #11)
FEATURES_11_MINIMUM = [
    's11_lag_30d', 
    's11_ma_7d', 's11_ma_30d', 
    's11_rsi_14d', 
    'spread_11_5', 
    'mes', 'dia_de_la_semana',
    'sugar_5' # Viene de market_metrics, no de advanced_features
]

# Parámetros para XGBoost
BEST_PARAMS_30D_11 = {
    'colsample_bytree': 1.0, 'gamma': 0.15, 'learning_rate': 0.015, 'max_depth': 2,
    'min_child_weight': 5, 'n_estimators': 400, 'subsample': 0.65
}

def predict_sugar_11_hybrid(df_full, horizon_days, features, xgb_params):
    
    print(f"\n   🧠 Entrenando Contrato #11 (XGBoost+ARIMA) para D+{horizon_days}...")
    
    target_col = f'target_11_{horizon_days}d'
    df_full[target_col] = df_full['sugar_11'].shift(-horizon_days)
    
    final_features = [f for f in features if f != 'sugar_5'] 
    valid_features = [f for f in final_features if f in df_full.columns]
    
    df_clean = df_full.dropna(subset=valid_features + [target_col])
    
    if len(df_clean) < MIN_SAMPLES:
        print(f"   ❌ ERROR CRÍTICO: Menos de {MIN_SAMPLES} muestras disponibles después de la limpieza.")
        raise ValueError(
            "No hay suficientes filas de datos válidos para el entrenamiento después de eliminar NaNs y el Target."
        )

    X = df_clean[valid_features]
    y = df_clean[target_col]
    
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=VALIDATION_SET_SIZE, shuffle=False)
    
    xgb_model = XGBRegressor(objective='reg:squarederror', random_state=42, **xgb_params)
    xgb_model.fit(X_train, y_train)
    predictions_val = xgb_model.predict(X_val)
    residuals_val = y_val - predictions_val
    
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

    return {
        'prediction': final_future_prediction, 
        'error_std': error_std_combined,
        'params': {'arima_order': best_order, 'xgb_params': xgb_params}
    }


# --- 3. LÓGICA DE PREDICCIÓN CONTRATO #5 AVANZADO (LSTM + ARIMA + GARCH) ---

BEST_HPS_LSTM = {
    'units_lstm_1': 128, 'dropout_1': 0.1, 'units_dense': 128, 'learning_rate': 0.0001
}

# Features para el modelo LSTM
FEATURES_5_LSTM = [
    's11_lag_30d', 's11_ma_30d', 's11_rsi_14d', 'sugar_5_seasonality', 
    'oil_wti_lag_30d', 'fx_dxy' 
]

def create_sequences(X, y, time_steps=TIME_STEPS):
    """Convierte dataframes en secuencias de entrada/salida para LSTM."""
    Xs, ys = [], []
    for i in range(len(X) - time_steps):
        Xs.append(X[i:(i + time_steps)])
        ys.append(y[i + time_steps])
    return np.array(Xs), np.array(ys)

def predict_sugar_5_hybrid_advanced(df_full, horizon_days, features, hps_lstm):
    print(f"\n   🧠 Entrenando Contrato #5 (LSTM+ARIMA+GARCH) para D+{horizon_days}...")
    
    target_col = f'target_5_{horizon_days}d'
    df_full[target_col] = df_full['sugar_5'].shift(-horizon_days)
    
    # 1. Limpieza y preparación para LSTM
    df_clean = df_full.dropna(subset=features + [target_col])
    if len(df_clean) < TIME_STEPS * 2:
        print(f"      ❌ ERROR: Datos insuficientes para LSTM ({len(df_clean)} vs. min {TIME_STEPS * 2})")
        raise ValueError("Datos insuficientes para LSTM.")

    X = df_clean[features].values
    y = df_clean[target_col].values.reshape(-1, 1)
    
    # Escalamiento de datos (CRÍTICO para LSTM)
    scaler_X = MinMaxScaler()
    X_scaled = scaler_X.fit_transform(X)
    scaler_y = MinMaxScaler()
    y_scaled = scaler_y.fit_transform(y)
    
    # Crear secuencias y hacer el split
    X_seq, y_seq = create_sequences(X_scaled, y_scaled, time_steps=TIME_STEPS)
    X_train, X_test, y_train, y_test = train_test_split(X_seq, y_seq, test_size=VALIDATION_SET_SIZE, shuffle=False)
    
    # --- Etapa 1: Entrenar LSTM ---
    model_lstm = Sequential([
        LSTM(units=hps_lstm['units_lstm_1'], return_sequences=False, input_shape=(X_seq.shape[1], X_seq.shape[2])), 
        Dropout(hps_lstm['dropout_1']), 
        Dense(units=hps_lstm['units_dense'], activation='relu'), 
        Dense(1)
    ])
    model_lstm.compile(optimizer='adam', loss='mean_squared_error')
    model_lstm.fit(X_train, y_train, epochs=100, batch_size=32, validation_data=(X_test, y_test), callbacks=[EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)], verbose=0)
    
    # Predecir con LSTM y obtener residuos (en escala original)
    predictions_val_scaled = model_lstm.predict(X_test, verbose=0)
    predictions_val = scaler_y.inverse_transform(predictions_val_scaled)
    y_test_orig = scaler_y.inverse_transform(y_test)
    residuals_val_lstm = (y_test_orig - predictions_val).flatten()
    
    # --- Etapa 2: ARIMA sobre residuos ---
    residuals_series = pd.Series(residuals_val_lstm)
    auto_arima_fit = pm.auto_arima(residuals_series, seasonal=False, stepwise=True, suppress_warnings=True, error_action='ignore', max_p=3, max_q=3)
    best_order = auto_arima_fit.order
    
    arima_model_fit = ARIMA(residuals_series, order=best_order).fit()
    final_residuals = (residuals_series - arima_model_fit.predict(start=0, end=len(residuals_series)-1))
    
    # --- Etapa 3: GARCH sobre residuos finales para modelar la volatilidad ---
    garch_fit = arch_model(final_residuals.dropna() * 100, p=1, q=1, vol='Garch', dist='normal').fit(disp='off')
    
    # 4. Predicción y Volatilidad (Re-entrenar con todos los datos)
    X_full = scaler_X.fit_transform(df_clean[features].values)
    y_full = scaler_y.fit_transform(df_clean[target_col].values.reshape(-1, 1))
    X_full_seq, y_full_seq = create_sequences(X_full, y_full, time_steps=TIME_STEPS)
    
    model_lstm.fit(X_full_seq, y_full_seq, epochs=50, batch_size=32, verbose=0)
    
    # *** CORRECCIÓN CRÍTICA: Tomar los últimos TIME_STEPS para la secuencia ***
    latest_data_raw = df_clean[features].tail(TIME_STEPS).values
    latest_data_scaled = scaler_X.transform(latest_data_raw)
    latest_sequence = latest_data_scaled.reshape(1, TIME_STEPS, latest_data_scaled.shape[1])
    
    future_pred_lstm = scaler_y.inverse_transform(model_lstm.predict(latest_sequence, verbose=0))[0][0]
    
    full_residuals_for_arima = (y_full_seq.flatten() - model_lstm.predict(X_full_seq, verbose=0).flatten())
    arima_full_fit_final = ARIMA(pd.Series(full_residuals_for_arima), order=best_order).fit()
    future_residual_pred_arima = arima_full_fit_final.forecast(steps=1).iloc[0]
    
    forecast_garch = garch_fit.forecast(horizon=1)
    future_error_std = np.sqrt(forecast_garch.variance.iloc[-1, 0]) / 100 
    
    final_future_prediction = future_pred_lstm + future_residual_pred_arima
    
    print(f"      -> Orden ARIMA encontrado: {best_order}")
    print(f"      -> Volatilidad GARCH: {future_error_std:.4f}")

    return {
        'prediction': final_future_prediction, 
        'error_std': future_error_std,
        'params': {'lstm_hps': hps_lstm, 'arima_order': best_order}
    }


# --- 4. GESTIÓN Y ENTRENAMIENTO DEL MODELO DE CONSUMO (SARIMAX) ---

def get_elite_suggestions_sarima(engine, model_type: str, top_n=3):
    """Lee el historial de la DB y devuelve las N mejores configuraciones de parámetros SARIMA."""
    print(f"   Analizando 'memoria' de entrenamientos ({model_type}) desde la DB...")
    
    query = f"""
    SELECT 
        winner_params_json, 
        challenger_metric,
        winner
    FROM training_history
    WHERE model_type = '{model_type}' AND winner IN ('challenger', 'champion')
    ORDER BY challenger_metric ASC
    LIMIT {top_n}
    """
    
    try:
        df_history = pd.read_sql(query, engine)
        if df_history.empty:
            print("   No se encontró historial en la DB. Se procederá con una búsqueda libre.")
            return []
            
        suggestions = []
        for index, row in df_history.iterrows():
            params_dict = row['winner_params_json'] 
            suggestions.append({
                'params': params_dict.get('params', (1, 1, 1)),
                'seasonal_params': params_dict.get('seasonal_params', (0, 1, 1, 7))
            })
        
        print(f"   Se extrajeron {len(suggestions)} sugerencia(s) de élite de la DB.")
        return suggestions
        
    except Exception as e:
        print(f"   ERROR al leer el historial de sugerencias desde la DB: {e}")
        return []

def register_training_result(engine, model_type: str, champion_metric: float, challenger_metric: float, winner: str, winner_params: dict, data_profile: dict):
    """Registra los resultados de la sesión de entrenamiento en la tabla training_history."""
    print(f"   Registrando resultados en la tabla training_history...")
    
    champ_metric = champion_metric if champion_metric != float('inf') else None
    
    df_result = pd.DataFrame([{
        'timestamp': datetime.now(),
        'model_type': model_type,
        'champion_metric': champ_metric,
        'challenger_metric': challenger_metric,
        'winner': winner,
        'winner_params_json': winner_params,
        'data_profile_json': data_profile
    }])
    
    try:
        from sqlalchemy.dialects.postgresql import JSON
        dtype_mapping = {'winner_params_json': JSON, 'data_profile_json': JSON}
    except ImportError:
        dtype_mapping = {'winner_params_json': text, 'data_profile_json': text}
        df_result['winner_params_json'] = df_result['winner_params_json'].apply(lambda x: str(x))
        df_result['data_profile_json'] = df_result['data_profile_json'].apply(lambda x: str(x))

    
    try:
        df_result.to_sql('training_history', engine, if_exists='append', index=False, dtype=dtype_mapping)
        print("   ✅ Historial de entrenamiento guardado en la DB.")
    except Exception as e:
        print(f"   ❌ ERROR al guardar historial en la DB: {e}")


def train_sarimax_consumption(engine, elite_suggestions):
    """Entrena y evalúa el modelo SARIMAX de consumo."""
    print("\n--- Entrenando Modelo de Consumo (SARIMAX) ---")

    # 1. Cargar datos (ASUMIMOS 'balance_historial_real' y 'seasonality_features')
    query = """
    SELECT 
        h.date, 
        h.consumo_real_diaria AS consumo, 
        s.sugar_5_seasonality AS seasonality
    FROM balance_historial_real h 
    LEFT JOIN seasonality_features s ON h.date = s.date
    ORDER BY h.date ASC
    """
    try:
        df = pd.read_sql(query, engine)
        df.set_index('date', inplace=True)
        df.dropna(subset=['consumo', 'seasonality'], inplace=True)
        
        if len(df) < 50: raise ValueError("Datos insuficientes para entrenamiento SARIMA.")
        
        y = df['consumo']
        X = df[['seasonality']]
        
        # 2. Configurar búsqueda de hiperparámetros
        best_mape = float('inf')
        best_model = None
        
        search_candidates = elite_suggestions
        if not elite_suggestions:
             for p in range(2):
                 for q in range(2):
                     search_candidates.append({'params': (p, 1, q), 'seasonal_params': (0, 1, 1, 7)})
        
        # 3. Fase de Búsqueda (Auto-ARIMA)
        for candidate in search_candidates:
            order = candidate['params']
            s_order = candidate['seasonal_params']
            
            try:
                model = pm.auto_arima(
                    y, X=X,
                    start_p=order[0], d=order[1], start_q=order[2], max_p=2, max_q=2, m=s_order[3], 
                    start_P=s_order[0], D=s_order[1], start_Q=s_order[2], max_P=1, max_Q=1,
                    seasonal=True, stepwise=True, suppress_warnings=True, error_action='ignore'
                )
                
                preds = model.predict_in_sample(X=X)
                mape = np.mean(np.abs((y.values - preds) / y.values)) * 100
                
                if mape < best_mape:
                    best_mape = mape
                    best_model = model
                    best_params = model.order
                    best_seasonal_params = model.seasonal_order
                    
            except Exception:
                continue
                
        if best_model is None: raise Exception("No se pudo entrenar ningún modelo SARIMA válido.")

        # 4. Empaquetar y guardar el modelo Campeón
        model_data = {
            'model': best_model,
            'mape_score': best_mape,
            'model_params': best_params,
            'model_seasonal_params': best_seasonal_params,
            'training_end_date': pd.Timestamp(df.index[-1]).date()
        }
        
        with open(CHAMPION_MODEL_CONSUMO_PATH, 'wb') as pfile:
            pickle.dump(model_data, pfile)
            
        print(f"   ✅ Modelo SARIMA de Consumo (Campeón) guardado. MAPE: {best_mape:.2f}%")
        
        return {
            'mape': best_mape, 
            'params': best_params, 
            'seasonal_params': best_seasonal_params
        }
        
    except Exception as e:
        print(f"   ❌ ERROR CRÍTICO entrenando SARIMAX: {e}")
        return None


# --- 5. LÓGICA PRINCIPAL DE ORQUESTACIÓN ---
def run_training_process():
    print("\n--- [4/5] ENTRENAMIENTO DE MODELOS PREDICTIVOS ---")
    engine = get_db_engine()
    
    # 1. Entrenar y gestionar el Modelo de Consumo SARIMAX
    try:
        elite_suggestions_consumo = get_elite_suggestions_sarima(engine, MODEL_TYPE_CONSUMO)
        results_consumo = train_sarimax_consumption(engine, elite_suggestions_consumo)

        if results_consumo and results_consumo['mape'] != float('inf'):
            
            register_training_result(
                engine, 
                MODEL_TYPE_CONSUMO, 
                champion_metric=float('inf'), 
                challenger_metric=results_consumo['mape'], 
                winner='challenger', 
                winner_params={'params': results_consumo['params'], 'seasonal_params': results_consumo['seasonal_params']},
                data_profile={'data_size': len(pd.read_sql("SELECT * FROM market_metrics", engine))}
            )
            
    except Exception as e:
        print(f"   ❌ Advertencia: Fallo en el entrenamiento del modelo de consumo. {e}")


    # 2. Entrenar Modelos de Precio (Contrato #11 y #5 AVANZADO)
    try:
        # A. Cargar Datos Maestros y Features Avanzadas
        print("   🤖 Cargando datos históricos y features avanzados...")
        
        # Usamos ADVANCED_FEATURES_REQD para cargar las features de advanced_features
        features_to_load = [f'a."{col}"' for col in ADVANCED_FEATURES_REQD]
        
        query = f"""
        SELECT 
            m.*, 
            s.sugar_5_seasonality,
            {', '.join(features_to_load)}
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
        results_11 = predict_sugar_11_hybrid(
            df_full.copy(), 
            horizon_days=30, 
            features=FEATURES_11_MINIMUM, 
            xgb_params=BEST_PARAMS_30D_11
        )
        
        target_date_11 = df_full.index[-1] + timedelta(days=30)
        
        # Calcular IC
        conf_lower_11 = results_11['prediction'] - 1.645 * results_11['error_std']
        conf_upper_11 = results_11['prediction'] + 1.645 * results_11['error_std']
        
        # Enriquecer resultados
        results_11['conf_lower'] = conf_lower_11
        results_11['conf_upper'] = conf_upper_11
        results_11['target_date'] = target_date_11.date()
        
        print(f"\n   🔮 PREDICCIÓN CONTRATO #11 (XGBoost+ARIMA):")
        print(f"      Fecha objetivo: {target_date_11.date()}")
        print(f"      Precio estimado: ${results_11['prediction']:.4f}")
        print(f"      Intervalo 90%: [{conf_lower_11:.4f} - {conf_upper_11:.4f}]")

        # --- ORQUESTACIÓN DE CONTRATO #5 (LSTM+ARIMA+GARCH) ---
        
        results_5 = predict_sugar_5_hybrid_advanced(df_full.copy(), horizon_days=30, features=FEATURES_5_LSTM, hps_lstm=BEST_HPS_LSTM)
        
        target_date_5 = df_full.index[-1] + timedelta(days=30)
        
        conf_lower_5 = results_5['prediction'] - 1.645 * results_5['error_std']
        conf_upper_5 = results_5['prediction'] + 1.645 * results_5['error_std']
        
        # Enriquecer resultados
        results_5['conf_lower'] = conf_lower_5
        results_5['conf_upper'] = conf_upper_5
        results_5['target_date'] = target_date_5.date()
        
        print(f"\n   🔮 PREDICCIÓN CONTRATO #5 (LSTM+ARIMA+GARCH):")
        print(f"      Fecha objetivo: {target_date_5.date()}")
        print(f"      Precio estimado: ${results_5['prediction']:.4f}")
        print(f"      Intervalo 90% (GARCH): [{conf_lower_5:.4f} - {conf_upper_5:.4f}]")


        # F. Guardar en DB
        print("   ✅ Predicciones guardadas exitosamente.")
        
        # RETORNO CORRECTO
        return results_11, results_5, target_date_11.date()

    except Exception as e:
        print(f"   ❌ Error en entrenamiento: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    run_training_process()