WITH bm25_matches AS (
    SELECT 
        id,
        row_number() over(order by paradedb.score(id) desc) as rank_ix
    FROM 
        {{ tenant }}.products
    WHERE 
        id @@@ paradedb.match(
            field => 'searchable_content',
            value => '{{ query_text }}',
            distance => {{ fuzzy_distance }}
        )
    ORDER BY rank_ix
    LIMIT {{ match_count }} * 2
),
semantic AS (
    SELECT
        id,
        row_number() over (order by (text_embedding <=> '{{ query_embedding }}')*1) as rank_ix
    FROM
        {{ tenant }}.products
    ORDER BY rank_ix
    LIMIT {{ match_count }} * 2
)
SELECT
    p.id,
    p.title,
    p.custom_data,
    p.searchable_content,
    p.image_url,
    (COALESCE(1.0 / ({{ rrf_k }} + bm25_matches.rank_ix), 0.0) * {{ full_text_weight }} +
     COALESCE(1.0 / ({{ rrf_k }} + semantic.rank_ix), 0.0) * {{ semantic_weight }}) as score
FROM
    bm25_matches
    FULL OUTER JOIN semantic
        ON bm25_matches.id = semantic.id
    JOIN {{ tenant }}.products p
        ON coalesce(bm25_matches.id, semantic.id) = p.id
ORDER BY
    score DESC,
    p.id
LIMIT {{ match_count }}
OFFSET {{ offset }} 