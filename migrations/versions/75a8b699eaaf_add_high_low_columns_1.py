"""add_high_low_columns_1

Revision ID: 75a8b699eaaf
Revises: 771e97d2056c
Create Date: 2025-11-28 18:04:54.180828

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '75a8b699eaaf'
down_revision: Union[str, Sequence[str], None] = '771e97d2056c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Agregamos columnas High y Low para los activos clave
    columns = [
        'sugar_11', 'sugar_5', 'oil_wti', 'oil_brent', 
        'natgas_hh', 'fx_dxy', 'fx_dx_future'
    ]
    
    for col in columns:
        op.add_column('market_metrics', sa.Column(f'{col}_high', sa.Numeric(10, 4)))
        op.add_column('market_metrics', sa.Column(f'{col}_low', sa.Numeric(10, 4)))

def downgrade() -> None:
    columns = [
        'sugar_11', 'sugar_5', 'oil_wti', 'oil_brent', 
        'natgas_hh', 'fx_dxy', 'fx_dx_future'
    ]
    for col in columns:
        op.drop_column('market_metrics', f'{col}_high')
        op.drop_column('market_metrics', f'{col}_low')