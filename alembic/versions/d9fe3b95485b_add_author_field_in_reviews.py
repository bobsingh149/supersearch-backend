"""add_author_field_in_reviews

Revision ID: d9fe3b95485b
Revises: 2f7095ec1f6c
Create Date: 2025-05-03 12:35:40.204589

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Schema names from the original migration
SCHEMAS = ['demo_movies', 'test', 'development', 'staging', 'production']

# revision identifiers, used by Alembic.
revision: str = 'd9fe3b95485b'
down_revision: Union[str, None] = '2f7095ec1f6c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for schema in SCHEMAS:
        op.execute(f"""
        ALTER TABLE {schema}.reviews 
        ADD COLUMN IF NOT EXISTS author VARCHAR(255);
        """)


def downgrade() -> None:
    for schema in SCHEMAS:
        op.execute(f"""
        ALTER TABLE {schema}.reviews 
        DROP COLUMN IF EXISTS author;
        """)
