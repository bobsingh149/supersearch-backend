SELECT *
FROM {{ tenant }}.{{ table_name }}
{% if filters %}
WHERE 
    {% for column, value in filters.items() %}
    {% if loop.index > 1 %} AND {% endif %}{{ column }} = '{{ value }}'
    {% endfor %}
{% endif %}
{% if sort_by %}
ORDER BY {{ sort_by }} {{ sort_direction | default('ASC') }}
{% endif %}
{% if limit %}
LIMIT {{ limit }}
{% endif %}
{% if offset %}
OFFSET {{ offset }}
{% endif %} 