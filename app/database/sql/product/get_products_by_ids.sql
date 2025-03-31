SELECT id, title, custom_data, searchable_content, image_url 
FROM demo_movies.products
WHERE id = ANY(:product_ids) 