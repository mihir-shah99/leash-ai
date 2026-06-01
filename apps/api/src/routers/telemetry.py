from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime
import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.db.session import get_db
from src.models.audit import AuditEvent
from src.models.tenant import Tenant
from src.core.auth import get_current_tenant
from src.core.audit import compute_event_hash, hashable_fields, GENESIS_HASH

logger = logging.getLogger(__name__)

router = APIRouter()

class AuditEventPayload(BaseModel):
    event_id: str
    timestamp: str
    action_type: str
    action_detail: Dict[str, Any]
    policy_decision: str
    policy_reason: str
    evaluation_duration_ms: float

class RedactPayload(BaseModel):
    text: str

@router.post("/redact")
async def redact_text(payload: RedactPayload, tenant: Tenant = Depends(get_current_tenant)):
    """
    Provide deep NER-based redaction as a service for edge SDKs.
    """
    try:
        from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
        from presidio_anonymizer import AnonymizerEngine
        
        # In a real setup, we would initialize this once globally to save cold start
        analyzer = AnalyzerEngine()
        ssn_pattern = Pattern(name="ssn_pattern", regex=r"\b\d{3}[-.]?\d{2}[-.]?\d{4}\b", score=0.85)
        ssn_recognizer = PatternRecognizer(supported_entity="US_SSN", patterns=[ssn_pattern])
        analyzer.registry.add_recognizer(ssn_recognizer)
        
        anonymizer = AnonymizerEngine()
        
        # entities=None analyses for ALL supported entity types; an empty list
        # matches nothing (the previous bug, which made deep redaction a no-op).
        results = analyzer.analyze(text=payload.text, entities=None, language='en')
        anonymized_result = anonymizer.anonymize(text=payload.text, analyzer_results=results)
        
        return {"redacted_text": anonymized_result.text}
    except Exception as e:
        logger.error(f"Redaction API failed: {e}")
        raise HTTPException(status_code=500, detail="Redaction service unavailable")

@router.post("/ingest")
async def ingest_telemetry(
    event: AuditEventPayload,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Ingest a single audit event from an AgentShield SDK.

    The tenant is resolved from the API key, so events are attributable and
    isolated. Each event is hash-chained to the tenant's previous event to make
    the audit trail tamper-evident.
    """
    logger.info(
        f"Audit event {event.event_id} | tenant={tenant.api_key_prefix} | "
        f"decision={event.policy_decision}"
    )

    # Deterministic SDK agent id per tenant (until per-agent identity lands).
    agent_id = uuid.uuid5(uuid.NAMESPACE_OID, f"{tenant.id}:sdk")
    violations = [event.policy_reason] if event.policy_decision == "DENY" else []

    try:
        # Fetch the tip of this tenant's hash chain. NOTE: under highly
        # concurrent ingest this read-then-write can race; a per-tenant advisory
        # lock or serial sequence is the hardening step (tracked for later).
        prev_result = await db.execute(
            select(AuditEvent.event_hash)
            .where(AuditEvent.tenant_id == tenant.id)
            .order_by(AuditEvent.time.desc())
            .limit(1)
        )
        previous_hash = prev_result.scalar_one_or_none() or GENESIS_HASH

        fields = hashable_fields(
            event_id=event.event_id,
            timestamp=event.timestamp,
            tenant_id=str(tenant.id),
            agent_id=str(agent_id),
            action_type=event.action_type,
            action_detail=event.action_detail,
            decision=event.policy_decision,
            violations=violations,
        )
        event_hash = compute_event_hash(fields, previous_hash)

        db_event = AuditEvent(
            event_id=uuid.UUID(event.event_id),
            time=datetime.fromisoformat(event.timestamp.replace("Z", "+00:00")),
            tenant_id=tenant.id,
            agent_id=agent_id,
            action_type=event.action_type,
            action_detail=event.action_detail,
            decision=event.policy_decision,
            violations=violations,
            event_hash=event_hash,
            previous_hash=previous_hash,
        )
        db.add(db_event)
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to save audit event to DB: {e}")
        # Don't fail the SDK request on a telemetry DB issue, so the agent is
        # never blocked by the audit pipeline.
        await db.rollback()

    return {"status": "success", "event_id": event.event_id}

@router.get("/")
async def get_telemetry(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.tenant_id == tenant.id)
        .order_by(AuditEvent.time.desc())
        .limit(50)
    )
    return result.scalars().all()

