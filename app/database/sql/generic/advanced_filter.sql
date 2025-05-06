SELECT *
FROM {{ tenant }}.{{ table_name }}
{% if filters %}
WHERE 
    {% for filter in filters %}
    {% if loop.index > 1 %} {{ filter.logic_operator | default('AND') }} {% endif %}
    {{ filter.column }} {{ filter.operator | default('=') }} 
    {% if filter.operator in ['IN', 'NOT IN'] %}
        ({% for val in filter.value %}{% if not loop.first %}, {% endif %}'{{ val }}'{% endfor %})
    {% elif filter.operator in ['BETWEEN', 'NOT BETWEEN'] %}
        '{{ filter.value[0] }}' AND '{{ filter.value[1] }}'
    {% elif filter.operator in ['IS NULL', 'IS NOT NULL'] %}
        {# No value needed for these operators #}
    {% else %}
        '{{ filter.value }}'
    {% endif %}
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