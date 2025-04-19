import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
import logging
from starlette.middleware.cors import CORSMiddleware
import logging.handlers
import os

from starlette.responses import StreamingResponse

from app.core.settings import settings
from app.services.vertex import get_embedding
from app.routes import organization, product, recommend, search_product, shopping_assistant, sync_product, settings, sync_history, auth, lead
from app.database.session import check_db_connection
from dotenv import load_dotenv
from app.middlewares.route_logging import RequestTimingMiddleware
from app.middlewares.auth import AuthMiddleware
from app.middlewares.rate_limiter import RateLimiterMiddleware

load_dotenv()

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # Console handler
        logging.StreamHandler(),
        # File handler - rotating file handler to prevent logs from growing too large
        logging.handlers.RotatingFileHandler(
            'logs/server.log',
            maxBytes=10485760,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
    ]
)
logger = logging.getLogger(__name__)

# Define rate-limited paths
RATE_LIMITED_PATHS = {
    "/v1/shopping-assistant/chat",
    "/v1/search"
}

# Create a standalone rate limiter to be used in lifespan
rate_limiter = RateLimiterMiddleware(None, max_requests=10, limited_paths=RATE_LIMITED_PATHS)

async def initialize_server():
    """Initialize all necessary components for server startup"""
    logger.info("Initializing model and processor...")
    # Check database connection
    if not await check_db_connection():
        logger.error("Database connection failed")
        raise RuntimeError("Database connection failed")
    logger.info("Database connection successful")
    
    await get_embedding("cognishop")
    logger.info("Initialization complete.")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize model and processor on startup"""
    await initialize_server()
    
    # Initialize rate limiter from database
    await rate_limiter.initialize_from_db()
    
    yield
    
    # Save rate limiter data to database when server shuts down
    logger.info("Saving rate limiter data to database before shutdown")
    await rate_limiter.save_to_db()
    
    logger.info("Shutting down...")

app = FastAPI(lifespan=lifespan)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(AuthMiddleware)

# Add rate limiter middleware
app.add_middleware(
    RateLimiterMiddleware,
    max_requests=30,
    limited_paths=RATE_LIMITED_PATHS
)

# Include all routers
API_V1_PREFIX = "/v1"

app.include_router(organization.router, prefix=API_V1_PREFIX)
app.include_router(product.router, prefix=API_V1_PREFIX)
app.include_router(recommend.router, prefix=API_V1_PREFIX)
app.include_router(search_product.router, prefix=API_V1_PREFIX)
app.include_router(settings.router, prefix=API_V1_PREFIX)
app.include_router(shopping_assistant.router, prefix=API_V1_PREFIX)
app.include_router(sync_product.router, prefix=API_V1_PREFIX)
app.include_router(sync_history.router, prefix=API_V1_PREFIX)
app.include_router(auth.router, prefix=API_V1_PREFIX)
app.include_router(lead.router, prefix=API_V1_PREFIX)


@app.get("/health",operation_id="root")
def read_root()->dict:
    """health check route"""
    return {"message": "server is healthy!"}


