UPDATE {{ tenant }}.{{ table_name }}
SET
{% for column, value in updates.items() %}
    {% if not loop.first %}, {% endif %}{{ column }} = '{{ value }}'
{% endfor %}
WHERE id = '{{ id }}'
RETURNING * 