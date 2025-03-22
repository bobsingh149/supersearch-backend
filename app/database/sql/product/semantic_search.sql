SELECT
    p.id,
    p.title,
    p.custom_data,
    p.searchable_content,
    (text_embedding <=> '{{ query_embedding }}')*1 as score
FROM
    products p
ORDER BY
    score asc
LIMIT {{match_count}}
