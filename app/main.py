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
from app.routes import organization, product, recommend, search_product, shopping_assistant, sync_product, settings, sync_history, auth
from app.database.session import check_db_connection
from dotenv import load_dotenv
from app.middlewares.route_logging import RequestTimingMiddleware
from app.middlewares.auth import ClerkAuthMiddleware

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
            'logs/supersearch.log',
            maxBytes=10485760,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
    ]
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize model and processor on startup"""
    logger.info("Initializing model and processor...")

    print("\nSettings:")
    print("=" * 50)
    print(settings)
    print("=" * 50)
    print()
    
    # Check database connection
    if not await check_db_connection():
        logger.error("Database connection failed")
        raise RuntimeError("Database connection failed")
    logger.info("Database connection successful")
    
    embedding = await get_embedding("startup")
    logger.info("Initialization complete.")
    
    yield
    
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
app.add_middleware(ClerkAuthMiddleware)

# Include all routers
API_V1_PREFIX = "/api/v1"

app.include_router(organization.router, prefix=API_V1_PREFIX)
app.include_router(product.router, prefix=API_V1_PREFIX)
app.include_router(recommend.router, prefix=API_V1_PREFIX)
app.include_router(search_product.router, prefix=API_V1_PREFIX)
app.include_router(settings.router, prefix=API_V1_PREFIX)
app.include_router(shopping_assistant.router, prefix=API_V1_PREFIX)
app.include_router(sync_product.router, prefix=API_V1_PREFIX)
app.include_router(sync_history.router, prefix=API_V1_PREFIX)
app.include_router(auth.router, prefix=API_V1_PREFIX)


@app.get("/health",operation_id="root")
def read_root()->dict:
    """health check route"""
    return {"message": "server is healthy!"}


