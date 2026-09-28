from contextlib import asynccontextmanager
from typing import Any
import app.models

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import customers, orders, refunds
from app.core.config import settings
from app.database.connection import engine


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    # Nothing needs explicit setup at start — SQLAlchemy connects lazily.
    # Dispose the connection pool cleanly on shutdown so Postgres doesn't hold
    # open idle connections after the process exits.
    yield
    await engine.dispose()


app = FastAPI(
    title="Worknoon Refund System",
    description="AI-powered customer support refund system",
    version="0.1.0",
    # Disable the default /docs and /redoc in production to reduce attack surface.
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
    lifespan=lifespan,
)

# --- CORS ---
# Allow the Vite development server, the containerised frontend (nginx on
# port 3000), and any configured frontend origin to make cross-origin requests.
# In production, replace this list with the real frontend origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        # Local Vite dev server
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        # Docker Compose — nginx serves the built frontend on port 3000
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# --- Routers ---
app.include_router(customers.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(refunds.router, prefix="/api")


# --- Health ---
@app.get("/health", tags=["health"])
async def health_check() -> dict[str, Any]:
    """Liveness probe — confirms the process is running and accepting requests."""
    return JSONResponse(content={"status": "ok"})
