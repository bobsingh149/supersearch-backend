import logging
from typing import List, Dict, Optional, Tuple
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json

from google import genai
from google.genai.types import GenerationConfig

from app.services.vertex import get_genai_client
from app.models.generate_content import ContentTopic, ContentGenerationResult, ContentGenerationStatus
from app.models.product import Product

logger = logging.getLogger(__name__)

TOPIC_PROMPTS = {
    ContentTopic.PRODUCT_DESCRIPTION: """Write a compelling and detailed product description for the following product:
{product_details}

The description should be engaging, highlight key features, and be between 150-200 words.
""",
    
    ContentTopic.STYLE_GUIDES: """Create a style guide for the following product:
{product_details}

Include information on how to wear/use it, what it pairs well with, seasonal recommendations, and styling tips.
The style guide should be around 150-200 words.
""",
    
    ContentTopic.FEATURES: """List and explain the key features of the following product:
{product_details}

Format as bullet points with brief explanations for each feature. Include at least 5-7 key features.
""",
    
    ContentTopic.BENEFITS: """Describe the main benefits of using/owning the following product:
{product_details}

Focus on how the product solves problems or improves the customer's life. Format as bullet points with
explanations for each benefit. Include at least 4-6 key benefits.
""",
    
    ContentTopic.USAGE_INSTRUCTIONS: """Create clear instructions on how to use the following product:
{product_details}

Include step-by-step usage guidelines, best practices, and any special considerations.
""",
    
    ContentTopic.CARE_INSTRUCTIONS: """Provide detailed care instructions for the following product:
{product_details}

Include cleaning methods, maintenance tips, storage recommendations, and how to extend the product's lifespan.
""",
    
    ContentTopic.SPECIFICATIONS: """Create a comprehensive technical specifications list for the following product:
{product_details}

Include dimensions, materials, compatibility, performance metrics, and any other relevant technical details.
Format as a well-organized list with categories.
""",
    
    ContentTopic.REVIEWS_SUMMARY: """Create a fictional summary of customer reviews for the following product:
{product_details}

Include overall rating (out of 5 stars), pros and cons mentioned by customers, and common feedback points.
Note: This is a generated summary and not based on actual customer reviews.
""",
    
    ContentTopic.COMPARISONS: """Generate a comparison between this product and similar products in the market:
{product_details}

Compare on factors like price range, quality, features, and use cases. Present as an objective comparison
without making definitive claims about being better than competitors.
Note: This is a generated comparison and not based on actual market analysis.
"""
}

class ContentGenerator:
    @staticmethod
    def format_product_for_prompt(product: Product) -> str:
        """Format product details for use in a prompt"""
        
        details = f"Product Name: {product.title or 'Untitled Product'}\n"
        
        if product.searchable_content:
            details += f"Product Details: {product.searchable_content}\n"
        
        if product.custom_data:
            # Add any relevant custom data
            for key, value in product.custom_data.items():
                # Skip complex nested structures and empty values
                if isinstance(value, (str, int, float)) and value:
                    details += f"{key.replace('_', ' ').title()}: {value}\n"
        
        return details

    @staticmethod
    async def generate_content_for_product(
        product: Product,
        topic: ContentTopic
    ) -> ContentGenerationResult:
        """Generate content for a specific product and topic using Gemini"""
        try:
            # Get the appropriate prompt template
            prompt_template = TOPIC_PROMPTS.get(topic)
            if not prompt_template:
                return ContentGenerationResult(
                    product_id=product.id,
                    topic=topic,
                    content="",
                    status=ContentGenerationStatus.FAILED,
                    error=f"No prompt template found for topic: {topic}"
                )
            
            # Format the product details for the prompt
            product_details = ContentGenerator.format_product_for_prompt(product)
            
            # Build the complete prompt
            prompt = prompt_template.format(product_details=product_details)
            
            # Initialize the Gemini client
            client = get_genai_client()
            
            # Configure generation parameters
            generation_config = GenerationConfig(
                temperature=0.7,
                max_output_tokens=500,
                top_p=0.95,
            )
            
            # Generate content
            response = await client.aio.models.generate_content(
                model='gemini-2.0-flash-001',
                contents=prompt,
                generation_config=generation_config
            )
            
            # Return the generated content
            return ContentGenerationResult(
                product_id=product.id,
                topic=topic,
                content=response.text,
                status=ContentGenerationStatus.COMPLETED
            )
            
        except Exception as e:
            logger.error(f"Error generating content for product {product.id}, topic {topic}: {str(e)}")
            return ContentGenerationResult(
                product_id=product.id,
                topic=topic,
                content="",
                status=ContentGenerationStatus.FAILED,
                error=str(e)
            )

    @staticmethod
    async def update_product_content(
        session: AsyncSession,
        product_id: str,
        topic: ContentTopic,
        content: str,
        tenant: str
    ) -> bool:
        """
        Update or add the AI-generated content for a product
        Returns True if successful, False otherwise
        """
        try:
            # Format the topic for storage (e.g., "product_description:Content text")
            content_entry = f"{topic.value}:{content}"
            
            # Check if the product already has ai_generated_contents
            query = text(f"""
                SELECT ai_generated_contents 
                FROM {tenant}.products 
                WHERE id = :product_id
            """)
            result = await session.execute(query, {"product_id": product_id})
            row = result.first()
            
            if not row:
                logger.error(f"Product not found: {product_id}")
                return False
                
            # Get current contents or initialize empty array
            current_contents = row[0] if row[0] else []
            
            # Check if this topic already exists
            topic_prefix = f"{topic.value}:"
            updated = False
            
            for i, entry in enumerate(current_contents):
                if entry.startswith(topic_prefix):
                    # Replace existing topic content
                    current_contents[i] = content_entry
                    updated = True
                    break
            
            if not updated:
                # Add new topic content
                current_contents.append(content_entry)
            
            # Update the database
            update_query = text(f"""
                UPDATE {tenant}.products 
                SET ai_generated_contents = :contents
                WHERE id = :product_id
            """)
            await session.execute(update_query, {
                "product_id": product_id,
                "contents": current_contents
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating product content: {str(e)}")
            return False 