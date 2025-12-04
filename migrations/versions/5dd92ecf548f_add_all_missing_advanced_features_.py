"""Add all missing advanced features columns

Revision ID: 5dd92ecf548f
Revises: 9b661bde535a
Create Date: 2025-12-04 15:13:30.242768

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5dd92ecf548f'
down_revision: Union[str, Sequence[str], None] = '9b661bde535a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Features de Lag y MA (Faltan 60d, 90d, MAs adicionales) ---
    op.add_column('advanced_features', sa.Column('s11_lag_60d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('s11_lag_90d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('s11_ma_7d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('s11_ma_90d', sa.Numeric(), nullable=True))
    
    # --- Features de Indicadores y Volatilidad ---
    op.add_column('advanced_features', sa.Column('s11_rsi_14d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('s11_volatilidad_30d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('s11_atr', sa.Numeric(), nullable=True)) # ATR
    op.add_column('advanced_features', sa.Column('s11_macd', sa.Numeric(), nullable=True)) # MACD
    op.add_column('advanced_features', sa.Column('s11_macd_hist', sa.Numeric(), nullable=True)) # MACD Histograma
    
    # --- Features de Etanol y Oil (Faltan 60d, 90d y Etanol completo) ---
    op.add_column('advanced_features', sa.Column('oil_wti_lag_60d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('oil_wti_lag_90d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('ethanol_lag_30d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('ethanol_lag_60d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('ethanol_lag_90d', sa.Numeric(), nullable=True))

    # --- Features de Spread/Correlación (Faltan Correlaciones adicionales) ---
    op.add_column('advanced_features', sa.Column('spread_ma_30d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('ratio_11_5', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('spread_vol_30d', sa.Numeric(), nullable=True))
    
    # Correlaciones a 60d y 90d
    op.add_column('advanced_features', sa.Column('corr_11_5_60d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('corr_11_5_90d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('corr_11_oil_30d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('corr_11_oil_60d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('corr_11_oil_90d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('corr_11_eth_30d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('corr_11_eth_60d', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('corr_11_eth_90d', sa.Numeric(), nullable=True))

def downgrade() -> None:
    pass