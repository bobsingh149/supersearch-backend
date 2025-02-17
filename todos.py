"""
1. superbase postgres with the pg vector extension
2. have both docker and cloud soutions
3. cosine closest neighbor and use just regualar vector
4. HNSW Indexes with Postgres and pgvector exact log and with index logn
5. embedding
6. text embedding small of openai

DO hybrid search both keyword matching and semantic matching

embeddig

Do by topic

Make a ui where u can add topics and update them this would be the only option it should
have abilty to be prefilled from pdf
Text blob for the spell check

for cloud make sure to give read only permission for single table

Include some basic analytics like top searches

Use cases
Search , help and recommendations

Give complete features give autocomplete also

also make the frontend component that direcy call my api

send data by the api no db access

https://github.com/johannesocean/pgvector-demo/tree/main/app

https://huggingface.co/BAAI/bge-m3

https://www.youtube.com/watch?v=JEBDfGqrAUA&t=1975s 
Already had chatbot for documentation


search anything image or text , upload image and find similar images useful for ecommerce and 
search image or text by semantics only need id, images and title, description, color optional fields

Search by the images or text and upload image to get similar images similar products or product recommendations and doc chatbot

pgvectorscale

hyrbid search (keyword(BM25), semantic and image

for data import see this https://console.cloud.timescale.com/dashboard/services/rujozngdux/import

tsvector

https://colab.research.google.com/drive/1ZXzRX5nGp6FlYZmA6sJNOTo2CweMvOsw?usp=sharing

https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/

https://www.youtube.com/watch?v=MlRkBvOCfTY

allow user to load their data and test the hybrid search

Also give autocomplete

only thumbnail url / blob / base64 will be used ask them to simply specify the fields of search and thumbnail column

https://www.youtube.com/watch?v=bQWfJxVYktY

Remove html tags from the text for all fields

use marque ecommerce embedding model and say in your webiste its better than openai, gemeni and amzaon embedding models 
trained on large ecommerce dataset fine tuned for the ecommerce

why use ours
Most models are trained on generic data and they little bit of everything
Our model is trained on large ecommerce dataset fine tuned for the ecommerce so it out performs all the other models

Give example of use cases yellow , lemon and amber will show similar colors even when
we don't find the exact keywords insted of returning no results

https://hub.docker.com/r/oaklight/vectorsearch/tags

Uses state of the art BM25 algorithm , semantic search and image search

Also add the custom filters tags, metafield and fields

https://github.com/jankovicsandras/plpgsql_bm25

https://www.youtube.com/watch?v=TbtBhbLh0cc

https://github.com/vgrabovets/multi_rake

https://github.com/daveebbelaar/pgvectorscale-rag-solution/tree/hybrid-search

have all filters

Have 3 types of autocomplete past history, trending and search when starts typing

Also have support for blog searching

Use yogi sister as paid promotion

Have a similar structure for all tables with metadata containing all columns
"""

