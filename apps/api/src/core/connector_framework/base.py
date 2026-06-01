from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime

class AgentRecord(BaseModel):
    external_id: str
    name: str
    agent_type: str
    description: Optional[str] = None
    status: str
    data_categories: List[str] = []
    metadata: Dict[str, Any] = {}
    last_seen: Optional[datetime] = None

class ConnectorStatus(BaseModel):
    is_healthy: bool
    last_sync: Optional[datetime] = None
    error_message: Optional[str] = None

class BaseConnector(ABC):
    """
    Abstract base class for all AgentShield connectors.
    Connectors are responsible for discovering agents and syncing activity logs.
    """
    
    def __init__(self, tenant_id: str, credentials: Dict[str, Any]):
        self.tenant_id = tenant_id
        self.credentials = credentials

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection and verify credentials."""
        pass

    @abstractmethod
    async def discover_agents(self) -> List[AgentRecord]:
        """Discover all AI agents available in the connected environment."""
        pass

    @abstractmethod
    async def get_agent_activity(self, agent_id: str, since: datetime) -> List[Dict[str, Any]]:
        """Retrieve recent activity/interaction logs for a specific agent."""
        pass

    @abstractmethod
    async def health_check(self) -> ConnectorStatus:
        """Check the health of the connection."""
        pass
