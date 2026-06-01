import pytest
from agentshield.pii import PIIRedactor

def test_edge_redaction():
    text = "My email is test@example.com and my SSN is 123-45-6789."
    
    # Redact using edge mode (regex)
    redacted = PIIRedactor.redact_string(text, mode="edge")
    
    assert "<EMAIL_ADDRESS>" in redacted
    assert "<US_SSN>" in redacted
    assert "test@example.com" not in redacted
    assert "123-45-6789" not in redacted

def test_deep_local_redaction():
    # Will fallback to edge if presidio isn't installed properly, but should still redact.
    text = "My email is admin@company.com and my SSN is 987-65-4321."
    
    redacted = PIIRedactor.redact_string(text, mode="deep_local")
    
    assert "admin@company.com" not in redacted
    assert "987-65-4321" not in redacted
