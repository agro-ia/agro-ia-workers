"""Add missing indicators and correlation features to advanced_features 1

Revision ID: 513211c12472
Revises: ae536a09c6ad
Create Date: 2025-12-04 15:47:40.428076

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '513211c12472'
down_revision: Union[str, Sequence[str], None] = 'ae536a09c6ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('advanced_features', sa.Column('s11_bollinger_upper', sa.Numeric(), nullable=True))
    op.add_column('advanced_features', sa.Column('s11_bollinger_lower', sa.Numeric(), nullable=True))
    
def downgrade() -> None:
    pass