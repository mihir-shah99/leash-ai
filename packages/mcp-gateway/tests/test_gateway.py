import pytest
from unittest.mock import MagicMock, patch
from mcp_gateway.server import MCPSecurityGateway

@pytest.fixture
def mock_shield():
    with patch("mcp_gateway.server.AgentShield") as MockShield:
        mock_instance = MockShield.return_value
        yield mock_instance

def test_gateway_initialization(mock_shield):
    gateway = MCPSecurityGateway("python", ["-m", "http.server"])
    
    assert gateway.target_command == "python"
    assert gateway.target_args == ["-m", "http.server"]
    assert gateway.server.name == "mcp-security-gateway"
    
def test_gateway_check_action_called(mock_shield):
    # This is a basic test to ensure the AgentShield instance is created
    gateway = MCPSecurityGateway("python", ["-m", "http.server"])
    assert gateway.shield == mock_shield
