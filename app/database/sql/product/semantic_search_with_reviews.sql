SELECT
    p.id,
    p.title,
    p.custom_data,
    p.searchable_content,
    p.image_url,
    p.ai_summary,
    (text_embedding <=> '{{ query_embedding }}')*1 as score,
    COALESCE(
        (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'content', r.content,
                    'author', r.author

                )
            )
            FROM (
                SELECT content, author
                FROM {{ tenant }}.reviews
                WHERE product_id = p.id
                LIMIT 3
            ) r
        ),
        '[]'::jsonb
    ) as reviews
FROM
    {{ tenant }}.products p
GROUP BY
    p.id, p.title, p.custom_data, p.searchable_content, p.image_url, p.ai_summary, p.text_embedding
ORDER BY
    score asc
LIMIT {{match_count}} 