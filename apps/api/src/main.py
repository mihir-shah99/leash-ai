from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from src.routers import telemetry, policies

app = FastAPI(
    title="AgentShield Control Plane",
    description="API for ingesting telemetry from the AgentShield SDK and managing policies.",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(telemetry.router, prefix="/v1/telemetry", tags=["telemetry"])
app.include_router(policies.router, prefix="/v1/policies", tags=["policies"])

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
