import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# --- MODIFICACIÓN CRÍTICA 1: Configuración de Rutas ---
# Añadir la raíz del proyecto al path para que podamos importar 'config.db'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- MODIFICACIÓN CRÍTICA 2: Importar el motor de DB del proyecto ---
from config.db import get_db_engine
# Importar la base declarativa donde se definen tus modelos
# IMPORTANTE: Cambia 'from models import Base' si tus modelos están en otra parte
from sqlalchemy.ext.declarative import declarative_base
target_metadata = declarative_base().metadata # Ajustar según donde tengas tu Base

# Este es el objeto de configuración de Alembic
config = context.config

# Interpretamos el archivo de configuración, que a menudo proporciona
# un controlador de registro.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- FIN DE MODIFICACIONES DE IMPORTS Y METADATA ---

def run_migrations_offline():
    """Run migrations in 'offline' mode. (Sin cambios)"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode. (Conexión crítica)"""
    
    # --- MODIFICACIÓN CRÍTICA 3: Usar el motor de DB del proyecto ---
    # Alembic ya no intentará leer la URL de conexión del alembic.ini, 
    # sino que usará la conexión establecida por tu worker.
    connectable = get_db_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()