"""add_high_low_columns

Revision ID: 771e97d2056c
Revises: 9ae56e7b0d8a
Create Date: 2025-11-28 17:59:27.262209

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '771e97d2056c'
down_revision: Union[str, Sequence[str], None] = '9ae56e7b0d8a'
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