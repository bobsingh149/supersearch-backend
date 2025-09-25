UPDATE {{ tenant }}.{{ table_name }}
SET
{% for column in updates %}
    {% if not loop.first %}, {% endif %}{{ column }} = :{{ column }}
{% endfor %}
WHERE {{ id_field }} = :{{ id_field }}
RETURNING * 