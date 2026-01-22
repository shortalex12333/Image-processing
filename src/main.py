"""
Image Processing Service - FastAPI Application Entry Point
Last deployment: 2026-01-22 14:37 UTC (Supabase client auth)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.logger import get_logger, configure_logging
from src.models.common import ErrorResponse

# Configure logging
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Image Processing Service starting", extra={
        "environment": settings.environment,
        "log_level": settings.log_level
    })

    yield

    # Shutdown
    logger.info("Image Processing Service shutting down")


# Create FastAPI app
app = FastAPI(
    title="Image Processing Service",
    description="Cloud_PMS Image Processing & OCR Backend",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [settings.render_service_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.error("Unhandled exception", extra={
        "path": request.url.path,
        "method": request.method,
        "error": str(exc)
    }, exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error_code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            details={"error": str(exc)} if settings.is_development else {}
        ).model_dump()
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.environment
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Image Processing Service",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


# Import and include routers
from src.routes.upload_routes import router as upload_router
from src.routes.session_routes import router as session_router
from src.routes.commit_routes import router as commit_router
from src.routes.label_routes import router as label_router
from src.routes.photo_routes import router as photo_router
from src.routes.label_generation_routes import router as label_generation_router

app.include_router(upload_router, prefix="/api/v1", tags=["upload"])
app.include_router(session_router, prefix="/api/v1", tags=["sessions"])
app.include_router(commit_router, prefix="/api/v1", tags=["commit"])
app.include_router(label_router, prefix="/api/v1", tags=["shipping-labels"])
app.include_router(photo_router, prefix="/api/v1", tags=["photos"])
app.include_router(label_generation_router, prefix="/api/v1", tags=["label-generation"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.is_development,
        log_level=settings.log_level
    )
