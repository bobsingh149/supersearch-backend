import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging

# Get logger instead of configuring it here
# This will use the configuration from main.py
logger = logging.getLogger(__name__)

class RequestTimingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Record start time
        start_time = time.time()
        
        # Process the request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Log the request details
        logger.info(
            f"Path: {request.url.path} | "
            f"Method: {request.method} | "
            f"Processing Time: {process_time:.2f}ms"
        )
        
        return response
