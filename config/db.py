import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from urllib.parse import quote_plus

# Cargar variables de entorno
load_dotenv()

def get_db_engine():
    """
    Crea y devuelve un motor SQLAlchemy usando las credenciales del .env
    """
    try:
        # Usamos .strip() para eliminar espacios en blanco accidentales al final o inicio
        user = os.getenv('DB_USER', '').strip()
        password = os.getenv('DB_PASS', '').strip()
        host = os.getenv('DB_HOST', '').strip()
        port = os.getenv('DB_PORT', '').strip()
        db_name = os.getenv('DB_NAME', '').strip()

        if not all([user, password, host, port, db_name]):
            raise ValueError("Faltan variables de entorno para la base de datos.")

        # Codificar usuario y contraseña (buena práctica siempre)
        encoded_user = quote_plus(user)
        encoded_password = quote_plus(password)

        connection_str = f'postgresql+psycopg2://{encoded_user}:{encoded_password}@{host}:{port}/{db_name}'
        
        # print(f"DEBUG: Conectando a {host}...") # Descomentar si falla de nuevo
        
        engine = create_engine(connection_str)
        return engine
    except Exception as e:
        print(f"❌ Error configurando el motor de DB: {e}")
        sys.exit(1)

def test_connection():
    engine = get_db_engine()
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print(f"✅ Conexión a PostgreSQL exitosa ({result.scalar()})")
        return True
    except Exception as e:
        print(f"❌ Error conectando a PostgreSQL: {e}")
        return False