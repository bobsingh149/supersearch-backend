SELECT *
FROM {{ tenant }}.{{ table_name }}
WHERE {{ id_field }} = '{{ id }}'
LIMIT 1 