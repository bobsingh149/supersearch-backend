"""create_leads_table

Revision ID: 7ece81796eab
Revises: 46eafe2c37c7
Create Date: 2025-04-16 00:13:56.771449

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '7ece81796eab'
down_revision: Union[str, None] = '46eafe2c37c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create leads table in public schema
    op.execute("""
    CREATE TABLE IF NOT EXISTS public.leads (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(255) NOT NULL,
        business_email VARCHAR(255) NOT NULL UNIQUE,
        company_name VARCHAR(255) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Create trigger for updated_at
    CREATE OR REPLACE FUNCTION public.update_leads_updated_at()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ language 'plpgsql';
    
    CREATE TRIGGER update_leads_updated_at
        BEFORE UPDATE ON public.leads
        FOR EACH ROW
        EXECUTE FUNCTION public.update_leads_updated_at();
    """)


def downgrade() -> None:
    # Drop the leads table
    op.execute("""
    DROP TRIGGER IF EXISTS update_leads_updated_at ON public.leads;
    DROP FUNCTION IF EXISTS public.update_leads_updated_at();
    DROP TABLE IF EXISTS public.leads;
    """)
