from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.db.session import get_db
from src.models.policy import Policy
import uuid

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
async def generate_policy(req: PolicyGenerateRequest) -> Dict[str, Any]:
    """
    Translates natural language security requirements into valid Cedar policies.
    """
    result = CedarPolicyTranslator.translate(req.natural_language)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["explanation"])
    return result


@router.get("/sync")
async def sync_policies(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Endpoint for the SDK to poll and download the latest policies for its tenant.
    """
    result = await db.execute(select(Policy).where(Policy.enabled == True))
    policies = result.scalars().all()
    
    return {
        "tenant_id": "mock_tenant",
        "policies": [
            {
                "id": str(p.id),
                "name": p.name,
                "content": p.policy_content,
                "language": p.policy_language
            } for p in policies
        ]
    }

@router.get("/")
async def list_policies(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Policy).order_by(Policy.created_at.desc()))
    return result.scalars().all()

@router.post("/")
async def create_policy(policy: PolicyCreate, db: AsyncSession = Depends(get_db)):
    db_policy = Policy(
        name=policy.name,
        description=policy.description,
        framework=policy.framework,
        policy_language=policy.policy_language,
        policy_content=policy.policy_content,
        severity=policy.severity
    )
    db.add(db_policy)
    await db.commit()
    await db.refresh(db_policy)
    return db_policy
