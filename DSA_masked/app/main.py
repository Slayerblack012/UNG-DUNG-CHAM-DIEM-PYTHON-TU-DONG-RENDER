"""
DSA AutoGrader — FastAPI Application Factory.

Tạo và cấu hình ứng dụng FastAPI:
  • CORS Middleware
  • GZip Compression
  • Static Files Mount
  • Database Initialization (lifespan)
  • API Router
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import BASE_DIR
from app.api.endpoints import router
from app.models.database import db

# ── Logging Configuration ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-18s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dsa.app")


# ═══════════════════════════════════════════
#  Lifespan (Startup / Shutdown)
# ═══════════════════════════════════════════

@asynccontextmanager
async def lifespan(application: FastAPI):
    """
    Application lifecycle manager.
    Thay thế deprecated @app.on_event("startup") / ("shutdown").
    """
    # ── Startup ──
    try:
        db.initialize()
        logger.info("[OK] Database initialized successfully.")
    except Exception as exc:
        logger.warning("[WARN] Database init failed: %s — running in offline mode.", exc)

    logger.info("[START] DSA AutoGrader is ready at http://0.0.0.0:8000")

    yield  # ← Application runs here

    # ── Shutdown ──
    logger.info("[STOP] DSA AutoGrader shutting down.")


# ═══════════════════════════════════════════
#  Application Factory
# ═══════════════════════════════════════════

def create_app() -> FastAPI:
    """Tạo và cấu hình FastAPI application."""

    application = FastAPI(
        title="DSA AutoGrader",
        description="Hệ thống chấm điểm bài tập DSA tự động",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,      # Ẩn Swagger UI
        redoc_url=None,     # Ẩn ReDoc
        openapi_url=None,   # Ẩn OpenAPI schema
    )

    # ── Middleware ──
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(GZipMiddleware, minimum_size=1000)

    # ── Static Files ──
    static_path = os.path.join(BASE_DIR, "static")
    if os.path.exists(static_path):
        application.mount("/static", StaticFiles(directory=static_path), name="static")

    # ── API Routes ──
    application.include_router(router)

    return application


# ── Create the application instance ──
app = create_app()
