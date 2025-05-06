SELECT *
FROM {{ tenant }}.{{ table_name }}
WHERE id = '{{ id }}'
LIMIT 1 