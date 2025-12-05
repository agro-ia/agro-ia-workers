import pandas as pd
import numpy as np
import sys
from sqlalchemy import text
from datetime import datetime, date

# Brújula para imports
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

# La función de obtención del motor DB ya está disponible
from config.db import get_db_engine 


# --- src/reporting.py (Corrección) ---

def save_predictions_to_db(engine, results_c11: dict, results_c5: dict, pricing_results: tuple, target_date: date): # <--- AÑADIR target_date aquí
    """
    Consolida las predicciones de precios y el informe de PRD para guardarlos 
    en la tabla 'final_predictions'.
    """
    
    # Extraer datos de Pricing
    # pricing_results es una tupla: (prd_results, comparacion)
    prd_results = pricing_results[0]
    comparacion = pricing_results[1]
    
    prd_delta_s_pct = prd_results['delta_s_combinado']
    
    # Crear DataFrame
    df_pred = pd.DataFrame([{
        'date': target_date, # <--- Usar el argumento target_date pasado
        
        # Contrato #11
        'c11_predicted_price': results_c11['prediction'],
        'c11_confidence_lower': results_c11['prediction'] - 1.645 * results_c11['error_std'], # Recalcular aquí
        'c11_confidence_upper': results_c11['prediction'] + 1.645 * results_c11['error_std'],
        
        # Contrato #5
        'c5_predicted_price': results_c5['prediction'],
        'c5_confidence_lower': results_c5['prediction'] - 1.645 * results_c5['error_std'], # Recalcular aquí
        'c5_confidence_upper': results_c5['prediction'] + 1.645 * results_c5['error_std'],
        
        # PRD
        'prd_usd_tn': prd_results['prd_tn'],
        'prd_delta_s_pct': prd_delta_s_pct,
        
        # Decisión Estratégica
        'export_decision_ars_50kg': comparacion['diferencial_ars_50kg'],
        'decision_text': comparacion['recomendacion'],
        'calculated_at': datetime.now()
    }])
    
    # 2. Guardar en la Base de Datos
    try:
        # Primero borramos si ya existe la predicción para esa fecha (por la llave primaria)
        with engine.connect() as con:
            con.execute(text(f"DELETE FROM final_predictions WHERE date = '{target_date.strftime('%Y-%m-%d')}'"))
            con.commit()
            
        df_pred.to_sql('final_predictions', engine, if_exists='append', index=False)
        print("   ✅ Predicciones finales guardadas en 'final_predictions'.")
        return True
    except Exception as e:
        print(f"   ❌ ERROR al guardar predicciones finales: {e}")
        import traceback
        traceback.print_exc()
        return False