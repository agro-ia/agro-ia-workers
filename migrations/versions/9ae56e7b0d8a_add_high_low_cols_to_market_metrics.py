"""add high low cols to market_metrics

Revision ID: 9ae56e7b0d8a
Revises: c3e86fd9a4d8
Create Date: 2025-11-28 17:34:34.368717

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9ae56e7b0d8a'
down_revision: Union[str, Sequence[str], None] = 'c3e86fd9a4d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Agregamos columnas High y Low para los activos que las tienen en el CSV
    
    # Sugar #11
    op.add_column('market_metrics', sa.Column('sugar_11_high', sa.Numeric(10, 4)))
    op.add_column('market_metrics', sa.Column('sugar_11_low', sa.Numeric(10, 4)))
    
    # Sugar #5
    op.add_column('market_metrics', sa.Column('sugar_5_high', sa.Numeric(10, 4)))
    op.add_column('market_metrics', sa.Column('sugar_5_low', sa.Numeric(10, 4)))
    
    # Petróleo WTI
    op.add_column('market_metrics', sa.Column('oil_wti_high', sa.Numeric(10, 4)))
    op.add_column('market_metrics', sa.Column('oil_wti_low', sa.Numeric(10, 4)))
    
    # Petróleo Brent
    op.add_column('market_metrics', sa.Column('oil_brent_high', sa.Numeric(10, 4)))
    op.add_column('market_metrics', sa.Column('oil_brent_low', sa.Numeric(10, 4)))
    
    # Etanol
    op.add_column('market_metrics', sa.Column('ethanol_high', sa.Numeric(10, 4)))
    op.add_column('market_metrics', sa.Column('ethanol_low', sa.Numeric(10, 4)))
    
    # Gas Natural HH
    op.add_column('market_metrics', sa.Column('natgas_hh_high', sa.Numeric(10, 4)))
    op.add_column('market_metrics', sa.Column('natgas_hh_low', sa.Numeric(10, 4)))
    
    # Gas Natural TTF
    op.add_column('market_metrics', sa.Column('natgas_ttf_high', sa.Numeric(10, 4)))
    op.add_column('market_metrics', sa.Column('natgas_ttf_low', sa.Numeric(10, 4)))
    
    # DXY (Índice Dólar)
    op.add_column('market_metrics', sa.Column('fx_dxy_high', sa.Numeric(10, 4)))
    op.add_column('market_metrics', sa.Column('fx_dxy_low', sa.Numeric(10, 4)))

    # Agregamos DX Future que estaba en el CSV pero no en nuestra tabla original
    op.add_column('market_metrics', sa.Column('fx_dx_future', sa.Numeric(10, 4)))
    op.add_column('market_metrics', sa.Column('fx_dx_future_high', sa.Numeric(10, 4)))
    op.add_column('market_metrics', sa.Column('fx_dx_future_low', sa.Numeric(10, 4)))


def downgrade() -> None:
    # En caso de revertir, borramos las columnas
    op.drop_column('market_metrics', 'sugar_11_high')
    op.drop_column('market_metrics', 'sugar_11_low')
    op.drop_column('market_metrics', 'sugar_5_high')
    op.drop_column('market_metrics', 'sugar_5_low')
    op.drop_column('market_metrics', 'oil_wti_high')
    op.drop_column('market_metrics', 'oil_wti_low')
    op.drop_column('market_metrics', 'oil_brent_high')
    op.drop_column('market_metrics', 'oil_brent_low')
    op.drop_column('market_metrics', 'ethanol_high')
    op.drop_column('market_metrics', 'ethanol_low')
    op.drop_column('market_metrics', 'natgas_hh_high')
    op.drop_column('market_metrics', 'natgas_hh_low')
    op.drop_column('market_metrics', 'natgas_ttf_high')
    op.drop_column('market_metrics', 'natgas_ttf_low')
    op.drop_column('market_metrics', 'fx_dxy_high')
    op.drop_column('market_metrics', 'fx_dxy_low')
    op.drop_column('market_metrics', 'fx_dx_future')
    op.drop_column('market_metrics', 'fx_dx_future_high')
    op.drop_column('market_metrics', 'fx_dx_future_low')