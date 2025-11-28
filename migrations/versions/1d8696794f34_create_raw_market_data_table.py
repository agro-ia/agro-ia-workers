"""create raw_market_data table

Revision ID: 1d8696794f34
Revises: 
Create Date: 2025-11-28 16:39:49.573924

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d8696794f34'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- CREAR TABLA ---
    op.create_table(
        'raw_market_data',
        sa.Column('raw_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('ticker', sa.String(length=50), nullable=False),
        sa.Column('open', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('high', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('low', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('close', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )
    
    # Crear un índice compuesto para búsquedas rápidas y evitar duplicados lógicos
    op.create_index('idx_ticker_date', 'raw_market_data', ['ticker', 'date'])


def downgrade() -> None:
    # --- BORRAR TABLA (Rollback) ---
    op.drop_index('idx_ticker_date', table_name='raw_market_data')
    op.drop_table('raw_market_data')