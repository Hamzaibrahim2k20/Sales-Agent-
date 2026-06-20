"""
Fordaq Lead Activation Agent — FastAPI backend
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import init_db
from api.leads import router as leads_router
from api.calls import router as calls_router
from api.webhooks import router as webhooks_router
from api.reports import router as reports_router
from api.dashboard import router as dashboard_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Fordaq Calling Agent started")
    yield
    logger.info("Fordaq Calling Agent shut down")


app = FastAPI(
    title="Fordaq Lead Activation Agent",
    description=(
        "Semi-automated calling agent that qualifies Fordaq members, "
        "logs call outcomes and surfaces hot leads for human follow-up."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount dashboard static files
import os
static_dir = os.path.join(os.path.dirname(__file__), "dashboard", "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# API routes
app.include_router(leads_router, prefix="/api/v1")
app.include_router(calls_router, prefix="/api/v1")
app.include_router(webhooks_router)
app.include_router(reports_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def serve_dashboard():
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard", "index.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    return {"message": "Fordaq Lead Activation Agent v1.0", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "fordaq-calling-agent"}
