import logging
import time
from typing import List
from enum import Enum

from google import genai
from google.auth import load_credentials_from_file
import vertexai
from google.genai.types import HttpOptions
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel
from app.core.appsettings import app_settings
logger = logging.getLogger(__name__)

# Load credentials and initialize Vertex AI
credentials, project = load_credentials_from_file(app_settings.google.credentials_path)
vertexai.init(project=project, credentials=credentials, location="asia-south1")

# Initialize the model
MODEL_NAME = "text-embedding-005"
model = TextEmbeddingModel.from_pretrained(MODEL_NAME)

# Initialize the Gemini client using project from settings
genai_client = genai.Client(vertexai=True, project=app_settings.google.project, location='us-central1',
                            http_options=HttpOptions(api_version='v1'))

def get_genai_client():
    return genai_client


class TaskType(Enum):
    DOCUMENT = "RETRIEVAL_DOCUMENT"
    QUERY = "RETRIEVAL_QUERY"

async def get_embedding(
    text: str | list[str], 
    task_type: TaskType = TaskType.QUERY
) -> List[float]:
    """
    Generate text embedding using Google's Vertex AI text-embedding-005 model.

    Args:
        text: The input text or list of texts to generate embeddings for.
        task_type: The type of embedding task. Use TaskType.DOCUMENT for document 
                  embeddings or TaskType.QUERY for query embeddings.

    Returns:
        A list of floats representing the embedding.
    """
    total_start_time = time.time()

    # Ensure input is a list
    if isinstance(text, str):
        text = text.replace("\n", " ")
        logger.debug(f"Processing single text of length: {len(text)}")
        texts = [text]
    else:
        logger.debug(f"Processing batch of {len(text)} texts")
        texts = text

    try:
        # Generate embeddings using Vertex AI
        embed_start = time.time()
        
        # Create embedding inputs with specified task type
        inputs = [TextEmbeddingInput(t, task_type.value) for t in texts]
        
        # Get embeddings
        embeddings = await model.get_embeddings_async(inputs)
        embedding = embeddings[0].values  # Get first embedding's values
        
        logger.debug(f"Embedding generation completed in {time.time() - embed_start:.3f}s")

        total_time = time.time() - total_start_time
        logger.info(f"Total embedding process completed in {total_time:.3f}s")
        return embedding

    except Exception as e:
        logger.error(f"Error generating text embedding: {str(e)}", exc_info=True)
        raise