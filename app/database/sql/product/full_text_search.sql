SELECT
    p.id,
    p.title,
    p.custom_data,
    p.searchable_content,
    p.image_url,
    paradedb.score(p.id) as score
FROM
    {{ tenant }}.products p
WHERE
    id @@@ paradedb.match(
        field => 'searchable_content',
        value => '{{ query_text }}',
        distance => {{ fuzzy_distance }}
    )
ORDER BY
    score DESC
LIMIT
    least({{ match_count }}, 30) 