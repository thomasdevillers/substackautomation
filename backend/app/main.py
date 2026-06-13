"""FastAPI entrypoint: API + scheduler + built SPA."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import init_db
from .routes import router
from .scheduler import run_catch_up, start_scheduler

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    run_catch_up()      # post anything overdue from downtime
    start_scheduler()   # then poll every 60s
    yield


app = FastAPI(title="Substack Notes Scheduler", lifespan=lifespan)
app.include_router(router)


@app.get("/api/health")
def health():
    return {"ok": True}


# Serve the built frontend (if present). API routes are registered above so
# they take precedence; everything else falls back to index.html (SPA routing).
_static = settings.static_dir
if os.path.isdir(_static):
    app.mount("/assets", StaticFiles(directory=os.path.join(_static, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        index = os.path.join(_static, "index.html")
        candidate = os.path.join(_static, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(index)
