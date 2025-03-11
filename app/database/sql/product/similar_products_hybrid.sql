WITH product_embeddings AS (
    SELECT 
        text_embedding,
        searchable_content
    FROM 
        products 
    WHERE 
        id = '{{ product_id }}'
),
bm25_matches AS (
    SELECT 
        p.id,
        row_number() over(order by paradedb.score(p.id) desc) as rank_ix
    FROM 
        products p,
        product_embeddings pe
    WHERE 
        p.id @@@ paradedb.match(
            field => 'searchable_content',
            value => '{{ searchable_content }}',
            distance => 2
        )
        AND p.id != '{{ product_id }}'
    ORDER BY rank_ix
    LIMIT least({{ match_count }}, 30) * 2
),
semantic AS (
    SELECT
        p.id,
        row_number() over (order by p.text_embedding <=> pe.text_embedding) as rank_ix
    FROM
        products p,
        product_embeddings pe
    WHERE
        p.id != '{{ product_id }}'
    ORDER BY rank_ix
    LIMIT least({{ match_count }}, 30) * 2
)
SELECT
    p.id,
    p.title,
    p.custom_data,
    p.searchable_content,
    (COALESCE(1.0 / ({{ rrf_k }} + bm25_matches.rank_ix), 0.0) * {{ full_text_weight }} +
     COALESCE(1.0 / ({{ rrf_k }} + semantic.rank_ix), 0.0) * {{ semantic_weight }}) as score
FROM
    bm25_matches
    FULL OUTER JOIN semantic
        ON bm25_matches.id = semantic.id
    JOIN products p
        ON coalesce(bm25_matches.id, semantic.id) = p.id
ORDER BY
    score DESC
LIMIT
    least({{ match_count }}, 30) 