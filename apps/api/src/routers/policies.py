from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.db.session import get_db
from src.models.policy import Policy
from src.models.tenant import Tenant
from src.core.auth import get_current_tenant

router = APIRouter()

from src.core.policy.translator import CedarPolicyTranslator

class PolicyCreate(BaseModel):
    name: str
    description: str
    framework: str
    policy_language: str = "cedar"
    policy_content: str
    severity: str = "medium"

class PolicyGenerateRequest(BaseModel):
    natural_language: str

@router.post("/generate")
async def generate_policy(
    req: PolicyGenerateRequest,
    tenant: Tenant = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """
    Translates natural language security requirements into valid Cedar policies.
    """
    result = CedarPolicyTranslator.translate(req.natural_language)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["explanation"])
    return result


@router.get("/sync")
async def sync_policies(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Endpoint for the SDK to poll and download the latest policies for its tenant.

    Returns the tenant's own enabled policies plus any enabled system policies
    (tenant_id IS NULL). Crucially, it never returns another tenant's policies.
    """
    result = await db.execute(
        select(Policy).where(
            Policy.enabled == True,  # noqa: E712 - SQLAlchemy boolean comparison
            or_(Policy.tenant_id == tenant.id, Policy.tenant_id.is_(None)),
        )
    )
    policies = result.scalars().all()

    return {
        "tenant_id": str(tenant.id),
        "policies": [
            {
                "id": str(p.id),
                "name": p.name,
                "content": p.policy_content,
                "language": p.policy_language,
            }
            for p in policies
        ],
    }

@router.get("/")
async def list_policies(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Policy)
        .where(or_(Policy.tenant_id == tenant.id, Policy.tenant_id.is_(None)))
        .order_by(Policy.created_at.desc())
    )
    return result.scalars().all()

@router.post("/")
async def create_policy(
    policy: PolicyCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    db_policy = Policy(
        tenant_id=tenant.id,
        name=policy.name,
        description=policy.description,
        framework=policy.framework,
        policy_language=policy.policy_language,
        policy_content=policy.policy_content,
        severity=policy.severity,
    )
    db.add(db_policy)
    await db.commit()
    await db.refresh(db_policy)
    return db_policy
