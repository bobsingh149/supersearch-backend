"""add reviews jsonb field to products

Revision ID: 7efd07744cd8
Revises: 6db85ca12673
Create Date: 2025-06-21 01:29:56.367107

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7efd07744cd8'
down_revision: Union[str, None] = '6db85ca12673'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMAS = ['demo_movies', 'test', 'development', 'staging', 'production']

def upgrade() -> None:
    for schema in SCHEMAS:
        # Add reviews column to products table
        op.execute(f"""
        ALTER TABLE {schema}.products 
        ADD COLUMN IF NOT EXISTS reviews JSONB;
        """)


def downgrade() -> None:
    for schema in SCHEMAS:
        # Remove reviews column from products table
        op.execute(f"""
        ALTER TABLE {schema}.products 
        DROP COLUMN IF EXISTS reviews;
        """)
