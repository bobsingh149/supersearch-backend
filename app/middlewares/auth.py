from fastapi import Request
import jwt
import os
import logging
from typing import Callable, List
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from datetime import datetime
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.public_key = os.getenv("CLERK_PEM_PUBLIC_KEY")
        if not self.public_key:
            logger.error("CLERK_PEM_PUBLIC_KEY environment variable not found")
            raise ValueError("CLERK_PEM_PUBLIC_KEY environment variable not found")
        self.permitted_origins = ["http://localhost:5173", "http://localhost:3000",  "http://localhost:9000", "https://api.cognishop.co", "https://dashboard.cognishop.co", "https://www.cognishop.co"]
        
        # List of public endpoints that don't require authentication
        self.public_endpoints = [
            "/health",
            "/docs",
            "/openapi.json",
            "/v1/auth/public",
            "/v1/leads",
            "/v1/shopping-assistant/chat",
            "/v1/search",
            "/v1/reviews"
        ]

    def verify_api_key(self, key: str) -> bool:
        """Verify if the provided API key matches the expected value."""
        return key == "uxqZuxesLl4Y6p2"
    
    def is_public_path(self, path: str) -> bool:
        """Check if the requested path is public and doesn't require authentication."""
        # Check exact matches
        if path in self.public_endpoints:
            return True
        
        # Check path prefixes
        for endpoint in self.public_endpoints:
            if path.startswith(endpoint):
                return True
        
        return False

    async def dispatch(self, request: Request, call_next: Callable):
        try:
            # Skip auth for public endpoints and OPTIONS requests
            if self.is_public_path(request.url.path) or request.method == "OPTIONS":
                return await call_next(request)

            # First check for X-API-Key header
            api_key = request.headers.get("X-API-Key")
            if api_key:
                if self.verify_api_key(api_key):
                    # Set a dummy user ID for API key authentication
                    request.state.user_id = "api_key_user"
                    request.state.user_payload = {"sub": "api_key_user", "type": "api_key"}
                    return await call_next(request)
                else:
                    return JSONResponse(
                        status_code=401, 
                        content={"detail": "Invalid API key"}
                    )

            # If no API key, check for Authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return JSONResponse(
                    status_code=401, 
                    content={"detail": "Missing or invalid Authorization header"}
                )
            
            session_token = auth_header.split(" ")[1]
            
            try:
                # Verify the JWT
                decoded = jwt.decode(session_token, self.public_key, algorithms=["RS256"])
                
                # Validate token expiration and not-before claims
                current_time = int(datetime.now().timestamp())
                if decoded.get("exp") < current_time:
                    return JSONResponse(
                        status_code=401, 
                        content={"detail": "Token expired"}
                    )
                
                if decoded.get("nbf") and decoded.get("nbf") > current_time:
                    return JSONResponse(
                        status_code=401, 
                        content={"detail": "Token not yet valid"}
                    )
                
                # Validate authorized party
                if decoded.get("azp") and decoded.get("azp") not in self.permitted_origins:
                    return JSONResponse(
                        status_code=401, 
                        content={"detail": "Invalid authorized party"}
                    )
                
                # Add user info to request state for access in route handlers
                request.state.user_id = decoded.get("sub")
                request.state.user_payload = decoded

            except jwt.PyJWTError as e:
                logger.error(f"JWT verification error: {str(e)}")
                return JSONResponse(
                    status_code=401, 
                    content={"detail": str(e)}
                )
            
            return await call_next(request)
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return JSONResponse(
                status_code=500, 
                content={"detail": "Internal server error during authentication"}
            ) 