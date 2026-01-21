"""Main FastAPI application entry point."""

import logging
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pythonjsonlogger import jsonlogger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import config
from src.db.connection import init_db, close_db

# Configure structured JSON logging
logger = logging.getLogger()


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logging."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = record.created
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id


# Setup JSON logging
json_handler = logging.StreamHandler(sys.stdout)
formatter = CustomJsonFormatter(
    "%(timestamp)s %(level)s %(name)s %(message)s"
)
json_handler.setFormatter(formatter)
logger.addHandler(json_handler)

# Log level from environment (DEBUG for troubleshooting OpenAI responses)
import os
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logger.setLevel(getattr(logging, log_level, logging.INFO))

# Initialize rate limiter (disabled in test mode)
limiter = Limiter(
    key_func=get_remote_address,
    enabled=not config.TESTING,
)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging all requests with timing."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        request_id = f"{time.time()}"

        # Log request
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None,
            },
        )

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Log response
            logger.info(
                "Request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration": round(duration, 3),
                },
            )
            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "Request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "duration": round(duration, 3),
                },
                exc_info=True,
            )
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers to responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers for production
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers[
            "Strict-Transport-Security"
        ] = "max-age=31536000; includeSubDomains"
        response.headers[
            "Content-Security-Policy"
        ] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://unpkg.com; style-src 'self' 'unsafe-inline'; frame-src 'self' https://www.youtube.com https://www.youtube-nocookie.com"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers[
            "Permissions-Policy"
        ] = "geolocation=(), microphone=(), camera=()"

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    await init_db()
    print("Database initialized")
    yield
    # Shutdown
    await close_db()
    print("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title="Misconception Dialogue Simulator",
    description=(
        "Three-party dialogue simulator for teacher training"
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware (configure allowed origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        config.FRONTEND_URL if hasattr(config, "FRONTEND_URL") else "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# Add session middleware for cookie-based auth (T112: Security hardening)
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    session_cookie="session_id",
    max_age=28800,  # 8 hours
    same_site="lax",
    https_only=config.is_production,  # Enable HTTPS-only in production
    # HttpOnly flag is enforced by SessionMiddleware internally.
)

# Mount static files
app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)

# Setup Jinja2 templates
templates = Jinja2Templates(directory="src/templates")


# Register route blueprints
from src.api.routes import (
    admin,
    admin_analysis,
    admin_api_usage,
    admin_prompts,
    admin_sessions,
    auth,
    health,
    scenarios,
    sessions,
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(scenarios.router)
app.include_router(sessions.router)
app.include_router(admin.router)
app.include_router(admin_analysis.router)
app.include_router(admin_api_usage.router)
app.include_router(admin_prompts.router)
app.include_router(admin_sessions.router)
