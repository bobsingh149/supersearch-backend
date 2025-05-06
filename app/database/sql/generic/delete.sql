DELETE FROM {{ tenant }}.{{ table_name }}
WHERE id = '{{ id }}'
RETURNING id 