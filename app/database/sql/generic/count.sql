SELECT COUNT(*) as total
FROM {{ tenant }}.{{ table_name }}
{% if filters %}
WHERE 
    {% for column, value in filters.items() %}
    {% if loop.index > 1 %} AND {% endif %}{{ column }} = '{{ value }}'
    {% endfor %}
{% endif %} 