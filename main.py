# --- src/main.py (Versión Corregida Final) ---

from config.db import get_db_engine
from src.pricing import run_pricing_and_decision
from config.db import test_connection
import sys
from src.fetcher import run_fetch_process
from src.processor import run_dataset_creation
from src.engineering import run_feature_engineering 
from src.training import run_training_process
from src.seeder_balance_real import run_balance_seeder
from src.reporting import save_predictions_to_db


def main():
    print("--- 🚜 INICIANDO AGRO_IA_WORKER ---")
    
    # 1. Verificar DB
    if not test_connection():
        sys.exit(1)

    # 2. Sembrar Datos de Balance Real
    # if not run_balance_seeder():
    #     print("⚠️ Proceso detenido: Fallo al sembrar datos de balance real.")
    #     sys.exit(1)
        
    # 3. Descargar (Extract)
    # run_fetch_process()

    # 4. Procesar (Transform)
    if not run_dataset_creation():
        print("⚠️ Proceso detenido en etapa de procesador.")
        sys.exit(1)
        
    # 5. Calcular Features (Engineering)
    if not run_feature_engineering():
        print("\n⚠️ Hubo problemas en la ingeniería de features.")
        sys.exit(1)

    # 6. Entrenar Modelo (Captura de Resultados ML)
    # run_training_process debe devolver (results_11, results_5)
    training_results = run_training_process()
    
    if training_results is None:
        print("\n⚠️ Hubo problemas en el entrenamiento del modelo.")
        sys.exit(1)
    
    # *** CORRECCIÓN APLICADA AQUÍ ***
    results_c11, results_5, target_date = training_results 
    results_c5 = results_5
    
    # 7. CAPA DE PRECIOS Y DECISIONES (PRD y Comparación)
    # run_pricing_and_decision devuelve (prd_results, comparacion)
    pricing_results = run_pricing_and_decision()
    
    if pricing_results is None:
        print("\n⚠️ Hubo problemas en el cálculo del PRD/Pricing.")
        sys.exit(1)
        
    # 8. GUARDADO FINAL Y REPORTE
    engine = get_db_engine()
        
    if save_predictions_to_db(engine, results_c11, results_c5, pricing_results, target_date):
        print("\n✨ PIPELINE PRINCIPAL COMPLETADO. Todos los resultados guardados.")
    else:
        print("\n⚠️ Fallo en la etapa de guardado final.")

    print("\n✨ PIPELINE PRINCIPAL COMPLETADO. Modelos entrenados y guardados.")

if __name__ == "__main__":
    main()