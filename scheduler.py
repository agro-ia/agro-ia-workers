"""
Scheduler para ejecutar el worker de Agro IA una vez al día a las 00:00 (medianoche)
"""
import schedule
import time
from datetime import datetime
import subprocess
import sys

def run_worker():
    """Ejecuta el proceso principal del worker"""
    print(f"\n{'='*60}")
    print(f"🕐 Iniciando ejecución programada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    try:
        # Ejecutar main.py como subproceso
        result = subprocess.run(
            [sys.executable, "main.py"],
            cwd="/app",
            capture_output=False,
            text=True
        )
        
        if result.returncode == 0:
            print(f"\n✅ Ejecución completada exitosamente: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"\n❌ Ejecución falló con código: {result.returncode}")
            
    except Exception as e:
        print(f"\n❌ Error durante la ejecución: {str(e)}")
    
    print(f"\n{'='*60}")
    print(f"⏰ Próxima ejecución programada: mañana a las 00:00")
    print(f"{'='*60}\n")

def main():
    """Configura y ejecuta el scheduler"""
    print("🚀 Iniciando Scheduler de Agro IA Worker")
    print(f"📅 Fecha de inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("⏰ Programado para ejecutarse todos los días a las 00:00 (medianoche)\n")
    
    # Programar la tarea para las 00:00 todos los días
    schedule.every().day.at("00:00").do(run_worker)
    
    # Ejecutar inmediatamente al iniciar (opcional, comentar si no se desea)
    print("▶️  Ejecutando primera vez al iniciar el contenedor...")
    run_worker()
    
    # Loop infinito para mantener el scheduler corriendo
    print("\n⏳ Scheduler en espera de próxima ejecución...\n")
    while True:
        schedule.run_pending()
        time.sleep(60)  # Verificar cada minuto

if __name__ == "__main__":
    main()
