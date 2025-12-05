# --- src/reporting.py ---
import pandas as pd
import numpy as np
import sys
from sqlalchemy import text
from datetime import datetime, date # Importar date
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)
from config.db import get_db_engine 

def save_predictions_to_db(engine, predictions_list: list, pricing_results: tuple):
    """
    Guarda la lista de predicciones (1-7, 30 días) en final_predictions.
    """
    if not predictions_list: return False
    
    # Datos de Pricing (Son constantes para el día de análisis)
    # pricing_results es (prd_results, comparacion)
    prd_data = pricing_results[0]
    decision_data = pricing_results[1]
    
    rows_to_insert = []
    
    for pred in predictions_list:
        row = {
            'date': pred['date'],
            
            # Modelo C11
            'c11_predicted_price': pred['c11_price'],
            'c11_confidence_lower': pred['c11_lower'],
            'c11_confidence_upper': pred['c11_upper'],
            
            # Modelo C5
            'c5_predicted_price': pred['c5_price'],
            'c5_confidence_lower': pred['c5_lower'],
            'c5_confidence_upper': pred['c5_upper'],
            
            # Datos de PRD (Se repiten para dar contexto a cada fila)
            'prd_usd_tn': prd_data['prd_tn'],
            'prd_delta_s_pct': prd_data['delta_s_combinado'],
            'export_decision_ars_50kg': decision_data['diferencial_ars_50kg'],
            'decision_text': decision_data['recomendacion'],
            
            'calculated_at': datetime.now()
        }
        rows_to_insert.append(row)
    
    df_final = pd.DataFrame(rows_to_insert)
    
    try:
        # Borrar predicciones anteriores para estas fechas específicas para evitar duplicados
        fechas = "', '".join([d['date'].strftime('%Y-%m-%d') for d in predictions_list])
        with engine.connect() as con:
            con.execute(text(f"DELETE FROM final_predictions WHERE date IN ('{fechas}')"))
            con.commit()
            
        df_final.to_sql('final_predictions', engine, if_exists='append', index=False)
        print(f"   ✅ Se guardaron {len(df_final)} filas de predicción (Horizontes 1-7, 30).")
        return True
    except Exception as e:
        print(f"   ❌ Error guardando predicciones: {e}")
        import traceback
        traceback.print_exc()
        return False