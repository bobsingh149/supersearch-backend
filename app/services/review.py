from typing import List, Optional, Dict
import logging
import json
import random
from google.genai.types import Content, Part, GenerateContentConfig, AutomaticFunctionCallingConfig
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.vertex import get_genai_client
from app.models.product import Product, ProductDB

logger = logging.getLogger(__name__)

class ReviewSummaryOutput(BaseModel):
    """Structured output for review summary"""
    summary: str
    pros: List[str]
    cons: List[str]

class GeneratedReviewsOutput(BaseModel):
    """Structured output for generated reviews and summary"""
    reviews: List[Dict[str, str]]
    summary: ReviewSummaryOutput

async def generate_review_summary(reviews: List[str], product_id: str, session: Optional[AsyncSession] = None, tenant: str = None) -> ReviewSummaryOutput:
    """
    Generate a summary of product reviews using Gemini AI.
    
    Args:
        reviews: List of review content strings
        product_id: ID of the product to fetch for context
        session: Optional database session
        tenant: Database schema to use
        
    Returns:
        ReviewSummaryOutput: Structured output with summary, pros and cons
    """
    client = get_genai_client()
    
    if not reviews:
        return ReviewSummaryOutput(
            summary="No reviews available to summarize.",
            pros=[],
            cons=[]
        )
    
    # Fetch product custom data if session is provided
    product_custom_data = None
    if session and tenant:
        try:
            # Get only custom_data from database
            query = text(f"SELECT custom_data FROM {tenant}.products WHERE id = :product_id")
            result = await session.execute(query, {"product_id": product_id})
            custom_data = result.scalar_one_or_none()
            
            if custom_data:
                product_custom_data = custom_data
        except Exception as e:
            logger.error(f"Error fetching product custom_data with ID {product_id}: {str(e)}")
    
    # Construct the prompt
    product_context = ""
    if product_custom_data:
        product_context = f"Product details: {json.dumps(product_custom_data)}"
    
    reviews_text = "\n\n".join([f"Review {i+1}: {review}" for i, review in enumerate(reviews)])
    
    prompt = f"""Analyze the following customer reviews with the product details:

{product_context}

Reviews:
{reviews_text}

Provide a response in JSON format with the following structure:
{{
  "summary": "A brief 2-3 sentence summary of the overall sentiment",
  "pros": ["pro point 1", "pro point 2", "pro point 3"],
  "cons": ["con point 1", "con point 2", "con point 3"]
}}

The "summary" should be a direct and concise overview of customer opinions without phrases like "here is the summary" or "this summary shows". Focus on the sentiments expressed.
The "pros" should be a list of 1-3 most important positive aspects mentioned in the reviews.
The "cons" should be a list of 1-3 most important negative aspects or issues mentioned in the reviews.
Each point should be specific, concise (under 10 words), and directly taken from the reviews.
If there are no pros or cons, include an empty list.

Your response must be valid JSON only, with no additional text before or after.
"""

    try:
        response = await client.aio.models.generate_content(
            model='gemini-2.0-flash-001',
            contents=prompt,
            config=GenerateContentConfig(
                max_output_tokens=1000,
                temperature=0.2,
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
            return ReviewSummaryOutput.model_validate(response_data)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {str(e)}")
            logger.debug(f"Response text: {response.text}")
            
            # Fallback to manually creating the structure
            return ReviewSummaryOutput(
                summary=response.text,
                pros=["Unable to extract structured pros from AI response"],
                cons=["Unable to extract structured cons from AI response"]
            )
            
    except Exception as e:
        logger.error(f"Error generating review summary: {str(e)}")
        return ReviewSummaryOutput(
            summary="Failed to generate review summary. Please try again later.",
            pros=[],
            cons=[]
        )

async def generate_fake_reviews_and_summary(product_id: str, session: Optional[AsyncSession] = None, tenant: str = None) -> GeneratedReviewsOutput:
    """
    Generate fake reviews and summary for a product using Gemini AI.
    
    Args:
        product_id: ID of the product to generate reviews for
        session: Optional database session
        tenant: Database schema to use
        
    Returns:
        GeneratedReviewsOutput: Structured output with reviews and summary
    """
    client = get_genai_client()
    
    # Fetch product custom data if session is provided
    product_custom_data = None
    if session and tenant:
        try:
            # Get only custom_data from database
            query = text(f"SELECT custom_data FROM {tenant}.products WHERE id = :product_id")
            result = await session.execute(query, {"product_id": product_id})
            custom_data = result.scalar_one_or_none()
            
            if custom_data:
                product_custom_data = custom_data
        except Exception as e:
            logger.error(f"Error fetching product custom_data with ID {product_id}: {str(e)}")
    
    # Generate random ratio of good, mixed, and bad reviews
    # Possible distributions: [good, mixed, bad]
    review_distributions = [
        [4, 1, 1],  # Mostly positive
        [3, 2, 1],  # Positive leaning
        [2, 2, 2],  # Balanced
        [2, 3, 1],  # Mixed leaning
        [1, 2, 3],  # Negative leaning
        [1, 1, 4],  # Mostly negative
    ]
    
    distribution = random.choice(review_distributions)
    good_count, mixed_count, bad_count = distribution
    
    # Construct the prompt
    product_context = ""
    if product_custom_data:
        product_context = f"Product details: {json.dumps(product_custom_data)}"
    
    prompt = f"""Generate 6 realistic customer reviews for the following product and provide a summary:

{product_context}

Generate exactly {good_count} positive reviews, {mixed_count} mixed reviews, and {bad_count} negative reviews.

Each review should:
- Be 2-4 sentences long
- Sound like a real customer wrote it
- Include specific details about the product
- Have varied writing styles and perspectives
- Include both pros and cons where appropriate

Provide a response in JSON format with the following structure:
{{
  "reviews": [
    {{"content": "review text here", "sentiment": "positive"}},
    {{"content": "review text here", "sentiment": "mixed"}},
    {{"content": "review text here", "sentiment": "negative"}},
    // ... 6 reviews total
  ],
  "summary": {{
    "summary": "A brief 2-3 sentence summary of the overall sentiment",
    "pros": ["pro point 1", "pro point 2", "pro point 3"],
    "cons": ["con point 1", "con point 2", "con point 3"]
  }}
}}

The "summary" should be a direct and concise overview of customer opinions without phrases like "here is the summary" or "this summary shows". Focus on the sentiments expressed.
The "pros" should be a list of 1-3 most important positive aspects mentioned in the reviews.
The "cons" should be a list of 1-3 most important negative aspects or issues mentioned in the reviews.
Each point should be specific, concise (under 10 words), and directly taken from the reviews.
If there are no pros or cons, include an empty list.

Your response must be valid JSON only, with no additional text before or after.
"""

    try:
        response = await client.aio.models.generate_content(
            model='gemini-2.0-flash-001',
            contents=prompt,
            config=GenerateContentConfig(
                max_output_tokens=2000,
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
            return GeneratedReviewsOutput.model_validate(response_data)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {str(e)}")
            logger.debug(f"Response text: {response.text}")
            
            # Fallback to manually creating the structure
            fallback_reviews = [
                {"content": "Unable to generate review content", "sentiment": "mixed"}
                for _ in range(6)
            ]
            fallback_summary = ReviewSummaryOutput(
                summary="Unable to generate review summary from AI response",
                pros=["Unable to extract structured pros"],
                cons=["Unable to extract structured cons"]
            )
            
            return GeneratedReviewsOutput(
                reviews=fallback_reviews,
                summary=fallback_summary
            )
            
    except Exception as e:
        logger.error(f"Error generating fake reviews: {str(e)}")
        
        # Fallback to basic structure
        fallback_reviews = [
            {"content": "Failed to generate review content. Please try again later.", "sentiment": "mixed"}
            for _ in range(6)
        ]
        fallback_summary = ReviewSummaryOutput(
            summary="Failed to generate review summary. Please try again later.",
            pros=[],
            cons=[]
        )
        
        return GeneratedReviewsOutput(
            reviews=fallback_reviews,
            summary=fallback_summary
        ) 