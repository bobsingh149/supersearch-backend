SELECT *
FROM {{ tenant }}.{{ table_name }}
WHERE {{ id_field }} = :{{ id_field }}
LIMIT 1 