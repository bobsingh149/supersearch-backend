"""remove_rate_limiter_from_schema_except_public

Revision ID: 6db85ca12673
Revises: 7e5ebfbfcd6e
Create Date: 2025-05-06 23:26:41.733578

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6db85ca12673'
down_revision: Union[str, None] = '7e5ebfbfcd6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMAS = ['demo_movies', 'demo_ecommerce', 'test', 'development', 'staging', 'production']

def upgrade() -> None:
    for schema in SCHEMAS:
        op.execute(f"""
            DROP TRIGGER IF EXISTS update_rate_limits_updated_at ON {schema}.rate_limits;
            DROP INDEX IF EXISTS idx_rate_limits_ip_address;
            DROP TABLE IF EXISTS {schema}.rate_limits;    
        """)



def downgrade() -> None:
    pass

    
