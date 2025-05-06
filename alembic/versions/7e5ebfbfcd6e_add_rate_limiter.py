"""add_rate_limiter

Revision ID: 7e5ebfbfcd6e
Revises: 1e11d6d50067
Create Date: 2025-05-06 21:33:59.796670

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e5ebfbfcd6e'
down_revision: Union[str, None] = '1e11d6d50067'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    schema = 'public'
    # Create the rate_limits table
    op.execute(f"""
       CREATE TABLE IF NOT EXISTS {schema}.rate_limits (
           ip_address TEXT PRIMARY KEY,
           request_count INTEGER NOT NULL DEFAULT 0,
           last_request_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
           created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
           updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
       );

       -- Create trigger for rate_limits updated_at
       CREATE TRIGGER update_rate_limits_updated_at
           BEFORE UPDATE ON {schema}.rate_limits
           FOR EACH ROW
           EXECUTE FUNCTION {schema}.update_updated_at_column();

       -- Create index on ip_address for faster lookups
       CREATE INDEX IF NOT EXISTS idx_rate_limits_ip_address 
           ON {schema}.rate_limits(ip_address);
       """)


def downgrade() -> None:

    schema = 'public'
    op.execute(f"""
        DROP TRIGGER IF EXISTS update_rate_limits_updated_at ON {schema}.rate_limits;
        DROP INDEX IF EXISTS idx_rate_limits_ip_address;
        DROP TABLE IF EXISTS {schema}.rate_limits;
    """)

    

