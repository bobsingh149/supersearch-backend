SELECT
    d.id,
    d.title,
    d.custom_data,
    d.searchable_content,
    paradedb.score(d.id) as score
FROM
    documents d
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