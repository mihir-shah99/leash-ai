from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_db
from src.models.audit import AuditEvent

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
async def redact_text(payload: RedactPayload):
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
async def ingest_telemetry(event: AuditEventPayload, db: AsyncSession = Depends(get_db)):
    """
    Ingest a single audit event from an AgentShield SDK.
    Writes to PostgreSQL JSONB column.
    """
    logger.info(f"Received audit event: {event.event_id} | Decision: {event.policy_decision}")
    
    # In a real system, tenant_id and agent_id come from Auth/Tokens.
    # For MVP, we'll dummy them or extract from headers.
    dummy_tenant_id = uuid.uuid4()
    dummy_agent_id = uuid.uuid4()

    try:
        db_event = AuditEvent(
            event_id=uuid.UUID(event.event_id),
            time=datetime.fromisoformat(event.timestamp.replace("Z", "+00:00")),
            tenant_id=dummy_tenant_id,
            agent_id=dummy_agent_id,
            action_type=event.action_type,
            action_detail=event.action_detail,
            decision=event.policy_decision,
            violations=[event.policy_reason] if event.policy_decision == "DENY" else [],
            event_hash="dummy_hash_for_mvp"
        )
        db.add(db_event)
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to save audit event to DB: {e}")
        # We don't fail the API request if telemetry insert fails, 
        # so the agent isn't blocked by telemetry DB issues.
        pass
    
    return {"status": "success", "event_id": event.event_id}

@router.get("/")
async def get_telemetry(db: AsyncSession = Depends(get_db)):
    from sqlalchemy.future import select
    result = await db.execute(
        select(AuditEvent).order_by(AuditEvent.time.desc()).limit(50)
    )
    events = result.scalars().all()
    return events

