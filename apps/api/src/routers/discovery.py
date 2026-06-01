from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any

from ..core.discovery.engine import DiscoveryEngine, DiscoveryReport

router = APIRouter()

# In a real app, this would be injected by a dependency verifying the JWT
async def get_current_tenant_id() -> str:
    return "tenant-1234-abcd"

@router.post("/scan", response_model=DiscoveryReport)
async def run_discovery_scan(tenant_id: str = Depends(get_current_tenant_id)):
    """
    Trigger a manual discovery scan across all connected environments for the tenant.
    """
    try:
        engine = DiscoveryEngine(tenant_id=tenant_id)
        report = await engine.run_discovery()
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/report/latest", response_model=DiscoveryReport)
async def get_latest_report(tenant_id: str = Depends(get_current_tenant_id)):
    """
    Fetch the most recent discovery report from the database.
    (Mocked for MVP to just run a scan)
    """
    # MVP: just run a scan synchronously. Later this will fetch from DB.
    engine = DiscoveryEngine(tenant_id=tenant_id)
    return await engine.run_discovery()
