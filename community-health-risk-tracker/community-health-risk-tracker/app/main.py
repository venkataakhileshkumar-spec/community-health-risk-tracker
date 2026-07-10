"""
Community Health Risk Tracker
==============================
FastAPI application entrypoint. Wires together the communities, indicators,
and risk-scoring routers, initializes the database schema, and serves the
static dashboard frontend.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import Base, engine
from app.routers import communities, indicators, risk

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Community Health Risk Tracker",
    description=(
        "Tracks community-level population health indicators and computes a "
        "transparent, weighted composite risk score to help prioritize "
        "outreach and resource allocation."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(communities.router)
app.include_router(indicators.router)
app.include_router(risk.router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def serve_dashboard():
        return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/api/health", tags=["health"])
def health_check():
    return {"status": "ok"}
