"""add_suggested_questions

Revision ID: 2f7095ec1f6c
Revises: 43c8c71d642c
Create Date: 2025-05-01 21:56:37.819923

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Schema names from the original migration
SCHEMAS = ['demo_movies', 'demo_ecommerce', 'test', 'development', 'staging', 'production']

# revision identifiers, used by Alembic.
revision: str = '2f7095ec1f6c'
down_revision: Union[str, None] = '43c8c71d642c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for schema in SCHEMAS:
        op.execute(f"""
        ALTER TABLE {schema}.products 
        ADD COLUMN IF NOT EXISTS suggested_questions JSONB;
        """)


def downgrade() -> None:
    for schema in SCHEMAS:
        op.execute(f"""
        ALTER TABLE {schema}.products 
        DROP COLUMN IF EXISTS suggested_questions;
        """)
