"""FastAPI application — serves API + static files."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from accessiflow.web.api.config_routes import router as config_router
from accessiflow.web.api.course_routes import router as course_router
from accessiflow.web.api.audit_routes import router as audit_router
from accessiflow.web.api.fix_routes import router as fix_router
from accessiflow.web.api.report_routes import router as report_router
from accessiflow.web.api.ws import router as ws_router
from accessiflow.web.api.ai_routes import router as ai_router
from accessiflow.web.api.standards_routes import router as standards_router
from accessiflow.web.api.auth_routes import router as auth_router
from accessiflow.web.api.admin_routes import router as admin_router

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, run migrations, seed admin. Shutdown: dispose engine."""
    from accessiflow.db.engine import dispose_engine, init_db
    from accessiflow.db.seed import seed_admin
    from accessiflow.db.session import get_session_factory

    # Create tables (SQLite auto-create; PG should use Alembic)
    await init_db()
    logger.info("Database initialized")

    # Seed admin user
    factory = get_session_factory()
    async with factory() as session:
        await seed_admin(session)

    yield

    # Shutdown
    await dispose_engine()


app = FastAPI(
    title="Accessiflow",
    description="WCAG 2.1 AA, Section 508, and VPAT accessibility auditor for Canvas LMS",
    version="2.0.0",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from accessiflow.auth.middleware import RequestIDMiddleware  # noqa: E402
app.add_middleware(RequestIDMiddleware)

# API routes
app.include_router(auth_router, prefix="/api/auth")
app.include_router(admin_router, prefix="/api/admin")
app.include_router(config_router, prefix="/api")
app.include_router(course_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(fix_router, prefix="/api")
app.include_router(report_router, prefix="/api")
app.include_router(ws_router)
app.include_router(ai_router, prefix="/api")
app.include_router(standards_router, prefix="/api")

# Static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    """Serve the SPA."""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


def main():
    """Entry point for `accessiflow-web` script."""
    import uvicorn
    uvicorn.run("accessiflow.web.app:app", host="0.0.0.0", port=8080, reload=False)  # nosec B104 — intentional for Docker
