SELECT 
    id, 
    title,
    custom_data, 
    searchable_content,
    image_url,
    0 as score
FROM {{ tenant }}.products
{% if filter_field and filter_value %}
WHERE 
    id @@@ paradedb.match(
        field => 'searchable_content',
        value => '{{ filter_value }}',
        distance => 1
    )
{% endif %}
{% if sort_field %}
ORDER BY (custom_data->>'{{ sort_field }}')::float {{ sort_direction | upper }}, id
{% else %}
ORDER BY id
{% endif %}
LIMIT {{ limit }} OFFSET {{ offset }} 