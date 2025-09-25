DELETE FROM {{ tenant }}.{{ table_name }}
WHERE {{ id_field }} = :{{ id_field }}
RETURNING {{ id_field }} 