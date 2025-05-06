WITH combined_results AS (
    (
        SELECT
            p.id,
            p.title,
            p.custom_data,
            p.searchable_content,
            p.image_url,
            paradedb.score(id) as score,
            'keyword' as search_type
        FROM
            {{ tenant }}.products p
        WHERE
            id @@@ paradedb.match(
                field => 'searchable_content',
                value => '{{ query_text }}',
                distance => {{ fuzzy_distance }}
            )
        ORDER BY paradedb.score(id) DESC
        LIMIT {{ match_count }}
    )
    UNION
    (
        SELECT
            p.id,
            p.title,
            p.custom_data,
            p.searchable_content,
            p.image_url,
            0 as score,
            'semantic' as search_type
        FROM
            {{ tenant }}.products p
        ORDER BY (text_embedding <=> '{{ query_embedding }}')*1
        LIMIT {{ match_count }}
    )
)

SELECT DISTINCT ON (id) 
    id,
    title,
    custom_data,
    searchable_content,
    image_url,
    score,
    search_type
FROM 
    combined_results
LIMIT {{ match_count }}
OFFSET {{ offset }} 