from fastapi import Request, HTTPException
import jwt
import os
import logging
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from datetime import datetime

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.public_key = os.getenv("CLERK_PEM_PUBLIC_KEY")
        if not self.public_key:
            logger.error("CLERK_PEM_PUBLIC_KEY environment variable not found")
            raise ValueError("CLERK_PEM_PUBLIC_KEY environment variable not found")
        self.permitted_origins = ["http://localhost:5173", "http://localhost:3000",  "http://localhost:9000", "https://api.cognishop.co", "https://dashboard.cognishop.co", "https://www.cognishop.co"]

    def verify_api_key(self, key: str) -> bool:
        """Verify if the provided API key matches the expected value."""
        return key == "uxqZuxesLl4Y6p2"

    async def dispatch(self, request: Request, call_next: Callable):
        # Skip auth for public endpoints and OPTIONS requests
        if (request.url.path in ["/health", "/docs", "/openapi.json"] or 
            request.url.path.startswith("/api/v1/auth/public") or
            request.method == "OPTIONS"):
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
                raise HTTPException(status_code=401, detail="Invalid API key")

        # If no API key, check for Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        session_token = auth_header.split(" ")[1]
        
        try:
            # Verify the JWT
            decoded = jwt.decode(session_token, self.public_key, algorithms=["RS256"])
            
            # Validate token expiration and not-before claims
            current_time = int(datetime.now().timestamp())
            if decoded.get("exp") < current_time:
                raise HTTPException(status_code=401, detail="Token expired")
            
            if decoded.get("nbf") and decoded.get("nbf") > current_time:
                raise HTTPException(status_code=401, detail="Token not yet valid")
            
            # Validate authorized party
            if decoded.get("azp") and decoded.get("azp") not in self.permitted_origins:
                raise HTTPException(status_code=401, detail="Invalid authorized party")
            
            # Add user info to request state for access in route handlers
            request.state.user_id = decoded.get("sub")
            request.state.user_payload = decoded

            print(request.state.user_payload)
            
        except jwt.PyJWTError as e:
            logger.error(f"JWT verification error: {str(e)}")
            raise HTTPException(status_code=401, detail=str(e))
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise HTTPException(status_code=401, detail=str(e))
        
        return await call_next(request) 