"""Remove unique constraint on date in final_predictions

Revision ID: 51f70ed6a369
Revises: fab54a1c8f0d
Create Date: 2025-12-05 14:06:31.210794

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '51f70ed6a369'
down_revision: Union[str, Sequence[str], None] = 'fab54a1c8f0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('final_predictions_date_key', 'final_predictions', type_='unique')
    op.drop_index('final_predictions_date_key', table_name='final_predictions')

def downgrade() -> None:
    op.create_constraint('final_predictions_date_key', 'final_predictions', ['date'], unique=True)
    op.create_index('final_predictions_date_key', 'final_predictions', ['date'], unique=True)