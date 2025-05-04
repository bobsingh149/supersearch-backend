SELECT
    p.id,
    p.title,
    p.custom_data,
    p.searchable_content,
    p.image_url,
    CASE
        WHEN length('{{ query_text }}') < 3 THEN 1
        ELSE paradedb.score(p.id)
    END as score
FROM
    products p
WHERE
    CASE
        WHEN length('{{ query_text }}') < 3 THEN
            title ILIKE '{{ query_text }}%'
        ELSE
            id @@@ paradedb.match(
            field => 'title',
            value => '{{ query_text }}',
            distance => {{ fuzzy_distance }}
             )
    END
ORDER BY
    score DESC
LIMIT
    least({{ match_count }}, 10) 