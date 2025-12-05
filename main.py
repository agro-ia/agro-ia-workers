# --- src/main.py (Versión Final Corregida) ---

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
    
    if not test_connection(): sys.exit(1)
    if not run_balance_seeder(): sys.exit(1)
    run_fetch_process()
    if not run_dataset_creation(): sys.exit(1)
    if not run_feature_engineering(): sys.exit(1)    

    # 6. Entrenar Modelo (Retorna una LISTA de predicciones)
    predictions_list = run_training_process()
    
    if predictions_list is None:
        print("\n⚠️ Hubo problemas en el entrenamiento del modelo.")
        sys.exit(1)
    
    # 7. CAPA DE PRECIOS Y DECISIONES
    pricing_results = run_pricing_and_decision()
    
    if pricing_results is None:
        print("\n⚠️ Hubo problemas en el cálculo del PRD/Pricing.")
        sys.exit(1)
        
    # 8. GUARDADO FINAL
    # Pasamos la LISTA DIRECTAMENTE, sin desempaquetar
    engine = get_db_engine()
    
    if save_predictions_to_db(engine, predictions_list, pricing_results):
        print("\n✨ PIPELINE PRINCIPAL COMPLETADO. Todos los resultados guardados.")
    else:
        print("\n⚠️ Fallo en la etapa de guardado final.")

    print("\n✨ FIN DEL PROCESO.")

if __name__ == "__main__":
    main()