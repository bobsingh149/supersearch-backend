SELECT p.id, p.title, p.custom_data, p.searchable_content, p.image_url, p.ai_summary,
       COALESCE(
           (
               SELECT jsonb_agg(
                   jsonb_build_object(

                       'content', r.content,
                       'author', r.author

                   )
               )
               FROM (
                   SELECT content, author
                   FROM demo_movies.reviews
                   WHERE product_id = p.id
                   LIMIT 3
               ) r
           ),
           '[]'::jsonb
       ) as reviews
FROM demo_movies.products p
WHERE p.id = ANY(:product_ids)
GROUP BY p.id, p.title, p.custom_data, p.searchable_content, p.image_url, p.ai_summary 