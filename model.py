from locale import normalize

from transformers import AutoModel, AutoProcessor
import torch
from PIL import Image
import requests
import time
from scipy.spatial.distance import cosine


# Choose your model: 'Marqo/marqo-ecommerce-embeddings-L' or 'Marqo/marqo-ecommerce-embeddings-B'
model_name = 'Marqo/marqo-ecommerce-embeddings-B'

# Load the model and processor
model = AutoModel.from_pretrained(model_name, trust_remote_code=True, cache_dir="model_cache")
processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)


start_load_time = time.time()
end_load_time = time.time()

print(f"Model loading took {end_load_time - start_load_time:.4f} seconds")
print("Model is loaded")

# Load an image and text for testing
# img = Image.open(requests.get('https://res.cloudinary.com/dllr1e6gn/image/upload/v1/profile_images/aemio6hooqxp1eiqzpev', stream=True).raw).convert("RGB")
# image = [img]
dataset = ["fashionable yellow HEART T-Shirts made in paris", "red COAT RACK showcased in paris fashion", "YELLOW COAT RACK PARIS FASHION"]
query = ["designed in paris brands clothing"]

print("processing the inputs")
start_process_time = time.time()
dataset_processed = processor(text=dataset,padding='max_length', return_tensors="pt")
query_processed = processor(text=query,padding='max_length', return_tensors="pt")

# image_processed = processor(images=image, padding='max_length', return_tensors="pt")
# image_processed.do_rescale=False
end_process_time = time.time()
print(f"Input processing took {end_process_time - start_process_time:.4f} seconds")



for i in range(1):
    start_time = time.time()
    # Perform inference
    with torch.no_grad():
        # image_features = model.get_image_features(image_processed['pixel_values'], normalize=True)
        dataset_features = model.get_text_features(dataset_processed['input_ids'], normalize=True)
        query_features = model.get_text_features(query_processed['input_ids'],normalize=True)

        dataset_mat = dataset_features
        query_vec = query_features[0]

        text_probs = (100 * query_features @ dataset_features.T).softmax(dim=-1)

        # Calculate distance for each text embedding
        for idx, text_embedding in enumerate(dataset_mat):
            # Multiply both embeddings by 100 before calculating distance
            distance = cosine(text_embedding, query_vec)
            print(f"Distance for '{dataset[idx]}': {distance:.4f}")


    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Iteration {i+1} took {elapsed_time:.4f} seconds")
    print(text_probs)
