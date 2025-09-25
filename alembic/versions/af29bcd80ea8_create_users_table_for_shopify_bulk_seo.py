"""create_users_table_for_shopify_bulk_seo

Revision ID: af29bcd80ea8
Revises: 7efd07744cd8
Create Date: 2025-09-19 17:29:21.270381

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af29bcd80ea8'
down_revision: Union[str, None] = '7efd07744cd8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the shopify_bulk_seo schema if it doesn't exist
    op.execute("CREATE SCHEMA IF NOT EXISTS shopify_bulk_seo;")

    # Create update_updated_at_column function for shopify_bulk_seo schema
    op.execute("""
    CREATE OR REPLACE FUNCTION shopify_bulk_seo.update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ language 'plpgsql';
    """)

    # Create the users table in shopify_bulk_seo schema
    op.execute("""
    CREATE TABLE IF NOT EXISTS shopify_bulk_seo.users (
        id VARCHAR(255) PRIMARY KEY,
        access_token VARCHAR(255) NOT NULL,
        product_description_custom_prompt TEXT,
        product_description_tone VARCHAR(255),
        product_description_word_count INTEGER,
        product_description_example TEXT,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    -- Create trigger for updated_at
    CREATE TRIGGER update_users_updated_at
        BEFORE UPDATE ON shopify_bulk_seo.users
        FOR EACH ROW
        EXECUTE FUNCTION shopify_bulk_seo.update_updated_at_column();
    """)

    # Alter existing columns to VARCHAR(255) if table already exists
    # This handles the case where the table was created with TEXT columns
    op.execute("""
    ALTER TABLE shopify_bulk_seo.users
    ALTER COLUMN id TYPE VARCHAR(255),
    ALTER COLUMN access_token TYPE VARCHAR(255),
    ALTER COLUMN product_description_tone TYPE VARCHAR(255);
    """)

    # Create the settings table in shopify_bulk_seo schema
    op.execute("""
    CREATE TABLE IF NOT EXISTS shopify_bulk_seo.settings (
        key VARCHAR(255) PRIMARY KEY,
        value JSONB NOT NULL DEFAULT '[]'::jsonb,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    -- Create trigger for settings updated_at
    CREATE TRIGGER update_settings_updated_at
        BEFORE UPDATE ON shopify_bulk_seo.settings
        FOR EACH ROW
        EXECUTE FUNCTION shopify_bulk_seo.update_updated_at_column();
    """)

    # Create the batch_jobs table with VARCHAR(255) status and check constraint
    op.execute("""
    CREATE TABLE IF NOT EXISTS shopify_bulk_seo.batch_jobs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(255) NOT NULL,
        payload JSONB,
        status VARCHAR(255) NOT NULL DEFAULT 'pending',
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT batch_jobs_status_check CHECK (status IN ('pending', 'running', 'completed', 'failed'))
    );

    -- Create trigger for batch_jobs updated_at
    CREATE TRIGGER update_batch_jobs_updated_at
        BEFORE UPDATE ON shopify_bulk_seo.batch_jobs
        FOR EACH ROW
        EXECUTE FUNCTION shopify_bulk_seo.update_updated_at_column();
    """)

    # Create the batch_products table with VARCHAR(255) status and check constraint
    op.execute("""
    CREATE TABLE IF NOT EXISTS shopify_bulk_seo.batch_products (
        batch_id UUID NOT NULL,
        product_id VARCHAR(255) NOT NULL,
        status VARCHAR(255) NOT NULL DEFAULT 'pending',
        error TEXT,
        ai_product_description TEXT,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (batch_id, product_id),
        CONSTRAINT fk_batch_products_batch_id
            FOREIGN KEY (batch_id)
            REFERENCES shopify_bulk_seo.batch_jobs(id)
            ON DELETE CASCADE,
        CONSTRAINT batch_products_status_check CHECK (status IN ('pending', 'processing', 'completed', 'failed'))
    );

    -- Create trigger for batch_products updated_at
    CREATE TRIGGER update_batch_products_updated_at
        BEFORE UPDATE ON shopify_bulk_seo.batch_products
        FOR EACH ROW
        EXECUTE FUNCTION shopify_bulk_seo.update_updated_at_column();
    """)

    # Insert default settings with sensible values
    op.execute("""
    INSERT INTO shopify_bulk_seo.settings (key, value) VALUES
    ('tone', '[
        {"label": "Professional", "value": "professional", "isDefault": true},
        {"label": "Friendly", "value": "friendly", "isDefault": false},
        {"label": "Casual", "value": "casual", "isDefault": false},
        {"label": "Persuasive", "value": "persuasive", "isDefault": false}
    ]'::jsonb),
    ('length', '[
        {"label": "Brief (50-100 words)", "value": "brief", "isDefault": true},
        {"label": "Standard (100-150 words)", "value": "standard", "isDefault": false},
        {"label": "Detailed (150-250 words)", "value": "detailed", "isDefault": false},
        {"label": "Comprehensive (250+ words)", "value": "comprehensive", "isDefault": false}
    ]'::jsonb),
    ('examples', '[
        {"label": "Fashion & Apparel", "value": "fashion_apparel", "isDefault": true},
        {"label": "Electronics & Gadgets", "value": "electronics_gadgets", "isDefault": false},
        {"label": "Home & Kitchen", "value": "home_kitchen", "isDefault": false},
        {"label": "Beauty & Personal Care", "value": "beauty_personal_care", "isDefault": false},
        {"label": "Sports & Outdoors", "value": "sports_outdoors", "isDefault": false},
        {"label": "Books & Media", "value": "books_media", "isDefault": false}
    ]'::jsonb),
    ('custom promots', '[
        {"label": "SEO Optimized", "value": "seo_optimized", "isDefault": true},
        {"label": "Benefit-Focused", "value": "benefit_focused", "isDefault": false},
        {"label": "Feature-Driven", "value": "feature_driven", "isDefault": false},
        {"label": "Storytelling", "value": "storytelling", "isDefault": false},
        {"label": "Urgency-Driven", "value": "urgency_driven", "isDefault": false}
    ]'::jsonb)
    ON CONFLICT (key) DO NOTHING;
    """)


def downgrade() -> None:
    # Drop the batch tables, users table, and settings table and related objects
    op.execute("""
    -- Drop triggers
    DROP TRIGGER IF EXISTS update_batch_products_updated_at ON shopify_bulk_seo.batch_products;
    DROP TRIGGER IF EXISTS update_batch_jobs_updated_at ON shopify_bulk_seo.batch_jobs;
    DROP TRIGGER IF EXISTS update_users_updated_at ON shopify_bulk_seo.users;
    DROP TRIGGER IF EXISTS update_settings_updated_at ON shopify_bulk_seo.settings;

    -- Drop tables (in correct order due to foreign key constraints)
    DROP TABLE IF EXISTS shopify_bulk_seo.batch_products;
    DROP TABLE IF EXISTS shopify_bulk_seo.batch_jobs;
    DROP TABLE IF EXISTS shopify_bulk_seo.settings;
    DROP TABLE IF EXISTS shopify_bulk_seo.users;

    -- Drop function
    DROP FUNCTION IF EXISTS shopify_bulk_seo.update_updated_at_column();

    -- Drop schema
    DROP SCHEMA IF EXISTS shopify_bulk_seo CASCADE;
    """)
