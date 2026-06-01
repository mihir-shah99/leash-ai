import uuid
from datetime import datetime
from typing import List, Optional, Any
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    plan = Column(String, default='discover')  # discover, protect, comply, enterprise
    compliance_frameworks = Column(ARRAY(String), default=[]) # e.g. ['hipaa', 'sox']
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    settings = Column(JSONB, default=dict)

    agents = relationship("Agent", back_populates="tenant")
    policies = relationship("Policy", back_populates="tenant")
    connectors = relationship("Connector", back_populates="tenant")


class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    external_id = Column(String)  # ID in source system (e.g. M365)
    source = Column(String, nullable=False) # 'm365', 'salesforce', 'sdk', 'manual'
    name = Column(String, nullable=False)
    agent_type = Column(String, nullable=False) # 'copilot', 'power_automate', 'custom'
    status = Column(String, default='discovered') # discovered, governed, blocked, archived
    risk_level = Column(String, default='unknown') # critical, high, medium, low, unknown
    data_categories = Column(ARRAY(String), default=[]) # ['phi', 'pii', 'financial']
    governance_config = Column(JSONB, default=dict)
    last_seen = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="agents")


class Policy(Base):
    __tablename__ = "policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True) # NULL for system policies
    framework = Column(String) # 'hipaa', 'sox', 'base_security'
    name = Column(String, nullable=False)
    description = Column(String)
    policy_language = Column(String, nullable=False, default='yaml') # yaml, rego, cedar
    policy_content = Column(String, nullable=False)
    severity = Column(String, default='medium')
    enabled = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)
    owasp_mapping = Column(ARRAY(String))
    regulation_ref = Column(String)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="policies")


class Connector(Base):
    __tablename__ = "connectors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    connector_type = Column(String, nullable=False) # 'm365', 'salesforce'
    status = Column(String, default='pending') # pending, connected, error, disconnected
    credentials = Column(JSONB, nullable=False) # Encrypted tokens
    last_sync = Column(DateTime(timezone=True))
    sync_config = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="connectors")


# We would define AuditEvent here or in a separate file optimized for TimescaleDB
class AuditEvent(Base):
    __tablename__ = "audit_events"
    
    # Normally for TimescaleDB 'time' is the primary partitioning key
    time = Column(DateTime(timezone=True), primary_key=True, default=datetime.utcnow)
    event_id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True) # composite PK for timescale
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    agent_id = Column(UUID(as_uuid=True), nullable=False)
    action_type = Column(String, nullable=False)
    action_detail = Column(JSONB, nullable=False)
    data_categories = Column(ARRAY(String))
    sensitivity = Column(String)
    decision = Column(String, nullable=False) # ALLOW, DENY, ESCALATE, TRANSFORM
    policies_evaluated = Column(ARRAY(String))
    violations = Column(ARRAY(String))
    user_context = Column(JSONB)
    session_id = Column(String)
    event_hash = Column(String, nullable=False)
    previous_hash = Column(String)
    signature = Column(String)
