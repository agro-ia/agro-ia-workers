"""Crear tablas balance_historial_real y training_history

Revision ID: 810404a0d3a3
Revises: d4b4b74aae75
Create Date: 2025-12-04 16:28:06.208237

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '810404a0d3a3'
down_revision: Union[str, Sequence[str], None] = 'd4b4b74aae75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. TABLA: balance_historial_real (Datos de Consumo y Producción) ---
    op.create_table(
        'balance_historial_real',
        sa.Column('history_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('date', sa.Date(), nullable=False, unique=True),
        
        # Consumo y Producción (para alimentar el PRD y el modelo SARIMAX)
        sa.Column('consumo_real_diaria', sa.Numeric(10, 2), nullable=True),
        sa.Column('produccion_real_diaria', sa.Numeric(10, 2), nullable=True),
        
        # Stock Inicial del Mes (Necesario para el cálculo de Stock Real Acumulado del PRD)
        sa.Column('stock_inicial_mes', sa.Numeric(10, 2), nullable=True),
        
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )
    op.create_index('idx_real_balance_date', 'balance_historial_real', ['date'])
    op.create_index('idx_training_type_ts', 'training_history', ['model_type', 'timestamp'])


def downgrade() -> None:
    # --- REVERTIR ---
    op.drop_index('idx_training_type_ts', table_name='training_history')
    op.drop_table('training_history')
    op.drop_index('idx_real_balance_date', table_name='balance_historial_real')
    op.drop_table('balance_historial_real')