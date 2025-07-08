"""create demo_ecommerce schema tables

Revision ID: eccb38ded9f5
Revises: 7efd07744cd8
Create Date: 2025-06-21 01:30:27.232354

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Import enums from model files
from app.models.settings import SettingKey
from app.models.sync_config import SyncSource
from app.models.sync_history import SyncStatus

# revision identifiers, used by Alembic.
revision: str = 'eccb38ded9f5'
down_revision: Union[str, None] = '7efd07744cd8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = 'demo_ecommerce'

def upgrade() -> None:
    # Convert enum values to strings and join them for SQL
    setting_keys = ", ".join([f"'{key.value}'" for key in SettingKey])
    sync_sources = ", ".join([f"'{source.value}'" for source in SyncSource])
    sync_statuses = ", ".join([f"'{status.value}'" for status in SyncStatus])
    
    # Create schema if it doesn't exist
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA};")

    # Create update_updated_at_column function for the schema
    op.execute(f"""
    CREATE OR REPLACE FUNCTION {SCHEMA}.update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ language 'plpgsql';
    """)

    # Create the products table
    op.execute(f"""
    CREATE TABLE IF NOT EXISTS {SCHEMA}.products (
        id TEXT PRIMARY KEY,
        title TEXT,
        text_embedding public.vector(768),
        image_embedding public.vector(768),
        searchable_content TEXT,
        image_url TEXT,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        custom_data JSONB,
        ai_generated_contents TEXT[] DEFAULT ARRAY[]::TEXT[],
        ai_summary JSONB,
        suggested_questions JSONB,
        reviews JSONB
    );

    -- Create trigger for updated_at
    CREATE TRIGGER update_products_updated_at
        BEFORE UPDATE ON {SCHEMA}.products
        FOR EACH ROW
        EXECUTE FUNCTION {SCHEMA}.update_updated_at_column();
    """)

    # Create the conversations table
    op.execute(f"""
    CREATE TABLE IF NOT EXISTS {SCHEMA}.conversations (
        conversation_id TEXT PRIMARY KEY,
        messages JSONB NOT NULL DEFAULT '[]'::jsonb,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    -- Create trigger for updated_at
    CREATE TRIGGER update_conversations_updated_at
        BEFORE UPDATE ON {SCHEMA}.conversations
        FOR EACH ROW
        EXECUTE FUNCTION {SCHEMA}.update_updated_at_column();

    -- Create index on conversation_id for faster lookups
    CREATE INDEX IF NOT EXISTS idx_conversations_id 
        ON {SCHEMA}.conversations(conversation_id);
    """)

    # Create the settings table
    op.execute(f"""
    CREATE TABLE IF NOT EXISTS {SCHEMA}.settings (
        key TEXT PRIMARY KEY,
        title TEXT,
        description TEXT,
        value JSONB,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT settings_key_check CHECK (key IN ({setting_keys}))
    );

    -- Create trigger for settings updated_at
    CREATE TRIGGER update_settings_updated_at
        BEFORE UPDATE ON {SCHEMA}.settings
        FOR EACH ROW
        EXECUTE FUNCTION {SCHEMA}.update_updated_at_column();
    """)

    # Create the sync_history table
    op.execute(f"""
    CREATE TABLE IF NOT EXISTS {SCHEMA}.sync_history (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        source TEXT NOT NULL,
        status TEXT NOT NULL,
        start_time TIMESTAMP WITH TIME ZONE NOT NULL,
        end_time TIMESTAMP WITH TIME ZONE,
        records_processed INTEGER,
        next_run TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT sync_history_source_check CHECK (source IN ({sync_sources})),
        CONSTRAINT sync_history_status_check CHECK (status IN ({sync_statuses}))
    );

    -- Create trigger for sync_history updated_at
    CREATE TRIGGER update_sync_history_updated_at
        BEFORE UPDATE ON {SCHEMA}.sync_history
        FOR EACH ROW
        EXECUTE FUNCTION {SCHEMA}.update_updated_at_column();
        
    -- Create index on created_at for sync_history to improve sorting performance
    CREATE INDEX IF NOT EXISTS sync_history_created_at_idx ON {SCHEMA}.sync_history (created_at DESC);
    """)
    
    # Create the rate_limits table
    op.execute(f"""
    CREATE TABLE IF NOT EXISTS {SCHEMA}.rate_limits (
        ip_address TEXT PRIMARY KEY,
        request_count INTEGER NOT NULL DEFAULT 0,
        last_request_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    -- Create trigger for rate_limits updated_at
    CREATE TRIGGER update_rate_limits_updated_at
        BEFORE UPDATE ON {SCHEMA}.rate_limits
        FOR EACH ROW
        EXECUTE FUNCTION {SCHEMA}.update_updated_at_column();
        
    -- Create index on ip_address for faster lookups
    CREATE INDEX IF NOT EXISTS idx_rate_limits_ip_address 
        ON {SCHEMA}.rate_limits(ip_address);
    """)

    # Create the reviews table
    op.execute(f"""
    CREATE TABLE IF NOT EXISTS {SCHEMA}.reviews (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        content TEXT NOT NULL,
        author TEXT,
        product_id TEXT NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_product
            FOREIGN KEY(product_id)
            REFERENCES {SCHEMA}.products(id)
            ON DELETE CASCADE
    );

    -- Create trigger for reviews updated_at
    CREATE TRIGGER update_reviews_updated_at
        BEFORE UPDATE ON {SCHEMA}.reviews
        FOR EACH ROW
        EXECUTE FUNCTION {SCHEMA}.update_updated_at_column();
        
    -- Create index on product_id for faster lookups
    CREATE INDEX IF NOT EXISTS idx_reviews_product_id 
        ON {SCHEMA}.reviews(product_id);
    """)

    # Create the orders table
    op.execute(f"""
    CREATE TABLE IF NOT EXISTS {SCHEMA}.orders (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded')),
        total_amount NUMERIC(10, 2) NOT NULL,
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
        BEFORE UPDATE ON {SCHEMA}.orders
        FOR EACH ROW
        EXECUTE FUNCTION {SCHEMA}.update_updated_at_column();
        
    -- Create index on user_id for faster lookups
    CREATE INDEX IF NOT EXISTS idx_orders_user_id 
        ON {SCHEMA}.orders(user_id);
    """)

    # Create search indexes
    op.execute(f"""
    CREATE INDEX IF NOT EXISTS search_bm25_idx ON {SCHEMA}.products
    USING bm25 (id, searchable_content, title)
    WITH (
        key_field='id',
        text_fields='{{"title": {{"tokenizer": {{"type": "ngram", "min_gram": 3, "max_gram": 3, "prefix_only": false}}}}}}'
    );
    """)

    op.execute(f"""
    CREATE INDEX IF NOT EXISTS text_embedding_idx
    ON {SCHEMA}.products
    USING hnsw (text_embedding public.vector_cosine_ops);
    """)
    
    op.execute(f"""
    CREATE INDEX IF NOT EXISTS image_embedding_idx
    ON {SCHEMA}.products
    USING hnsw (image_embedding public.vector_cosine_ops);
    """)


def downgrade() -> None:
    # Drop the entire schema and all its contents
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE;")
