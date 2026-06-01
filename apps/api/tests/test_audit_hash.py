import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.audit import (
    canonicalize,
    compute_event_hash,
    hashable_fields,
    GENESIS_HASH,
)


def _fields(**overrides):
    base = dict(
        event_id="11111111-1111-1111-1111-111111111111",
        timestamp="2026-06-01T00:00:00Z",
        tenant_id="t1",
        agent_id="a1",
        action_type="issue_refund",
        action_detail={"tool_name": "issue_refund", "arguments": {"amount": 100}},
        decision="ALLOW",
        violations=[],
    )
    base.update(overrides)
    return hashable_fields(**base)


def test_hash_is_deterministic():
    f = _fields()
    assert compute_event_hash(f, GENESIS_HASH) == compute_event_hash(f, GENESIS_HASH)


def test_canonicalize_is_key_order_independent():
    assert canonicalize({"a": 1, "b": 2}) == canonicalize({"b": 2, "a": 1})


def test_hash_changes_when_any_field_changes():
    base = compute_event_hash(_fields(), GENESIS_HASH)
    assert compute_event_hash(_fields(decision="DENY"), GENESIS_HASH) != base
    assert compute_event_hash(_fields(action_type="wire_transfer"), GENESIS_HASH) != base


def test_hash_depends_on_previous_hash():
    f = _fields()
    h1 = compute_event_hash(f, GENESIS_HASH)
    h2 = compute_event_hash(f, h1)
    assert h1 != h2  # same event, different chain position -> different hash


def test_chain_tamper_is_detectable():
    # Build a 3-event chain, then tamper with event 2 and confirm event 3's
    # recomputed hash no longer matches.
    e1 = _fields(event_id="1", action_detail={"amount": 100})
    e2 = _fields(event_id="2", action_detail={"amount": 200})
    e3 = _fields(event_id="3", action_detail={"amount": 300})

    h1 = compute_event_hash(e1, GENESIS_HASH)
    h2 = compute_event_hash(e2, h1)
    h3 = compute_event_hash(e3, h2)

    # Attacker rewrites event 2's amount; h2 (stored) stays the same but the
    # recomputed hash diverges, breaking the chain at event 3.
    tampered_e2 = _fields(event_id="2", action_detail={"amount": 999})
    recomputed_h2 = compute_event_hash(tampered_e2, h1)
    assert recomputed_h2 != h2
    # Anyone replaying the chain from the tampered event gets a different h3.
    assert compute_event_hash(e3, recomputed_h2) != h3
