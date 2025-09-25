INSERT INTO {{ tenant }}.{{ table_name }}
(
{% for column in columns %}
    {% if not loop.first %}, {% endif %}{{ column }}
{% endfor %}
)
VALUES
{% for item in items %}
    {% if not loop.first %}, {% endif %}(
    {% for column in columns %}
        {% if not loop.first %}, {% endif %}:{{ column }}_{{ loop.parent.loop.index }}
    {% endfor %}
    )
{% endfor %}
RETURNING * 