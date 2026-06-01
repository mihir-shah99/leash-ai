import logging
import re
import os
import httpx
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class PIIRedactor:
    """
    Hybrid PII redaction engine.
    Edge mode: Lightweight regex based redaction for serverless environments.
    Deep mode: NLP-based redaction using local Presidio or remote API.
    """
    
    # Pre-compile regex for Edge mode
    _EMAIL_REGEX = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
    _SSN_REGEX = re.compile(r"\b\d{3}[-.]?\d{2}[-.]?\d{4}\b")
    _CREDIT_CARD_REGEX = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
    
    _analyzer = None
    _anonymizer = None

    @classmethod
    def set_mode(cls, mode: str = "edge"):
        cls.mode = mode

    @classmethod
    def _redact_edge(cls, text: str) -> str:
        text = cls._EMAIL_REGEX.sub("<EMAIL_ADDRESS>", text)
        text = cls._SSN_REGEX.sub("<US_SSN>", text)
        text = cls._CREDIT_CARD_REGEX.sub("<CREDIT_CARD>", text)
        return text

    @classmethod
    def _redact_deep_local(cls, text: str) -> str:
        if cls._analyzer is None:
            try:
                from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
                from presidio_anonymizer import AnonymizerEngine
            except ImportError:
                logger.warning("Presidio not installed. Falling back to Edge mode.")
                return cls._redact_edge(text)
                
            logger.info("Initializing Microsoft Presidio AnalyzerEngine...")
            cls._analyzer = AnalyzerEngine()
            
            ssn_pattern = Pattern(name="ssn_pattern", regex=r"\b\d{3}[-.]?\d{2}[-.]?\d{4}\b", score=0.85)
            ssn_recognizer = PatternRecognizer(supported_entity="US_SSN", patterns=[ssn_pattern])
            cls._analyzer.registry.add_recognizer(ssn_recognizer)
            cls._anonymizer = AnonymizerEngine()
            
        results = cls._analyzer.analyze(text=text, entities=[], language='en')
        anonymized_result = cls._anonymizer.anonymize(text=text, analyzer_results=results)
        return anonymized_result.text
        
    @classmethod
    def _redact_deep_remote(cls, text: str) -> str:
        api_key = os.environ.get("AGENT_SHIELD_API_KEY", "")
        base_url = os.environ.get("AGENT_SHIELD_BASE_URL", "http://localhost:8000")
        
        try:
            response = httpx.post(
                f"{base_url}/v1/redact",
                json={"text": text},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=2.0
            )
            if response.status_code == 200:
                return response.json().get("redacted_text", text)
        except Exception as e:
            logger.warning(f"Remote redaction failed: {e}. Falling back to Edge mode.")
        
        return cls._redact_edge(text)

    @classmethod
    def redact_string(cls, text: str, mode: str = "edge") -> str:
        if not isinstance(text, str) or not text.strip():
            return text

        if mode == "deep_local":
            return cls._redact_deep_local(text)
        elif mode == "deep_remote":
            return cls._redact_deep_remote(text)
        else:
            return cls._redact_edge(text)

    @classmethod
    def redact_payload(cls, payload: Any, mode: str = "edge") -> Any:
        if isinstance(payload, str):
            return cls.redact_string(payload, mode)
        elif isinstance(payload, dict):
            return {k: cls.redact_payload(v, mode) for k, v in payload.items()}
        elif isinstance(payload, list):
            return [cls.redact_payload(item, mode) for item in payload]
        return payload
