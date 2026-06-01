import importlib.resources

def _load_policy(filename: str) -> str:
    """Load a cedar policy file from the bundled policies directory."""
    try:
        if hasattr(importlib.resources, 'files'):
            # Python 3.9+ 
            return importlib.resources.files('agentshield.policies').joinpath(filename).read_text("utf-8")
        else:
            # Fallback for older python
            return importlib.resources.read_text('agentshield.policies', filename)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Could not load policy pack '{filename}': {e}")
        return ""

class Packs:
    """
    Pre-compiled Cedar Policies that run locally using the true AST engine.
    Provides immediate out-of-the-box protection without requiring the Control Plane.
    """
    
    @property
    def OWASP_TOP_10(self) -> str:
        return _load_policy("owasp.cedar")
        
    @property
    def FINANCIAL(self) -> str:
        return _load_policy("financial.cedar")
        
    @property
    def NO_PII(self) -> str:
        return _load_policy("pii.cedar")

# Create a singleton instance so properties work without instantiation
Packs = Packs()
