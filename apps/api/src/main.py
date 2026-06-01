import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.routers import telemetry, policies

app = FastAPI(
    title="AgentShield Control Plane",
    description="API for ingesting telemetry from the AgentShield SDK and managing policies.",
    version="0.1.0"
)

# Explicit allow-list from config. A wildcard origin combined with credentials is
# rejected by browsers and unsafe, so we never use "*" here.
_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
allowed_origins = [o.strip() for o in _origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(telemetry.router, prefix="/v1/telemetry", tags=["telemetry"])
app.include_router(policies.router, prefix="/v1/policies", tags=["policies"])

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
