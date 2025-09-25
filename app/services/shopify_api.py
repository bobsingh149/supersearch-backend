"""Shopify API service for GraphQL operations."""
import logging
import aiohttp
import asyncio
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class ShopifyAPIError(Exception):
    """Custom exception for Shopify API errors."""
    pass


class ShopifyAPIService:
    """
    Service for interacting with Shopify GraphQL API.
    """
    
    def __init__(self, access_token: str, shop_domain: Optional[str] = None):
        """
        Initialize Shopify API service.
        
        Args:
            access_token: Shopify access token
            shop_domain: Shop domain (e.g., 'mystore.myshopify.com')
        """
        self.access_token = access_token
        self.shop_domain = shop_domain or self._extract_domain_from_token(access_token)
        self.graphql_url = f"https://{self.shop_domain}/admin/api/2025-07/graphql.json"
        
        self.headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self.access_token
        }
        
        # Rate limiting
        self.rate_limit_remaining = 1000
        self.rate_limit_reset_time = None
    
    def _extract_domain_from_token(self, access_token: str) -> str:
        """
        Extract domain from access token or use default.
        This is a placeholder - in reality, you'd store the domain with the user.
        """
        # This would need to be implemented based on how you store shop domains
        # For now, return a placeholder
        return "your-store.myshopify.com"
    
    async def _execute_graphql_query(
        self, 
        query: str, 
        variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query against Shopify API.
        
        Args:
            query: GraphQL query string
            variables: Query variables
            
        Returns:
            Response data from Shopify API
            
        Raises:
            ShopifyAPIError: If the API request fails
        """
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        # Check rate limits before making request
        await self._check_rate_limits()
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    self.graphql_url, 
                    headers=self.headers, 
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    # Update rate limit info from headers
                    self._update_rate_limits(response.headers)
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        # Check for GraphQL errors
                        if "errors" in data:
                            error_messages = [error.get("message", "Unknown error") for error in data["errors"]]
                            raise ShopifyAPIError(f"GraphQL errors: {', '.join(error_messages)}")
                        
                        return data
                    
                    elif response.status == 429:
                        # Rate limited - wait and retry once
                        await asyncio.sleep(1)
                        return await self._execute_graphql_query(query, variables)
                    
                    else:
                        error_text = await response.text()
                        raise ShopifyAPIError(f"HTTP {response.status}: {error_text}")
                        
            except aiohttp.ClientError as e:
                raise ShopifyAPIError(f"Network error: {str(e)}")
            except asyncio.TimeoutError:
                raise ShopifyAPIError("Request timeout")
    
    def _update_rate_limits(self, headers: Dict[str, str]) -> None:
        """Update rate limit info from response headers."""
        if "X-Shopify-Shop-Api-Call-Limit" in headers:
            limit_info = headers["X-Shopify-Shop-Api-Call-Limit"]
            current, maximum = map(int, limit_info.split("/"))
            self.rate_limit_remaining = maximum - current
    
    async def _check_rate_limits(self) -> None:
        """Check and handle rate limits."""
        if self.rate_limit_remaining <= 5:  # Conservative threshold
            logger.warning("Approaching rate limit, waiting 1 second")
            await asyncio.sleep(1)
    
    async def fetch_products_by_ids(
        self, 
        product_ids: List[str], 
        batch_size: int = 250
    ) -> List[Dict[str, Any]]:
        """
        Fetch products by specific IDs.
        
        Args:
            product_ids: List of product IDs
            batch_size: Number of products per request
            
        Returns:
            List of product data
        """
        products = []
        
        # Process product IDs in batches
        for i in range(0, len(product_ids), batch_size):
            batch_ids = product_ids[i:i + batch_size]
            
            # Build GraphQL query for specific IDs
            id_conditions = " OR ".join([f'\"gid://shopify/Product/{pid}\"' for pid in batch_ids])
            
            query = f"""
            query GetProductsByIds {{
                products(first: {len(batch_ids)}, query: "id:({id_conditions})") {{
                    nodes {{
                        {self._get_product_fields()}
                    }}
                }}
            }}
            """
            
            try:
                response_data = await self._execute_graphql_query(query)
                
                if response_data and 'data' in response_data and 'products' in response_data['data']:
                    nodes = response_data['data']['products']['nodes']
                    products.extend(nodes)
                    
                    logger.info(f"Fetched {len(nodes)} products in batch {i // batch_size + 1}")
                
                # Small delay between batches to be respectful
                if i + batch_size < len(product_ids):
                    await asyncio.sleep(0.1)
                    
            except ShopifyAPIError as e:
                logger.error(f"Error fetching product batch {i // batch_size + 1}: {str(e)}")
                # Continue with other batches
                continue
        
        logger.info(f"Successfully fetched {len(products)} products by ID")
        return products
    
    async def fetch_all_products_paginated(
        self, 
        batch_size: int = 250,
        max_products: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch all products using pagination.
        
        Args:
            batch_size: Number of products per request
            max_products: Maximum number of products to fetch (None for all)
            
        Returns:
            List of product data
        """
        products = []
        has_next_page = True
        cursor = None
        
        while has_next_page and (max_products is None or len(products) < max_products):
            # Adjust batch size if we're near the limit
            if max_products and len(products) + batch_size > max_products:
                batch_size = max_products - len(products)
            
            # Build pagination query
            after_clause = f', after: "{cursor}"' if cursor else ""
            
            query = f"""
            query GetAllProducts {{
                products(first: {batch_size}{after_clause}) {{
                    edges {{
                        cursor
                        node {{
                            {self._get_product_fields()}
                        }}
                    }}
                    pageInfo {{
                        hasNextPage
                    }}
                }}
            }}
            """
            
            try:
                response_data = await self._execute_graphql_query(query)
                
                if response_data and 'data' in response_data and 'products' in response_data['data']:
                    edges = response_data['data']['products']['edges']
                    page_info = response_data['data']['products']['pageInfo']
                    
                    # Extract products and update cursor
                    for edge in edges:
                        products.append(edge['node'])
                        cursor = edge['cursor']
                    
                    has_next_page = page_info.get('hasNextPage', False)
                    
                    logger.info(f"Fetched {len(edges)} products, total: {len(products)}")
                else:
                    break
                
                # Small delay between requests
                await asyncio.sleep(0.1)
                
            except ShopifyAPIError as e:
                logger.error(f"Error fetching products page: {str(e)}")
                break
        
        logger.info(f"Successfully fetched {len(products)} products total")
        return products
    
    def _get_product_fields(self) -> str:
        """
        Get the GraphQL fields to fetch for products.
        Returns all fields useful for AI generation.
        """
        return """
            id
            legacyResourceId
            title
            description(truncateAt: 2000)
            descriptionHtml
            handle
            productType
            vendor
            tags
            status
            createdAt
            updatedAt
            publishedAt
            category {
                id
                name
                fullName
            }
            seo {
                title
                description
            }
            priceRangeV2 {
                minVariantPrice {
                    amount
                    currencyCode
                }
                maxVariantPrice {
                    amount
                    currencyCode
                }
            }
            compareAtPriceRange {
                minVariantPrice {
                    amount
                    currencyCode
                }
                maxVariantPrice {
                    amount
                    currencyCode
                }
            }
            variants(first: 10) {
                nodes {
                    id
                    legacyResourceId
                    title
                    price
                    compareAtPrice
                    availableForSale
                    inventoryQuantity
                    weight
                    weightUnit
                    sku
                    barcode
                    selectedOptions {
                        name
                        value
                    }
                }
            }
            media(first: 5) {
                nodes {
                    ... on MediaImage {
                        id
                        image {
                            url
                            altText
                            width
                            height
                        }
                    }
                    ... on Video {
                        id
                        sources {
                            url
                            mimeType
                        }
                    }
                }
            }
            options {
                id
                name
                values
            }
            collections(first: 5) {
                nodes {
                    id
                    title
                    handle
                }
            }
            metafields(first: 10) {
                nodes {
                    id
                    namespace
                    key
                    value
                    type
                }
            }
            totalInventory
            tracksInventory
            onlineStoreUrl
            featuredMedia {
                ... on MediaImage {
                    image {
                        url
                        altText
                    }
                }
            }
        """
    
    async def update_product_description(
        self, 
        product_id: str, 
        description_html: str
    ) -> bool:
        """
        Update a product's description.
        
        Args:
            product_id: Product ID (including gid prefix)
            description_html: New description HTML
            
        Returns:
            True if successful
        """
        mutation = """
        mutation UpdateProduct($input: ProductInput!) {
            productUpdate(input: $input) {
                product {
                    id
                    descriptionHtml
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        variables = {
            "input": {
                "id": product_id,
                "descriptionHtml": description_html
            }
        }
        
        try:
            response_data = await self._execute_graphql_query(mutation, variables)
            
            if response_data and 'data' in response_data:
                update_result = response_data['data']['productUpdate']
                
                if update_result['userErrors']:
                    error_messages = [error['message'] for error in update_result['userErrors']]
                    raise ShopifyAPIError(f"Product update errors: {', '.join(error_messages)}")
                
                logger.info(f"Successfully updated product {product_id}")
                return True
            
            return False
            
        except ShopifyAPIError as e:
            logger.error(f"Error updating product {product_id}: {str(e)}")
            raise
    
    async def get_shop_info(self) -> Dict[str, Any]:
        """
        Get basic shop information.
        
        Returns:
            Shop information
        """
        query = """
        query GetShopInfo {
            shop {
                id
                name
                email
                domain
                myshopifyDomain
                primaryDomain {
                    host
                    url
                }
                currencyCode
                timezoneAbbreviation
                plan {
                    displayName
                }
            }
        }
        """
        
        try:
            response_data = await self._execute_graphql_query(query)
            
            if response_data and 'data' in response_data and 'shop' in response_data['data']:
                return response_data['data']['shop']
            
            return {}
            
        except ShopifyAPIError as e:
            logger.error(f"Error fetching shop info: {str(e)}")
            raise
