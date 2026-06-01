import httpx
from datetime import datetime
from typing import List, Dict, Any
from .base import BaseConnector, AgentRecord, ConnectorStatus

class M365Connector(BaseConnector):
    """
    Microsoft 365 Connector using Microsoft Graph API.
    Handles discovery of Copilot and other M365-integrated agents.
    """
    
    BASE_URL = "https://graph.microsoft.com/beta" # Using beta for Copilot admin APIs

    def __init__(self, tenant_id: str, credentials: Dict[str, Any]):
        super().__init__(tenant_id, credentials)
        # In a real app, we'd use MSAL to manage tokens. 
        # For this MVP, we assume credentials contains a valid access_token.
        self.access_token = self.credentials.get("access_token")
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json"
            }
        )

    async def connect(self) -> bool:
        try:
            # Simple call to verify token validity
            response = await self.client.get("/organization")
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    async def discover_agents(self) -> List[AgentRecord]:
        """
        Calls the Graph API to list Copilot extensions and agents.
        Endpoint: /copilot/admin/catalog/packages
        """
        agents = []
        try:
            # Mocking the call since this is a new beta API
            # response = await self.client.get("/copilot/admin/catalog/packages")
            # data = response.json()
            
            # Simulated response for the MVP
            data = {
                "value": [
                    {
                        "id": "app-123",
                        "displayName": "HR Leave Assistant Copilot",
                        "type": "custom_agent",
                        "status": "enabled",
                        "capabilities": ["GraphConnector", "Plugin"]
                    },
                    {
                        "id": "app-456",
                        "displayName": "Salesforce Integration for Copilot",
                        "type": "third_party",
                        "status": "enabled",
                        "capabilities": ["Plugin"]
                    }
                ]
            }
            
            for item in data.get("value", []):
                agents.append(AgentRecord(
                    external_id=item["id"],
                    name=item["displayName"],
                    agent_type=item["type"],
                    status=item["status"],
                    metadata={"capabilities": item.get("capabilities", [])},
                    last_seen=datetime.utcnow()
                ))
            return agents
            
        except httpx.HTTPError as e:
            # Handle error appropriately
            print(f"Error fetching agents from M365: {e}")
            return []

    async def get_agent_activity(self, agent_id: str, since: datetime) -> List[Dict[str, Any]]:
        """
        Calls the aiInteractionHistory API to get recent interactions.
        """
        # Mocking for MVP
        return []

    async def health_check(self) -> ConnectorStatus:
        is_connected = await self.connect()
        return ConnectorStatus(
            is_healthy=is_connected,
            last_sync=datetime.utcnow() if is_connected else None,
            error_message=None if is_connected else "Authentication failed"
        )
