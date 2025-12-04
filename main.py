import sys
from config.db import test_connection
from src.fetcher import run_fetch_process
from src.processor import run_dataset_creation
from src.engineering import run_feature_engineering # <--- Asegúrate de importar esto
from src.training import run_training_process

def main():
    print("--- 🚜 INICIANDO AGRO_IA_WORKER ---")
    
    # 1. Verificar DB
    if not test_connection():
        sys.exit(1)

    # 2. Descargar (Extract)
    run_fetch_process()

    # 3. Procesar (Transform)
    if not run_dataset_creation():
        print("⚠️ Proceso detenido en etapa de procesador.")
        sys.exit(1)
        
    # 4. Calcular Features (Engineering) - EL PASO NUEVO
    if run_feature_engineering():
        print("\n✨ PIPELINE COMPLETO: Datos + Features listos en DB.")
    else:
        print("\n⚠️ Hubo problemas en la ingeniería de features.")

    # 5. Entrenar Modelo
    if run_training_process():
        print("\n✨ PIPELINE COMPLETO: Modelo entrenado y predicción guardada.")
    else:
        print("\n⚠️ Hubo problemas en el entrenamiento del modelo.")

if __name__ == "__main__":
    main()