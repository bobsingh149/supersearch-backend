SELECT
    p.id,
    p.title,
    p.custom_data,
    p.searchable_content,
    paradedb.score(p.id) as score
FROM
    products p
WHERE
    id @@@ paradedb.match(
        field => 'title',
        value => '{{ query_text }}',
        distance => {{ fuzzy_distance }},
        conjunction_mode => true
    )
ORDER BY
    score DESC
LIMIT
    least({{ match_count }}, 10) 