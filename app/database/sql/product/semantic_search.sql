SELECT
    p.id,
    p.title,
    p.custom_data,
    p.searchable_content,
    p.image_url,
    (text_embedding <=> '{{ query_embedding }}')*1 as score
FROM
    products p
ORDER BY
    score asc
LIMIT {{match_count}}
