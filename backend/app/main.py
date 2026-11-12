"""Hestia API — FastAPI entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import ask, compare, experiments, health, predict, ranking

app = FastAPI(
    title="Hestia API",
    description="Guarding the flame beyond Earth — NASA microgravity combustion insights.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().web_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (health, experiments, compare, ranking, ask, predict):
    app.include_router(r.router)
