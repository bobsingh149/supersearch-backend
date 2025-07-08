SELECT 
    id, 
    title,
    custom_data, 
    searchable_content,
    image_url,
    0 as score
FROM {{ tenant }}.products
{% if filter_condition %}
WHERE {{ filter_condition }}
{% endif %}
{% if sort_field %}
ORDER BY (custom_data->>'{{ sort_field }}')::float {{ sort_direction | upper }}, id
{% else %}
ORDER BY id
{% endif %}
LIMIT {{ limit }} OFFSET {{ offset }} 