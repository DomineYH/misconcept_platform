"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from src.config import config
from src.db.connection import init_db, close_db


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

# Add session middleware for cookie-based auth
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    session_cookie="session_id",
    max_age=28800,  # 8 hours
    same_site="lax",
    https_only=False,  # Set True in production with HTTPS
)

# Mount static files
app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)

# Setup Jinja2 templates
templates = Jinja2Templates(directory="src/templates")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Register route blueprints
from src.api.routes import admin, auth, scenarios, sessions

app.include_router(auth.router)
app.include_router(scenarios.router)
app.include_router(sessions.router)
app.include_router(admin.router)
