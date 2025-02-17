(
    SELECT
        p.id,
        p.title,
        p.custom_data,
        p.searchable_content,
        0 as score,
        'keyword' as search_type
    FROM
        products p
    WHERE
        id @@@ paradedb.match(
            field => 'searchable_content',
            value => '{{ query_text }}',
            distance => {{ fuzzy_distance }}
        )
    LIMIT least({{ match_count }}, 30)
)
UNION
(
    SELECT
        p.id,
        p.title,
        p.custom_data,
        p.searchable_content,
        0 as score,
        'semantic' as search_type
    FROM
        products p
    ORDER BY text_embedding <=> '{{ query_embedding }}'
    LIMIT least({{ match_count }}, 30)
) 