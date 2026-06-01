from typing import List
from ..connector_framework.base import AgentRecord

class RiskClassifier:
    """
    Evaluates discovered agents and assigns risk levels and data exposure tags.
    """

    def __init__(self):
        # We would eventually load these rules from a database or config
        self.high_risk_capabilities = ["GraphConnector", "ExternalPlugin", "DatabaseWrite"]
        
    def classify_agent(self, agent: AgentRecord) -> AgentRecord:
        """Assigns a risk level based on agent type and capabilities."""
        capabilities = agent.metadata.get("capabilities", [])
        
        # 1. Determine risk level
        risk_score = 0
        
        if agent.agent_type == "custom_agent":
            risk_score += 2
        elif agent.agent_type == "third_party":
            risk_score += 3
        
        for cap in capabilities:
            if cap in self.high_risk_capabilities:
                risk_score += 2
                
        if risk_score >= 4:
            agent.metadata["risk_level"] = "high"
        elif risk_score >= 2:
            agent.metadata["risk_level"] = "medium"
        else:
            agent.metadata["risk_level"] = "low"
            
        # 2. Tag data exposure
        # In a real system, we'd analyze Graph permissions or prompt templates
        # For now, we simulate tagging based on name/capabilities
        exposure = []
        name_lower = agent.name.lower()
        if "hr" in name_lower or "leave" in name_lower:
            exposure.append("pii")
        if "finance" in name_lower or "sales" in name_lower:
            exposure.append("financial")
        if "health" in name_lower or "clinical" in name_lower:
            exposure.append("phi")
            agent.metadata["risk_level"] = "critical" # PHI immediately escalates
            
        agent.data_categories = exposure
        
        return agent
