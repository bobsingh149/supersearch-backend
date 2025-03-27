from fastapi import Request, HTTPException
from clerk_backend_api import Clerk
import os
import logging
from typing import Callable

logger = logging.getLogger(__name__)

class ClerkAuthMiddleware:
    def __init__(self):
        self.clerk_api_key = os.getenv("CLERK_API_KEY")
        if not self.clerk_api_key:
            logger.error("CLERK_API_KEY environment variable not found")
            raise ValueError("CLERK_API_KEY environment variable not found")
        self.clerk = Clerk(api_key=self.clerk_api_key)
    
    async def __call__(self, request: Request, call_next: Callable):
        # Skip auth for public endpoints
        if request.url.path in ["/health", "/api/docs", "/openapi.json"] or request.url.path.startswith("/api/v1/public"):
            return await call_next(request)
        
        # Extract the session token from the Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        session_token = auth_header.split(" ")[1]
        
        # Verify the session token with Clerk
        try:
            session = self.clerk.sessions.verify(session_token)
            if not session or not session.is_valid:
                raise HTTPException(status_code=401, detail="Invalid session")
            
            # Add user info to request state for access in route handlers
            request.state.user_id = session.user_id
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise HTTPException(status_code=401, detail=str(e))
        
        return await call_next(request) 