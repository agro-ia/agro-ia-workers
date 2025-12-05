"""Crear tabla prd_plan_diario (Objetivos de Stock y Producción)

Revision ID: b544bcb18622
Revises: 810404a0d3a3
Create Date: 2025-12-04 17:18:10.297669

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b544bcb18622'
down_revision: Union[str, Sequence[str], None] = '810404a0d3a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'prd_plan_diario',
        sa.Column('plan_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('date', sa.Date(), nullable=False, unique=True),
        
        # Objetivos Diarios
        sa.Column('consumo_diario_objetivo', sa.Numeric(10, 2), nullable=True),
        sa.Column('produccion_diaria_objetivo', sa.Numeric(10, 2), nullable=True),
        sa.Column('stock_diario_objetivo', sa.Numeric(10, 2), nullable=True),
        
        # Referencia Estratégica (Mensual)
        sa.Column('stock_estrategico_mensual', sa.Numeric(10, 2), nullable=True),
        
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )
    op.create_index('idx_plan_date', 'prd_plan_diario', ['date'])

def downgrade() -> None:
    op.drop_index('idx_plan_date', table_name='prd_plan_diario')
    op.drop_table('prd_plan_diario')