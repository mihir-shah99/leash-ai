from typing import List, Dict, Any
from pydantic import BaseModel
from .classifier import RiskClassifier
from ..connector_framework.base import BaseConnector, AgentRecord
from ..connector_framework.m365 import M365Connector

class DiscoveryReport(BaseModel):
    tenant_id: str
    total_agents: int
    agents: List[AgentRecord]
    risk_summary: Dict[str, int]
    compliance_gaps: List[str]

class DiscoveryEngine:
    """
    Orchestrates the discovery process across all connected platforms.
    """

    def __init__(self, tenant_id: str, db_session=None):
        self.tenant_id = tenant_id
        self.db_session = db_session
        self.classifier = RiskClassifier()

    def _get_connectors(self) -> List[BaseConnector]:
        """
        Retrieves active connectors for the tenant from the database.
        For MVP, we mock returning a configured M365 connector.
        """
        # TODO: Fetch from DB using self.db_session
        mock_credentials = {"access_token": "mock_token_123"}
        return [M365Connector(self.tenant_id, mock_credentials)]

    async def run_discovery(self) -> DiscoveryReport:
        """
        Runs the full discovery pipeline.
        """
        raw_agents: List[AgentRecord] = []
        connectors = self._get_connectors()

        # Phase 1: Enumerate
        for connector in connectors:
            if await connector.connect():
                discovered = await connector.discover_agents()
                raw_agents.extend(discovered)
            else:
                # Log connector failure
                pass

        # Phase 2: Enrich & Classify
        processed_agents = []
        risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "unknown": 0}
        
        for agent in raw_agents:
            enriched_agent = self.classifier.classify_agent(agent)
            processed_agents.append(enriched_agent)
            
            risk = enriched_agent.metadata.get("risk_level", "unknown")
            if risk in risk_counts:
                risk_counts[risk] += 1

        # Phase 3: Identify Gaps
        # Simple heuristic: if any critical agents have no governance, flag it
        gaps = []
        if risk_counts["critical"] > 0:
            gaps.append(f"Found {risk_counts['critical']} critical risk agents with potential PHI/PII exposure.")

        # Phase 4: Generate Report (and ideally save to DB)
        report = DiscoveryReport(
            tenant_id=self.tenant_id,
            total_agents=len(processed_agents),
            agents=processed_agents,
            risk_summary=risk_counts,
            compliance_gaps=gaps
        )
        
        return report
