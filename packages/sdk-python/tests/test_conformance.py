"""Runs the shared cross-SDK conformance suite against the Python engine.

The same cases.json is executed by the TypeScript SDK, guaranteeing a policy
authored once enforces identically in both runtimes.
"""
import json
from pathlib import Path

import pytest

from agentshield.engine import PolicyEngine

CASES_PATH = Path(__file__).resolve().parents[2] / "conformance" / "cases.json"
CASES = json.loads(CASES_PATH.read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_conformance(case):
    engine = PolicyEngine(
        case["policies"],
        default_effect=case.get("default_effect", "allow"),
        fail_closed=case.get("fail_closed", True),
    )
    decision, _violations = engine.evaluate(case["tool_name"], case["args"])
    assert decision == case["expected"], (
        f"{case['name']}: got {decision}, expected {case['expected']}"
    )
