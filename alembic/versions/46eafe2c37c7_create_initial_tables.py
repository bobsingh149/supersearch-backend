"""create initial tables

Revision ID: 46eafe2c37c7
Revises: 
Create Date: 2025-01-03 13:55:06.606243

"""
from typing import Sequence, Union
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '46eafe2c37c7'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vectorscale CASCADE;")

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_search;")
    
    # Create the products table using raw SQL
    op.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        title TEXT,
        text_embedding vector(768),
        image_embedding vector(768),
        searchable_content TEXT,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        custom_data JSONB
    );

    -- Create trigger for updated_at
    CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ language 'plpgsql';

    CREATE TRIGGER update_products_updated_at
        BEFORE UPDATE ON products
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    # Create the documents table
    op.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        content TEXT,
        text_embedding vector(768),
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    -- Create trigger for updated_at
    CREATE TRIGGER update_documents_updated_at
        BEFORE UPDATE ON documents
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    # Create the conversations table
    op.execute("""
    CREATE TABLE IF NOT EXISTS conversations (
        conversation_id TEXT PRIMARY KEY,
        messages JSONB NOT NULL DEFAULT '[]'::jsonb,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    -- Create trigger for updated_at
    CREATE TRIGGER update_conversations_updated_at
        BEFORE UPDATE ON conversations
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();

    -- Create index on conversation_id for faster lookups
    CREATE INDEX IF NOT EXISTS idx_conversations_id ON conversations(conversation_id);
    """)

    # Create indexes
    op.execute("""
    CREATE INDEX IF NOT EXISTS search_bm25_idx ON products
    USING bm25 (id, searchable_content)
    WITH (key_field='id');
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS text_embedding_idx
    ON products
    USING diskann (text_embedding vector_cosine_ops);
    """)
    
    op.execute("""
    CREATE INDEX IF NOT EXISTS image_embedding_idx
    ON products
    USING diskann (image_embedding vector_cosine_ops);
    """)

    # Create index for text embedding in documents
    op.execute("""
    CREATE INDEX IF NOT EXISTS documents_text_embedding_idx
    ON documents
    USING diskann (text_embedding vector_cosine_ops);
    """)


def downgrade() -> None:
    # Drop everything in reverse order
    op.execute("""
    -- Drop triggers
    DROP TRIGGER IF EXISTS update_products_updated_at ON products;
    DROP TRIGGER IF EXISTS update_documents_updated_at ON documents;
    DROP TRIGGER IF EXISTS update_conversations_updated_at ON conversations;
    DROP FUNCTION IF EXISTS update_updated_at_column;
    
    -- Drop indexes
    DROP INDEX IF EXISTS search_bm25_idx;
    DROP INDEX IF EXISTS text_embedding_idx;
    DROP INDEX IF EXISTS image_embedding_idx;
    DROP INDEX IF EXISTS documents_text_embedding_idx;
    DROP INDEX IF EXISTS idx_conversations_id;
    
    -- Drop tables
    DROP TABLE IF EXISTS products;
    DROP TABLE IF EXISTS documents;
    DROP TABLE IF EXISTS conversations;
    
    -- Drop extensions (if no other tables are using them)
    DROP EXTENSION IF EXISTS vectorscale;
    DROP EXTENSION IF EXISTS pg_search;
    """)
