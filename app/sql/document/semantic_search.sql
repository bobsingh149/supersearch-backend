SELECT
    d.id,
    d.title,
    d.custom_data,
    d.searchable_content,
    text_embedding <=> '{{ query_embedding }}' as score
FROM
    documents d
ORDER BY
    text_embedding <=> '{{ query_embedding }}'
LIMIT
    least({{ match_count }}, 30) 