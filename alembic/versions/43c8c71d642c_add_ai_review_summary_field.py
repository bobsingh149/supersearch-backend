"""add_ai_review_summary_field

Revision ID: 43c8c71d642c
Revises: 7ece81796eab
Create Date: 2025-05-01 14:25:31.167205

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = '43c8c71d642c'
down_revision: Union[str, None] = '7ece81796eab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Schema names from the original migration
SCHEMAS = ['demo_movies', 'demo_ecommerce', 'test', 'development', 'staging', 'production']

def upgrade() -> None:
    # Add ai_summary JSONB column to products table in each schema
    for schema in SCHEMAS:
        op.execute(f"""
        ALTER TABLE {schema}.products 
        ADD COLUMN IF NOT EXISTS ai_summary JSONB;
        """)


def downgrade() -> None:
    # Remove ai_summary column from products table in each schema
    for schema in SCHEMAS:
        op.execute(f"""
        ALTER TABLE {schema}.products 
        DROP COLUMN IF EXISTS ai_summary;
        """)
