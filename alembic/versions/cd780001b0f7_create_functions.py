"""create-functions

Revision ID: cd780001b0f7
Revises: 46eafe2c37c7
Create Date: 2025-02-09 03:08:41.509980

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd780001b0f7'
down_revision: Union[str, None] = '46eafe2c37c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the hybrid search function with ParadeDB
    op.execute("""
    CREATE OR REPLACE FUNCTION hybrid_search(
        query_text text,
        query_embedding vector(768),
        match_count int,
        full_text_weight float = 1,
        semantic_weight float = 1,
        rrf_k int = 50,
        fuzzy_distance int = 2
    )
    RETURNS TABLE (
        id text,
        text_embedding vector(768),
        image_embedding vector(768),
        searchable_content text,
        created_at timestamp with time zone,
        updated_at timestamp with time zone,
        custom_data jsonb,
        score float
    )
    LANGUAGE sql
    AS $$
        WITH bm25_matches AS (
            SELECT 
                id,
                row_number() over(order by paradedb.score(id) desc) as rank_ix
            FROM 
                products
            WHERE 
                id @@@ paradedb.match(
                    field => 'searchable_content',
                    value => query_text,
                    distance => fuzzy_distance
                )
            ORDER BY rank_ix
            LIMIT least(match_count, 30) * 2
        ),
        semantic AS (
            SELECT
                id,
                row_number() over (order by text_embedding <=> query_embedding) as rank_ix
            FROM
                products
            ORDER BY rank_ix
            LIMIT least(match_count, 30) * 2
        )
        SELECT
            p.id,
            p.text_embedding,
            p.image_embedding,
            p.searchable_content,
            p.created_at,
            p.updated_at,
            p.custom_data,
            (COALESCE(1.0 / (rrf_k + bm25_matches.rank_ix), 0.0) * full_text_weight +
             COALESCE(1.0 / (rrf_k + semantic.rank_ix), 0.0) * semantic_weight) as score
        FROM
            bm25_matches
            FULL OUTER JOIN semantic
                ON bm25_matches.id = semantic.id
            JOIN products p
                ON coalesce(bm25_matches.id, semantic.id) = p.id
        ORDER BY
            score DESC
        LIMIT
            least(match_count, 30)
    $$;
    """)

    # Add the unranked hybrid search function
    op.execute("""
    CREATE OR REPLACE FUNCTION hybrid_search_without_ranking(
        query_text text,
        query_embedding vector(768),
        match_count int,
        fuzzy_distance int = 2
    )
    RETURNS TABLE (
        id text,
        text_embedding vector(768),
        image_embedding vector(768),
        searchable_content text,
        created_at timestamp with time zone,
        updated_at timestamp with time zone,
        custom_data jsonb,
        search_type text
    )
    LANGUAGE sql
    AS $$
        (
            SELECT
                p.*,
                'keyword' as search_type
            FROM
                products p
            WHERE
                id @@@ paradedb.match(
                    field => 'searchable_content',
                    value => query_text,
                    distance => fuzzy_distance
                )
            LIMIT least(match_count, 30)
        )
        UNION
        (
            SELECT
                p.*,
                'semantic' as search_type
            FROM
                products p
            ORDER BY text_embedding <=> query_embedding
            LIMIT least(match_count, 30)
        )
    $$;
    """)

    # Add the full text search function with fuzzy matching
    op.execute("""
    CREATE OR REPLACE FUNCTION full_text_search(
        query_text text,
        match_count int = 10,
        fuzzy_distance int = 1
    )
    RETURNS TABLE (
        searchable_content text,
        score float
    )
    LANGUAGE sql
    AS $$
        SELECT
            p.searchable_content,
            paradedb.score(p.id) as score
        FROM
            products p
        WHERE
            id @@@ paradedb.match(
                field => 'searchable_content',
                value => query_text,
                distance => fuzzy_distance
            )
        ORDER BY
            score DESC
        LIMIT
            least(match_count, 30)
    $$;
    """)
    

    # Add the autocomplete search function
    op.execute("""
    CREATE OR REPLACE FUNCTION autocomplete_search(
        query_text text,
        match_count int = 10,
        fuzzy_distance int = 2
    )
    RETURNS TABLE (
        id text,
        text_embedding vector(768),
        image_embedding vector(768),
        searchable_content text,
        created_at timestamp with time zone,
        updated_at timestamp with time zone,
        custom_data jsonb,
        score float
    )
    LANGUAGE sql
    AS $$
        SELECT
            p.*,
            paradedb.score(p.id) as score
        FROM
            products p
        WHERE
            id @@@ paradedb.match(
                field => 'searchable_content',
                value => query_text,
                distance => fuzzy_distance,
                conjunction_mode => true
            )
        ORDER BY
            score DESC
        LIMIT
            least(match_count, 10)
    $$;
    """)


def downgrade() -> None:
    op.execute("""
    DROP FUNCTION IF EXISTS hybrid_search(text, vector(768), int, float, float, int, int);
    DROP FUNCTION IF EXISTS hybrid_search_without_ranking(text, vector(768), int, int);
    DROP FUNCTION IF EXISTS full_text_search(text, int, int);
    DROP FUNCTION IF EXISTS autocomplete_search(text, int, int);
    """)
