"""LLM service for bulk SEO generation."""
import logging
import asyncio
from typing import Dict, Any, Optional, List
from enum import Enum

from google.genai.types import GenerationConfig

from app.services.vertex import get_genai_client
from app.core.appsettings import app_settings

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None

logger = logging.getLogger(__name__)


class SEOTone(str, Enum):
    """Available tones for SEO content generation."""
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    CASUAL = "casual"
    PERSUASIVE = "persuasive"
    LUXURY = "luxury"
    TECHNICAL = "technical"


class SEOLength(str, Enum):
    """Available length options for SEO content."""
    BRIEF = "brief"          # 50-100 words
    STANDARD = "standard"    # 100-150 words
    DETAILED = "detailed"    # 150-250 words
    COMPREHENSIVE = "comprehensive"  # 250+ words


class LLMProvider(str, Enum):
    """Available LLM providers."""
    GEMINI = "gemini"
    OPENAI = "openai"


class LLMModel(str, Enum):
    """Available LLM models."""
    GEMINI_2_0_FLASH_001 = "gemini-2.0-flash-001"
    GPT_5_MINI = "gpt-5-mini"


class BulkSEOLLMService:
    """
    Service for generating SEO-optimized product descriptions using LLM.

    Supports multiple providers:
    - Google Gemini (2.0 Flash-001)
    - OpenAI GPT-4o Mini

    Usage examples:
        # Use Gemini 2.0 Flash-001 (default)
        service = BulkSEOLLMService()

        # Use Gemini 2.0 Flash-001 explicitly
        service = BulkSEOLLMService(provider=LLMProvider.GEMINI, model=LLMModel.GEMINI_2_0_FLASH_001)

        # Use OpenAI GPT-4o Mini
        service = BulkSEOLLMService(provider=LLMProvider.OPENAI, model=LLMModel.GPT_5_MINI)
    """

    def __init__(self, provider: LLMProvider = LLMProvider.GEMINI, model: LLMModel = LLMModel.GEMINI_2_0_FLASH_001):
        """
        Initialize the LLM service.

        Args:
            provider: LLM provider to use (gemini or openai)
            model: Specific model to use
        """
        # Validate model-provider compatibility
        if not self.validate_model_provider(provider, model):
            raise ValueError(f"Model {model.value} is not compatible with provider {provider.value}")

        self.provider = provider
        self.model = model

        if provider == LLMProvider.GEMINI:
            self.client = get_genai_client()
            # Gemini generation configuration
            self.generation_config = GenerationConfig(
                temperature=0.7,
                top_p=0.9,
                top_k=40,
                max_output_tokens=1000,
                response_mime_type="text/plain"
            )
        elif provider == LLMProvider.OPENAI:
            if not OPENAI_AVAILABLE:
                raise ImportError("OpenAI package is not installed. Please install it to use OpenAI models.")
            self.client = openai.AsyncClient(api_key=app_settings.openai_api_key if hasattr(app_settings, 'openai_api_key') else None)
            self.generation_config = None  # OpenAI uses different config approach
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        logger.info(f"Initialized LLM service with provider: {provider.value}, model: {model.value}")

    @classmethod
    def get_available_models(cls, provider: LLMProvider) -> List[LLMModel]:
        """
        Get available models for a specific provider.

        Args:
            provider: LLM provider

        Returns:
            List of available models for the provider
        """
        if provider == LLMProvider.GEMINI:
            return [LLMModel.GEMINI_2_0_FLASH_001]
        elif provider == LLMProvider.OPENAI:
            return [LLMModel.GPT_5_MINI]
        else:
            return []

    @classmethod
    def validate_model_provider(cls, provider: LLMProvider, model: LLMModel) -> bool:
        """
        Validate that a model is compatible with a provider.

        Args:
            provider: LLM provider
            model: Model to validate

        Returns:
            True if compatible, False otherwise
        """
        available_models = cls.get_available_models(provider)
        return model in available_models

    async def generate_product_description(
        self,
        product_data: Dict[str, Any],
        tone: str = "professional",
        word_count: int = 150,
        custom_prompt: Optional[str] = None,
        example: Optional[str] = None
    ) -> str:
        """
        Generate SEO-optimized product description using LLM.

        Args:
            product_data: Shopify product data
            tone: Writing tone for the description
            word_count: Target word count
            custom_prompt: Custom prompt instructions
            example: Example description for style reference

        Returns:
            Generated product description
        """
        try:
            # Build the comprehensive prompt
            prompt = self._build_seo_prompt(
                product_data=product_data,
                tone=tone,
                word_count=word_count,
                custom_prompt=custom_prompt,
                example=example
            )
            
            logger.debug(f"Generating description for product: {product_data.get('title', 'Unknown')}")

            # Generate content based on provider
            if self.provider == LLMProvider.GEMINI:
                response = await self.client.agenerate_content(
                    model=self.model.value,
                    contents=prompt,
                    config=self.generation_config
                )
                generated_text = response.text.strip() if response and response.text else ""
            elif self.provider == LLMProvider.OPENAI:
                response = await self.client.chat.completions.create(
                    model=self.model.value,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=1000,
                    top_p=0.9
                )
                generated_text = response.choices[0].message.content.strip() if response.choices else ""

            # Check if we got a response
            if not generated_text:
                raise Exception("Empty response from LLM")

            # Post-process the generated content
            processed_description = self._post_process_description(
                generated_text,
                word_count,
                tone
            )

            logger.info(f"Successfully generated description for product: {product_data.get('title', 'Unknown')} using {self.provider.value}")
            return processed_description
                
        except Exception as e:
            logger.error(f"Error generating description for product {product_data.get('id', 'Unknown')}: {str(e)}")
            raise
    
    def _build_seo_prompt(
        self,
        product_data: Dict[str, Any],
        tone: str,
        word_count: int,
        custom_prompt: Optional[str] = None,
        example: Optional[str] = None
    ) -> str:
        """
        Build a comprehensive SEO-focused prompt for product description generation.
        """
        # Extract key product information
        title = product_data.get('title', 'Product')
        description = product_data.get('description', '')
        product_type = product_data.get('productType', '')
        vendor = product_data.get('vendor', '')
        tags = product_data.get('tags', [])
        
        # Extract price information
        price_info = self._extract_price_info(product_data.get('priceRangeV2', {}))
        
        # Extract variant information
        variants_info = self._extract_variants_info(product_data.get('variants', {}).get('nodes', []))
        
        # Extract collections
        collections = [col.get('title', '') for col in product_data.get('collections', {}).get('nodes', [])]
        
        # Extract category information
        category_info = product_data.get('category', {})
        category_name = category_info.get('fullName', category_info.get('name', ''))
        
        # Extract media information
        media_info = self._extract_media_info(product_data.get('media', {}).get('nodes', []))
        
        # Build the main prompt
        prompt = f"""You are an expert e-commerce copywriter specializing in SEO-optimized product descriptions. 

PRODUCT INFORMATION:
- Title: {title}
- Brand/Vendor: {vendor}
- Product Type: {product_type}
- Category: {category_name}
- Current Description: {description if description else 'No existing description'}
- Price: {price_info}
- Collections: {', '.join(collections) if collections else 'None'}
- Tags: {', '.join(tags) if tags else 'None'}
- Available Variants: {variants_info}
- Media: {media_info}

WRITING REQUIREMENTS:
- Tone: {tone.title()} (write in a {tone} manner that matches this tone throughout)
- Target Length: Approximately {word_count} words
- Focus: SEO optimization with natural keyword integration
- Format: Clean, readable paragraphs suitable for e-commerce

SEO GUIDELINES:
1. Naturally incorporate the product title and key terms
2. Include relevant keywords from the product type and category
3. Mention the brand/vendor naturally
4. Highlight unique selling points and benefits
5. Use action-oriented language to encourage purchases
6. Include relevant product attributes and features
7. Make it scannable with good flow

CONTENT STRUCTURE:
1. Opening hook that captures attention
2. Key features and benefits
3. Product details and specifications (if applicable)
4. Call-to-action or closing statement

"""

        # Add custom instructions if provided
        if custom_prompt:
            prompt += f"\nADDITIONAL INSTRUCTIONS:\n{custom_prompt}\n"
        
        # Add example style reference if provided
        if example:
            prompt += f"\nSTYLE REFERENCE:\nUse this example as a style guide (but don't copy content):\n{example}\n"
        
        
        prompt += f"""
FINAL INSTRUCTIONS:
- Write ONLY the product description, no additional text or explanations
- Ensure the description is exactly what would appear on a product page
- Make it compelling, informative, and SEO-friendly
- Target approximately {word_count} words
- Use {tone} tone throughout
- Focus on converting browsers into buyers

Generate the SEO-optimized product description now:"""
        
        return prompt
    
    def _extract_price_info(self, price_range: Dict[str, Any]) -> str:
        """Extract and format price information."""
        if not price_range:
            return "Price available upon request"
        
        min_price = price_range.get('minVariantPrice', {})
        max_price = price_range.get('maxVariantPrice', {})
        
        min_amount = min_price.get('amount', '')
        max_amount = max_price.get('amount', '')
        currency = min_price.get('currencyCode', 'USD')
        
        if min_amount == max_amount:
            return f"{currency} {min_amount}"
        else:
            return f"{currency} {min_amount} - {max_amount}"
    
    def _extract_variants_info(self, variants: List[Dict[str, Any]]) -> str:
        """Extract variant information for the prompt."""
        if not variants:
            return "Single variant available"
        
        variant_details = []
        for variant in variants[:5]:  # Limit to first 5 variants
            title = variant.get('title', '')
            if title and title != 'Default Title':
                variant_details.append(title)
        
        if variant_details:
            return f"{len(variants)} variants: {', '.join(variant_details)}"
        else:
            return f"{len(variants)} variants available"
    
    def _extract_media_info(self, media: List[Dict[str, Any]]) -> str:
        """Extract media information for context."""
        if not media:
            return "No media available"
        
        image_count = sum(1 for m in media if 'image' in m)
        video_count = sum(1 for m in media if 'sources' in m)
        
        media_info = []
        if image_count:
            media_info.append(f"{image_count} images")
        if video_count:
            media_info.append(f"{video_count} videos")
        
        return ', '.join(media_info) if media_info else "Media available"
    
    def _post_process_description(
        self,
        generated_text: str,
        target_word_count: int,
        tone: str
    ) -> str:
        """
        Post-process the generated description to ensure quality.
        """
        # Remove any unwanted prefixes or suffixes
        text = generated_text.strip()
        
        # Remove common AI-generated prefixes
        unwanted_prefixes = [
            "Here's a product description:",
            "Product Description:",
            "Description:",
            "Here is the product description:",
            "SEO-optimized description:",
        ]
        
        for prefix in unwanted_prefixes:
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].strip()
        
        # Ensure proper paragraph structure
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        text = '\n\n'.join(paragraphs)
        
        # Basic word count check (allow some flexibility)
        word_count = len(text.split())
        if abs(word_count - target_word_count) > target_word_count * 0.3:  # 30% tolerance
            logger.warning(f"Generated description word count ({word_count}) differs significantly from target ({target_word_count})")
        
        return text
    
    async def generate_batch_descriptions(
        self,
        products_data: List[Dict[str, Any]],
        user_settings: Dict[str, Any],
        max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Generate descriptions for multiple products concurrently.
        
        Args:
            products_data: List of product data dictionaries
            user_settings: User's AI generation settings
            max_concurrent: Maximum concurrent requests
            
        Returns:
            List of results with product_id, status, description, and error (if any)
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def generate_single_product(product_data: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                try:
                    description = await self.generate_product_description(
                        product_data=product_data,
                        tone=user_settings.get('tone', 'professional'),
                        word_count=user_settings.get('word_count', 150),
                        custom_prompt=user_settings.get('custom_prompt'),
                        example=user_settings.get('example')
                    )
                    
                    return {
                        'product_id': product_data.get('id', ''),
                        'status': 'success',
                        'description': description,
                        'error': None
                    }
                    
                except Exception as e:
                    return {
                        'product_id': product_data.get('id', ''),
                        'status': 'error',
                        'description': None,
                        'error': str(e)
                    }
        
        # Generate descriptions concurrently
        tasks = [generate_single_product(product) for product in products_data]
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r['status'] == 'success')
        logger.info(f"Generated descriptions for {success_count}/{len(products_data)} products")
        
        return results
    
    def get_tone_guidelines(self, tone: str) -> str:
        """Get specific guidelines for different tones."""
        tone_guidelines = {
            "professional": "Use formal language, focus on specifications and quality, avoid casual expressions",
            "friendly": "Use warm, approachable language, include conversational elements, be welcoming",
            "casual": "Use relaxed, everyday language, be conversational and relatable",
            "persuasive": "Use compelling language, emphasize benefits and urgency, include strong calls-to-action",
            "luxury": "Use sophisticated language, emphasize exclusivity and premium quality",
            "technical": "Use precise terminology, focus on specifications and technical details"
        }
        
        return tone_guidelines.get(tone.lower(), "Use clear and engaging language")
    
    def get_word_count_guidelines(self, word_count: int) -> str:
        """Get guidelines based on target word count."""
        if word_count <= 100:
            return "Keep it concise, focus on key selling points, use impactful phrases"
        elif word_count <= 200:
            return "Include key features and benefits, maintain good flow, use descriptive language"
        elif word_count <= 300:
            return "Provide comprehensive details, include specifications, tell a product story"
        else:
            return "Create a detailed narrative, include extensive features, specifications, and use cases"
