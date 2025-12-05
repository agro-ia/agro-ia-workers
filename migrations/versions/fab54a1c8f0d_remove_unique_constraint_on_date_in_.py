"""Remove unique constraint on date in final_predictions

Revision ID: fab54a1c8f0d
Revises: 38a614c2d4d8
Create Date: 2025-12-05 14:00:25.750805

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fab54a1c8f0d'
down_revision: Union[str, Sequence[str], None] = '38a614c2d4d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Eliminar el índice único actual (el nombre puede variar, verifica en tu DB si falla)
    # Por defecto alembic lo llamó 'idx_pred_date' en la migración anterior
    op.drop_index('idx_pred_date', table_name='final_predictions')
    
    # 2. Crear un índice normal (NO único) para mantener la velocidad de búsqueda
    op.create_index('idx_pred_date', 'final_predictions', ['date'], unique=False)

def downgrade() -> None:
    # Revertir: Borrar índice normal y volver a crear el único
    op.drop_index('idx_pred_date', table_name='final_predictions')
    op.create_index('idx_pred_date', 'final_predictions', ['date'], unique=True)