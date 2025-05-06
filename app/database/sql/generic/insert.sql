INSERT INTO {{ tenant }}.{{ table_name }}
(
{% for column in columns %}
    {% if not loop.first %}, {% endif %}{{ column }}
{% endfor %}
)
VALUES
(
{% for column in columns %}
    {% if not loop.first %}, {% endif %}'{{ values[column] }}'
{% endfor %}
)
RETURNING * 