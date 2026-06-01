import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from .base import Base

class AuditEvent(Base):
    __tablename__ = "audit_events"

    # We use time as the primary index conceptually for TimescaleDB, 
    # but SQLAlchemy needs a primary key
    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    time = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    action_type = Column(String, nullable=False)
    action_detail = Column(JSONB, nullable=False)
    
    data_categories = Column(ARRAY(String), default=list)
    sensitivity = Column(String)
    
    decision = Column(String, nullable=False)
    policies_evaluated = Column(ARRAY(String), default=list)
    violations = Column(ARRAY(String), default=list)
    
    user_context = Column(JSONB)
    session_id = Column(String)
    
    event_hash = Column(String, nullable=False)
    previous_hash = Column(String)
    signature = Column(String)
