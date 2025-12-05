"""Crear tabla final_predictions para resultados consolidados de modelos y PRD

Revision ID: 38a614c2d4d8
Revises: b544bcb18622
Create Date: 2025-12-04 17:48:35.851136

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '38a614c2d4d8'
down_revision: Union[str, Sequence[str], None] = 'b544bcb18622'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'final_predictions',
        sa.Column('prediction_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('date', sa.Date(), nullable=False, unique=True), # Fecha objetivo de la predicción (ej: 2026-01-10)
        
        # --- Resultados del Contrato #11 (XGBoost + ARIMA) ---
        sa.Column('c11_predicted_price', sa.Numeric(10, 4), nullable=True),
        sa.Column('c11_confidence_lower', sa.Numeric(10, 4), nullable=True),
        sa.Column('c11_confidence_upper', sa.Numeric(10, 4), nullable=True),
        
        # --- Resultados del Contrato #5 (LSTM + ARIMA + GARCH) ---
        sa.Column('c5_predicted_price', sa.Numeric(10, 4), nullable=True),
        sa.Column('c5_confidence_lower', sa.Numeric(10, 4), nullable=True),
        sa.Column('c5_confidence_upper', sa.Numeric(10, 4), nullable=True), # Usa GARCH Volatility
        
        # --- Resultados del PRD (Precio de Referencia Dinámico) ---
        sa.Column('prd_usd_tn', sa.Numeric(10, 4), nullable=True),
        sa.Column('prd_delta_s_pct', sa.Numeric(10, 4), nullable=True),
        
        # --- Decisión Estratégica (Comparador de Mercados) ---
        sa.Column('export_decision_ars_50kg', sa.Numeric(10, 4), nullable=True), # Diferencial de rentabilidad
        sa.Column('decision_text', sa.String(length=50), nullable=True), # Ej: "EXPORTAR"
        
        sa.Column('calculated_at', sa.DateTime(), server_default=sa.func.now())
    )
    op.create_index('idx_pred_date', 'final_predictions', ['date'])

def downgrade() -> None:
    op.drop_index('idx_pred_date', table_name='final_predictions')
    op.drop_table('final_predictions')