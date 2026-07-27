from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.db import Database
from app.ratelimit import SlidingWindowLimiter
from app.routers import api, web
from app.seed import seed_demo


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    database = Database(resolved.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database.create_all()
        if resolved.seed_demo_data:
            with database.session() as db:
                seed_demo(db, resolved)
        yield

    app = FastAPI(
        title="Gateway + Archangel",
        description="A human Christian discussion network with silent, structured biblical analysis.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved
    app.state.db = database
    app.state.rate_limiter = SlidingWindowLimiter()

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.include_router(web.router)
    app.include_router(api.router)
    return app


app = create_app()
