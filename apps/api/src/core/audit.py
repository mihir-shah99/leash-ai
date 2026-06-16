"""Tamper-evident audit hashing.

Each audit event is hash-chained to the previous event for the same tenant:

    event_hash = SHA-256( canonical(event_fields) | previous_hash )

Because each hash incorporates the prior one, altering or deleting any event
breaks every subsequent hash in that tenant's chain, which is exactly the
property an auditor needs. This replaces the previous constant
``"dummy_hash_for_mvp"`` placeholder.
"""
import hashlib
import json
from typing import Any, Dict, Optional

# Sentinel for the first event in a tenant's chain.
GENESIS_HASH = "0" * 64


def canonicalize(fields: Dict[str, Any]) -> str:
    """Deterministic JSON serialization so the hash is reproducible."""
    return json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str)


def compute_event_hash(fields: Dict[str, Any], previous_hash: Optional[str]) -> str:
    """Hash the canonical event payload chained to the previous hash."""
    base = canonicalize(fields) + "|" + (previous_hash or GENESIS_HASH)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def hashable_fields(
    *,
    event_id: str,
    timestamp: str,
    tenant_id: str,
    agent_id: str,
    action_type: str,
    action_detail: Dict[str, Any],
    decision: str,
    violations: list,
) -> Dict[str, Any]:
    """The exact, stable set of fields covered by the integrity hash."""
    return {
        "event_id": event_id,
        "timestamp": timestamp,
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "action_type": action_type,
        "action_detail": action_detail,
        "decision": decision,
        "violations": violations,
    }
