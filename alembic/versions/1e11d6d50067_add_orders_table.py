"""add_orders_table

Revision ID: 1e11d6d50067
Revises: d9fe3b95485b
Create Date: 2025-05-04 20:17:43.404827

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e11d6d50067'
down_revision: Union[str, None] = 'd9fe3b95485b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMAS = ['demo_movies', 'test', 'development', 'staging', 'production']


def upgrade() -> None:
    for schema in SCHEMAS:
        # Create the orders table
        op.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.orders (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id TEXT NOT NULL,
            status TEXT NOT NULL,
            total_amount DECIMAL(10, 2) NOT NULL,
            items JSONB NOT NULL,
            shipping_address JSONB,
            billing_address JSONB,
            payment_info JSONB,
            tracking_number TEXT,
            expected_shipping_date TIMESTAMP WITH TIME ZONE,
            notes TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        -- Create trigger for orders updated_at
        CREATE TRIGGER update_orders_updated_at
            BEFORE UPDATE ON {schema}.orders
            FOR EACH ROW
            EXECUTE FUNCTION {schema}.update_updated_at_column();
            
        -- Create indexes for common query patterns
        CREATE INDEX IF NOT EXISTS idx_orders_user_id 
            ON {schema}.orders(user_id);
        CREATE INDEX IF NOT EXISTS idx_orders_status 
            ON {schema}.orders(status);
        CREATE INDEX IF NOT EXISTS idx_orders_created_at 
            ON {schema}.orders(created_at DESC);
        """)


def downgrade() -> None:
    for schema in SCHEMAS:
        op.execute(f"DROP TABLE IF EXISTS {schema}.orders CASCADE;")
