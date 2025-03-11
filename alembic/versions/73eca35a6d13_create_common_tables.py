"""create-common-tables

Revision ID: 73eca35a6d13
Revises: cd780001b0f7
Create Date: 2025-02-28 12:40:33.183142

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '73eca35a6d13'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create test schema

    # Create extensions in public schema
    op.execute("CREATE EXTENSION IF NOT EXISTS vectorscale CASCADE SCHEMA public;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_search SCHEMA paradedb;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm SCHEMA public;")
    
    # Create updated_at function in public schema
    op.execute("""
    CREATE OR REPLACE FUNCTION public.update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ language 'plpgsql';
    """)
    
    # Create tenants table
    op.execute("""
    CREATE TABLE IF NOT EXISTS public.tenants (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(256) NOT NULL,
        email VARCHAR(256) NOT NULL UNIQUE,
        is_active BOOLEAN NOT NULL DEFAULT true,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    -- Create trigger for updated_at
    CREATE TRIGGER update_tenants_updated_at
        BEFORE UPDATE ON public.tenants
        FOR EACH ROW
        EXECUTE FUNCTION public.update_updated_at_column();
    """)

    # Create organizations table
    op.execute("""
    CREATE TABLE IF NOT EXISTS public.organizations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(256) NOT NULL,
        description TEXT,
        meta_data JSONB,
        is_active BOOLEAN NOT NULL DEFAULT true,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    -- Create trigger for updated_at
    CREATE TRIGGER update_organizations_updated_at
        BEFORE UPDATE ON public.organizations
        FOR EACH ROW
        EXECUTE FUNCTION public.update_updated_at_column();
    """)

    # Create tenant_organizations table
    op.execute("""
    CREATE TABLE IF NOT EXISTS public.tenant_organizations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
        organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT tenant_organization_unique UNIQUE (tenant_id, organization_id)
    );

    -- Create trigger for updated_at
    CREATE TRIGGER update_tenant_organizations_updated_at
        BEFORE UPDATE ON public.tenant_organizations
        FOR EACH ROW
        EXECUTE FUNCTION public.update_updated_at_column();

    -- Create indexes
    CREATE INDEX IF NOT EXISTS idx_tenant_organizations_tenant_id 
        ON public.tenant_organizations(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_tenant_organizations_organization_id 
        ON public.tenant_organizations(organization_id);
    """)


def downgrade() -> None:
    # Drop tables in reverse order
    op.execute("""
    -- Drop triggers
    DROP TRIGGER IF EXISTS update_tenant_organizations_updated_at ON public.tenant_organizations;
    DROP TRIGGER IF EXISTS update_organizations_updated_at ON public.organizations;
    DROP TRIGGER IF EXISTS update_tenants_updated_at ON public.tenants;
    
    -- Drop tables
    DROP TABLE IF EXISTS public.tenant_organizations;
    DROP TABLE IF EXISTS public.organizations;
    DROP TABLE IF EXISTS public.tenants;
    
    -- Drop function
    DROP FUNCTION IF EXISTS public.update_updated_at_column();
    
    -- Drop extensions
    DROP EXTENSION IF EXISTS vectorscale CASCADE;
    DROP EXTENSION IF EXISTS pg_search CASCADE;
    DROP EXTENSION IF EXISTS pg_trgm;
    
    -- Drop schema
    DROP SCHEMA IF EXISTS test CASCADE;
    """)
