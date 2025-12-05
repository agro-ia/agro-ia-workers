"""create training history

Revision ID: d4b4b74aae75
Revises: 513211c12472
Create Date: 2025-12-04 16:22:58.500865

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4b4b74aae75'
down_revision: Union[str, Sequence[str], None] = '513211c12472'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'training_history',
        sa.Column('history_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('model_type', sa.String(50), nullable=False), # Ej: 'SARIMAX_CONSUMO', 'XGBOOST_11'
        sa.Column('champion_metric', sa.Numeric(10, 4), nullable=True), # MAPE del Campeón
        sa.Column('challenger_metric', sa.Numeric(10, 4), nullable=True), # MAPE del Contendiente
        sa.Column('winner', sa.String(20), nullable=False), # 'champion' o 'challenger'
        sa.Column('winner_params_json', sa.JSON(), nullable=True), # Parámetros del ganador
        sa.Column('data_profile_json', sa.JSON(), nullable=True), # Perfil de datos usado
    )

def downgrade() -> None:
    op.drop_table('training_history')