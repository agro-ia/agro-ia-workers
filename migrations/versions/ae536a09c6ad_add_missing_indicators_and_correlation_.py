"""Add missing indicators and correlation features to advanced_features

Revision ID: ae536a09c6ad
Revises: 5dd92ecf548f
Create Date: 2025-12-04 15:44:23.196823

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ae536a09c6ad'
down_revision: Union[str, Sequence[str], None] = '5dd92ecf548f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Indicadores Técnicos Faltantes
    op.add_column('advanced_features', sa.Column('s11_bollinger_upper', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('s11_bollinger_lower', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('s11_macd', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('s11_macd_hist', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('s11_atr', sa.Numeric(), nullable=True))
    
    # 2. Lags y MAs Faltantes
    op.add_column('advanced_features', sa.Column('s11_lag_60d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('s11_lag_90d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('s11_ma_7d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('s11_ma_90d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('oil_wti_lag_60d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('oil_wti_lag_90d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('ethanol_lag_30d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('ethanol_lag_60d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('ethanol_lag_90d', sa.Numeric(), nullable=True))
    
    # 3. Correlaciones y Spreads Faltantes
    op.add_column('advanced_features', sa.Column('spread_vol_30d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('corr_11_5_60d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('corr_11_5_90d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('corr_11_oil_30d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('corr_11_oil_60d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('corr_11_oil_90d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('corr_11_eth_30d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('corr_11_eth_60d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('corr_11_eth_90d', sa.Numeric(), nullable=True))
    # NOTA: Las columnas s11_lag_30d, spread_11_5, etc., ya existen desde la migración inicial.
    
def downgrade() -> None:
    pass