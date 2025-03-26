"""create initial tables

Revision ID: 46eafe2c37c7
Revises: 73eca35a6d13
Create Date: 2025-01-03 13:55:06.606243

"""
from typing import Sequence, Union
from alembic import op

# Import enums from model files
from app.models.settings import SettingKey
from app.models.sync_config import SyncSource
from app.models.sync_history import SyncStatus

# revision identifiers, used by Alembic.
revision: str = '46eafe2c37c7'
down_revision: Union[str, None] = '73eca35a6d13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMAS = ['demo_movies', 'test','development', 'staging', 'production']

def upgrade() -> None:
    # Convert enum values to strings and join them for SQL
    setting_keys = ", ".join([f"'{key.value}'" for key in SettingKey])
    sync_sources = ", ".join([f"'{source.value}'" for source in SyncSource])
    sync_statuses = ", ".join([f"'{status.value}'" for status in SyncStatus])
    
    for schema in SCHEMAS:
        # Create schema if it doesn't exist
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema};")

        # Create update_updated_at_column function for each schema
        op.execute(f"""
        CREATE OR REPLACE FUNCTION {schema}.update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        """)

        # Create the products table using raw SQL
        op.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.products (
            id TEXT PRIMARY KEY,
            title TEXT,
            text_embedding public.vector(768),
            image_embedding public.vector(768),
            searchable_content TEXT,
            image_url TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            custom_data JSONB
        );

        -- Create trigger for updated_at
        CREATE TRIGGER update_products_updated_at
            BEFORE UPDATE ON {schema}.products
            FOR EACH ROW
            EXECUTE FUNCTION {schema}.update_updated_at_column();
        """)

        # Create the conversations table
        op.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.conversations (
            conversation_id TEXT PRIMARY KEY,
            messages JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        -- Create trigger for updated_at
        CREATE TRIGGER update_conversations_updated_at
            BEFORE UPDATE ON {schema}.conversations
            FOR EACH ROW
            EXECUTE FUNCTION {schema}.update_updated_at_column();

        -- Create index on conversation_id for faster lookups
        CREATE INDEX IF NOT EXISTS idx_conversations_id 
            ON {schema}.conversations(conversation_id);
        """)

        # Create the settings table
        op.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.settings (
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
            BEFORE UPDATE ON {schema}.settings
            FOR EACH ROW
            EXECUTE FUNCTION {schema}.update_updated_at_column();
        """)

        # Create the sync_history table
        op.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.sync_history (
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
            BEFORE UPDATE ON {schema}.sync_history
            FOR EACH ROW
            EXECUTE FUNCTION {schema}.update_updated_at_column();
            
        -- Create index on created_at for sync_history to improve sorting performance
        CREATE INDEX IF NOT EXISTS sync_history_created_at_idx ON {schema}.sync_history (created_at DESC);
        """)

        # Create indexes
        op.execute(f"""
        CREATE INDEX IF NOT EXISTS search_bm25_idx ON {schema}.products
        USING bm25 (id, searchable_content, title)
        WITH (
            key_field='id',
            text_fields='{{"title": {{"tokenizer": {{"type": "ngram", "min_gram": 3, "max_gram": 3, "prefix_only": false}}}}}}'
        );
        """)

        op.execute(f"""
        CREATE INDEX IF NOT EXISTS text_embedding_idx
        ON {schema}.products
        USING diskann (text_embedding public.vector_cosine_ops);
        """)
        
        op.execute(f"""
        CREATE INDEX IF NOT EXISTS image_embedding_idx
        ON {schema}.products
        USING diskann (image_embedding public.vector_cosine_ops);
        """)




def downgrade() -> None:
    # Drop everything in reverse order for each schema
    for schema in SCHEMAS:
        op.execute(f"""
        -- Drop triggers
        DROP TRIGGER IF EXISTS update_products_updated_at ON {schema}.products;
        DROP TRIGGER IF EXISTS update_conversations_updated_at ON {schema}.conversations;
        DROP TRIGGER IF EXISTS update_settings_updated_at ON {schema}.settings;
        DROP TRIGGER IF EXISTS update_sync_history_updated_at ON {schema}.sync_history;
        DROP FUNCTION IF EXISTS {schema}.update_updated_at_column();
        
        -- Drop indexes
        DROP INDEX IF EXISTS {schema}.search_bm25_idx;
        DROP INDEX IF EXISTS {schema}.text_embedding_idx;
        DROP INDEX IF EXISTS {schema}.image_embedding_idx;
        DROP INDEX IF EXISTS {schema}.idx_conversations_id;
        
        -- Drop tables
        DROP TABLE IF EXISTS {schema}.products;
        DROP TABLE IF EXISTS {schema}.conversations;
        DROP TABLE IF EXISTS {schema}.settings;
        DROP TABLE IF EXISTS {schema}.sync_history;
        
        -- Drop schema
        DROP SCHEMA IF EXISTS {schema} CASCADE;
        """)
