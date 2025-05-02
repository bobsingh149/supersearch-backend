from typing import List, Dict, Any, Optional
import logging
import json
from google.genai.types import Content, GenerateContentConfig, AutomaticFunctionCallingConfig

from app.services.vertex import get_genai_client
from app.models.product_questions import ProductQuestionOutput

logger = logging.getLogger(__name__)

class ItemQuestionService:
    """Service for generating questions related to items using Gemini AI"""
    
    @staticmethod
    async def generate_questions(item_data: Dict[str, Any], num_questions: int = 5) -> ProductQuestionOutput:
        """
        Generate questions related to an item using Gemini AI.
        
        Args:
            item_data: Dictionary containing item data
            num_questions: Number of questions to generate (default: 5)
            
        Returns:
            ProductQuestionOutput: Structured output with list of questions
        """
        client = get_genai_client()
        
        if not item_data:
            return ProductQuestionOutput(questions=["No item data available for question generation."])
        
        # Construct the prompt
        prompt = f"""Generate {num_questions} relevant questions that a customer might ask about this item:

Item details: {json.dumps(item_data)}

Provide a response in JSON format with the following structure:
{{
  "questions": [
    "question 1",
    "question 2",
    "question 3",
    "question 4",
    "question 5"
  ]
}}

Each question should:
1. Be specifically answerable using the provided item context
2. Be concise and natural-sounding as if asked by a customer
3. Focus on different aspects of the item (specifications, usage, comparison with alternatives, etc.)
4. Use the actual item name rather than generic references
5. Be phrased as a direct question with a question mark
6. Represent common customer inquiries about this type of item

Your response must be valid JSON only, with no additional text before or after.
"""

        try:
            response = await client.aio.models.generate_content(
                model='gemini-2.0-flash-001',
                contents=prompt,
                config=GenerateContentConfig(
                    max_output_tokens=1000,
                    temperature=0.7,
                    automatic_function_calling=AutomaticFunctionCallingConfig(
                        disable=True,
                        maximum_remote_calls=0
                    ),
                ),
            )
            
            # Try to parse JSON response
            try:
                response_text = response.text.strip()
                # Clean up any potential markdown code block formatting
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                    
                response_data = json.loads(response_text.strip())
                
                # Create and return a validated model
                return ProductQuestionOutput.model_validate(response_data)
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {str(e)}")
                logger.debug(f"Response text: {response.text}")
                
                # Fallback to manually extracting questions or returning an error
                fallback_questions = [
                    "Failed to generate structured questions from AI response.",
                    "Please try again later."
                ]
                
                return ProductQuestionOutput(questions=fallback_questions)
                
        except Exception as e:
            logger.error(f"Error generating item questions: {str(e)}")
            return ProductQuestionOutput(
                questions=["Failed to generate item questions. Please try again later."]
            ) 