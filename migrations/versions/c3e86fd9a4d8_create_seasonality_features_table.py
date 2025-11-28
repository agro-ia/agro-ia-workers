"""create seasonality_features table

Revision ID: c3e86fd9a4d8
Revises: 2a1249b150e2
Create Date: 2025-11-28 17:08:23.406465

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e86fd9a4d8'
down_revision: Union[str, Sequence[str], None] = '2a1249b150e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'seasonality_features',
        sa.Column('feature_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('date', sa.Date(), nullable=False, unique=True),
        
        # Aquí guardaremos el componente estacional calculado
        # (Qué tanto sube o baja el precio solo por la época del año)
        sa.Column('sugar_5_seasonality', sa.Numeric(10, 6)), 
        
        sa.Column('calculated_at', sa.DateTime(), server_default=sa.func.now())
    )
    op.create_index('idx_seasonality_date', 'seasonality_features', ['date'])


def downgrade() -> None:
    op.drop_index('idx_seasonality_date', table_name='seasonality_features')
    op.drop_table('seasonality_features')