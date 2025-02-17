SELECT
    p.id,
    p.title,
    p.custom_data,
    p.searchable_content,
    text_embedding <=> '{{ query_embedding }}' as score
FROM
    products p
ORDER BY
    text_embedding <=> '{{ query_embedding }}'
LIMIT
    least({{ match_count }}, 30) 