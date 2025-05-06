WITH product_embeddings AS (
    SELECT 
        text_embedding
    FROM 
        {{ tenant }}.products 
    WHERE 
        id = '{{ product_id }}'
)
SELECT
    p.id,
    p.title,
    p.custom_data,
    p.searchable_content,
    p.image_url,
    p.text_embedding <=> pe.text_embedding as score
FROM
    {{ tenant }}.products p,
    product_embeddings pe
WHERE
    p.id != '{{ product_id }}'
ORDER BY
    p.text_embedding <=> pe.text_embedding
LIMIT
    least({{ match_count }}, 30) 