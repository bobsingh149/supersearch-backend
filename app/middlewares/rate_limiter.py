from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from typing import Dict, Set, Optional, Callable, List
import logging
from datetime import datetime
from sqlalchemy.future import select
from sqlalchemy.dialects.postgresql import insert
from app.database.session import get_async_session_with_contextmanager
from app.models.rate_limit import RateLimitDB
import asyncio

logger = logging.getLogger(__name__)

# Shared request counts dictionary across all instances
REQUEST_COUNTS: Dict[str, int] = {}
INITIALIZATION_LOCK = asyncio.Lock()
INITIALIZED = False

# Set of IP addresses that are excluded from rate limiting
EXCLUDED_IPS: Set[str] = {"106.221.198.120","127.0.0.1"}

class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, 
        app, 
        max_requests: int = 10,
        limited_paths: Set[str] = None,
        get_path_identifier: Optional[Callable[[str], str]] = None,
        excluded_ips: Set[str] = None
    ):
        super().__init__(app)
        self.max_requests = max_requests
        # Use the shared module-level request counts
        self.limited_paths = limited_paths or set()
        self.get_path_identifier = get_path_identifier or (lambda path: path)
        self.excluded_ips = excluded_ips or EXCLUDED_IPS

    def get_tenant_from_headers(self, request: Request) -> str:
        """Get tenant from request headers"""
        
        # Check for tenant header (case-insensitive)
        tenant = request.headers.get("tenant") or request.headers.get("Tenant") or request.headers.get("X-Tenant")
        
        if not tenant:
            raise ValueError("Tenant header is required but not provided")
        
        return tenant.strip()

    @staticmethod
    async def initialize_from_db():
        """Load existing rate limits from database on startup"""
        global INITIALIZED
        if INITIALIZED:
            return

        async with INITIALIZATION_LOCK:
            if INITIALIZED:  # Double-check lock pattern
                return

            logger.info("Initializing rate limiter from database...")
            try:
                async with get_async_session_with_contextmanager(tenant="public") as session:
                    result = await session.execute(select(RateLimitDB))
                    rate_limits = result.scalars().all()

                    for rate_limit in rate_limits:
                        REQUEST_COUNTS[rate_limit.ip_address] = rate_limit.request_count

                    logger.info(f"Loaded {len(rate_limits)} rate limits from database")
                    INITIALIZED = True
            except Exception as e:
                logger.error(f"Failed to initialize rate limiter from database: {str(e)}")
                # Continue without data from database
                INITIALIZED = True  # Mark as initialized to prevent retry loops

    @staticmethod
    async def save_to_db():
        """Save current rate limits to database"""
        logger.info("Saving rate limits to database...")
        try:
            async with get_async_session_with_contextmanager(tenant="public") as session:
                for ip_address, count in REQUEST_COUNTS.items():
                    # Use PostgreSQL insert ... on conflict
                    stmt = insert(RateLimitDB).values(
                        ip_address=ip_address,
                        request_count=count,
                        last_request_time=datetime.now()
                    ).on_conflict_do_update(
                        index_elements=['ip_address'],
                        set_=dict(
                            request_count=count,
                            last_request_time=datetime.now()
                        )
                    )
                    await session.execute(stmt)
                await session.commit()
                logger.info(f"Saved {len(REQUEST_COUNTS)} rate limits to database")
        except Exception as e:
            logger.error(f"Failed to save rate limits to database: {str(e)}")
    
    def get_client_ip(self, request: Request) -> str:
        """Get client IP address, checking headers for forwarded IP"""
        # Check for X-Forwarded-For header first (common in proxied environments)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs; the client IP is the first one
            return forwarded_for.split(",")[0].strip()
        
        # Check for X-Real-IP header (used by some proxies)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to client.host when not using a reverse proxy
        try:
            if request.client and hasattr(request.client, 'host') and request.client.host:
                return request.client.host
        except Exception as e:
            logger.warning(f"Failed to get client IP from request.client: {str(e)}")
        
        # Final fallback for cases where client information is not available
        return "unknown"
    
    def should_rate_limit(self, path: str) -> bool:
        """Determine if the request path should be rate limited"""
        # Skip rate limiting for v1/leads routes
        if path.startswith("/v1/leads"):
            return False
            
        path_identifier = self.get_path_identifier(path)
        return path_identifier in self.limited_paths
    
    @staticmethod
    def add_excluded_ip(ip_address: str) -> None:
        """Add an IP address to the exclusion list"""
        EXCLUDED_IPS.add(ip_address)
        logger.info(f"Added {ip_address} to rate limit exclusion list")
    
    @staticmethod
    def remove_excluded_ip(ip_address: str) -> bool:
        """Remove an IP address from the exclusion list"""
        if ip_address in EXCLUDED_IPS:
            EXCLUDED_IPS.remove(ip_address)
            logger.info(f"Removed {ip_address} from rate limit exclusion list")
            return True
        return False
    
    @staticmethod
    def get_excluded_ips() -> List[str]:
        """Get list of all excluded IP addresses"""
        return list(EXCLUDED_IPS)
    
    async def dispatch(self, request: Request, call_next):

        # Skip rate limiting for OPTIONS requests
        if request.method == "OPTIONS":
            return await call_next(request)

        # Get tenant from request headers
        try:
            tenant = self.get_tenant_from_headers(request)
            request.state.tenant = tenant
        except ValueError as e:
            logger.error(f"Missing tenant header: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Tenant header is required"}
            )

        # Ensure initialized from database
        if not INITIALIZED:
            await self.initialize_from_db()
        

        # TODO: Uncomment to enable selective rate limiting
       
        # Check if path should be rate limited
        # if not self.should_rate_limit(request.url.path):
        #     return await call_next(request)
        
        # Get client IP address
        client_ip = self.get_client_ip(request)
        
        # Skip rate limiting for excluded IPs
        if client_ip in self.excluded_ips:
            logger.debug(f"IP {client_ip} is excluded from rate limiting")
            request.state.client_ip = client_ip
            return await call_next(request)
        
        # Check current request count for this IP
        current_count = REQUEST_COUNTS.get(client_ip, 0)
        
        # If the request count exceeds the limit, return 429 Too Many Requests
        if current_count >= self.max_requests:
            logger.warning(f"Rate limit exceeded for IP {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"error": "Rate limit exceeded. Please try again later."}
            )
        
        # Otherwise, increment the request count and allow the request
        REQUEST_COUNTS[client_ip] = current_count + 1
        logger.debug(f"Request count for IP {client_ip}: {current_count + 1}")
        
        request.state.client_ip = client_ip
        # Process the request
        response = await call_next(request)
        
        return response 