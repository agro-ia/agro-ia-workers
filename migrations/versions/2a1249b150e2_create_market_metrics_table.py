"""create market_metrics table

Revision ID: 2a1249b150e2
Revises: 1d8696794f34
Create Date: 2025-11-28 16:50:19.276378

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a1249b150e2'
down_revision: Union[str, Sequence[str], None] = '1d8696794f34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Esta es la tabla FINAL que consultará tu API y tus Modelos de IA
    op.create_table(
        'market_metrics',
        sa.Column('market_metric_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('date', sa.Date(), nullable=False, unique=True), # Fecha única (índice temporal)
        
        # --- Precios de Cierre (Close) de tus activos ---
        sa.Column('sugar_11', sa.Numeric(10, 4)),
        sa.Column('sugar_5', sa.Numeric(10, 4)),
        sa.Column('fx_ars_usd', sa.Numeric(10, 4)),
        sa.Column('fx_brl_usd', sa.Numeric(10, 4)),
        sa.Column('fx_dxy', sa.Numeric(10, 4)),
        sa.Column('oil_wti', sa.Numeric(10, 4)),
        sa.Column('oil_brent', sa.Numeric(10, 4)),
        sa.Column('natgas_hh', sa.Numeric(10, 4)),
        sa.Column('natgas_ttf', sa.Numeric(10, 4)),
        sa.Column('ethanol', sa.Numeric(10, 4)),
        
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now())
    )
    # Índice para búsquedas rápidas por fecha
    op.create_index('idx_metrics_date', 'market_metrics', ['date'])


def downgrade() -> None:
    op.drop_index('idx_metrics_date', table_name='market_metrics')
    op.drop_table('market_metrics')