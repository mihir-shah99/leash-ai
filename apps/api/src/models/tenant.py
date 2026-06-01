import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from .base import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    plan = Column(String, nullable=False, default='discover')
    compliance_frameworks = Column(ARRAY(String), default=list)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    settings = Column(JSON, default=dict)
