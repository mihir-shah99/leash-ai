import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from .base import Base

class Policy(Base):
    __tablename__ = "policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), index=True) # Nullable for global policies
    
    framework = Column(String) # e.g. 'hipaa', 'sox'
    name = Column(String, nullable=False)
    description = Column(String)
    
    # We use Microsoft AGT underneath which supports YAML/Rego/Cedar.
    policy_language = Column(String, default="yaml", nullable=False)
    policy_content = Column(String, nullable=False)
    
    severity = Column(String, default="medium")
    enabled = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
