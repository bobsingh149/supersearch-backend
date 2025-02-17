WITH bm25_matches AS (
    SELECT 
        id,
        row_number() over(order by paradedb.score(id) desc) as rank_ix
    FROM 
        documents
    WHERE 
        id @@@ paradedb.match(
            field => 'searchable_content',
            value => '{{ query_text }}',
            distance => {{ fuzzy_distance }}
        )
    ORDER BY rank_ix
    LIMIT least({{ match_count }}, 30) * 2
),
semantic AS (
    SELECT
        id,
        row_number() over (order by text_embedding <=> '{{ query_embedding }}') as rank_ix
    FROM
        documents
    ORDER BY rank_ix
    LIMIT least({{ match_count }}, 30) * 2
)
SELECT
    d.id,
    d.title,
    d.custom_data,
    d.searchable_content,
    (COALESCE(1.0 / ({{ rrf_k }} + bm25_matches.rank_ix), 0.0) * {{ full_text_weight }} +
     COALESCE(1.0 / ({{ rrf_k }} + semantic.rank_ix), 0.0) * {{ semantic_weight }}) as score
FROM
    bm25_matches
    FULL OUTER JOIN semantic
        ON bm25_matches.id = semantic.id
    JOIN documents d
        ON coalesce(bm25_matches.id, semantic.id) = d.id
ORDER BY
    score DESC
LIMIT
    least({{ match_count }}, 30) 