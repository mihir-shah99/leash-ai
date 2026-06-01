"""Unit tests for the Cedar-subset policy engine.

These cover the correctness regressions that motivated the engine rewrite:
numeric bypasses, parser crashes, dropped operators, and over-blocking.
"""
import pytest

from agentshield.engine import (
    PolicyEngine,
    PolicyParseError,
    parse_policy_statement,
    _coerce_number,
)

REFUND = 'forbid(principal, action, resource) when { context.tool_name == "issue_refund" && context.amount > 500 };'


@pytest.mark.parametrize(
    "amount,expected",
    [
        (10000, "DENY"),
        (501, "DENY"),
        ("5,000", "DENY"),     # thousands separator must not bypass
        ("$9999", "DENY"),     # currency symbol must not bypass
        ("5_000", "DENY"),     # underscore grouping
        (" 600 ", "DENY"),     # surrounding whitespace
        ("abc", "DENY"),       # present-but-unparseable fails closed for forbid
        (500, "ALLOW"),        # boundary, not strictly greater
        (100, "ALLOW"),
    ],
)
def test_numeric_guardrail_cannot_be_bypassed(amount, expected):
    engine = PolicyEngine([REFUND])
    decision, _ = engine.evaluate("issue_refund", {"amount": amount})
    assert decision == expected


def test_missing_attribute_does_not_overblock():
    engine = PolicyEngine([REFUND])
    decision, _ = engine.evaluate("send_email", {"to": "a@b.com"})
    assert decision == "ALLOW"


def test_two_equalities_in_one_clause_does_not_crash():
    policy = 'forbid(principal, action, resource) when { context.tool_name == "x" && context.role == "guest" };'
    engine = PolicyEngine([policy])
    assert engine.evaluate("x", {"role": "guest"})[0] == "DENY"
    assert engine.evaluate("x", {"role": "admin"})[0] == "ALLOW"


def test_not_equals_is_honored():
    policy = 'forbid(principal, action, resource) when { context.role != "admin" };'
    engine = PolicyEngine([policy])
    assert engine.evaluate("deploy", {"role": "guest"})[0] == "DENY"
    assert engine.evaluate("deploy", {"role": "admin"})[0] == "ALLOW"


def test_logical_or_and_parens():
    policy = 'forbid(principal, action, resource) when { (context.tool_name == "a" || context.tool_name == "b") && context.env == "prod" };'
    engine = PolicyEngine([policy])
    assert engine.evaluate("a", {"env": "prod"})[0] == "DENY"
    assert engine.evaluate("a", {"env": "dev"})[0] == "ALLOW"
    assert engine.evaluate("c", {"env": "prod"})[0] == "ALLOW"


def test_substring_in_operator():
    policy = 'forbid(principal, action, resource) when { "rm -rf" in context.query };'
    engine = PolicyEngine([policy])
    assert engine.evaluate("sh", {"query": "rm -rf /"})[0] == "DENY"
    assert engine.evaluate("sh", {"query": "ls"})[0] == "ALLOW"
    assert engine.evaluate("sh", {})[0] == "ALLOW"  # missing attr, no over-block


def test_membership_in_list():
    policy = 'forbid(principal, action, resource) when { context.region in context.blocked };'
    engine = PolicyEngine([policy])
    assert engine.evaluate("t", {"region": "eu", "blocked": ["eu", "cn"]})[0] == "DENY"
    assert engine.evaluate("t", {"region": "us", "blocked": ["eu", "cn"]})[0] == "ALLOW"


def test_invalid_policy_is_skipped_not_fatal():
    engine = PolicyEngine(["this is garbage ;", REFUND])
    # The valid policy is still enforced.
    assert engine.evaluate("issue_refund", {"amount": 9999})[0] == "DENY"


def test_default_deny_posture():
    engine = PolicyEngine([], default_effect="deny")
    assert engine.evaluate("anything", {})[0] == "DENY"


def test_fail_open_posture_allows_indeterminate():
    engine = PolicyEngine([REFUND], fail_closed=False)
    # With fail_closed disabled, an unparseable present value does not block.
    assert engine.evaluate("issue_refund", {"amount": "abc"})[0] == "ALLOW"


def test_explicit_deny_wins_over_permit():
    policies = [
        'permit(principal, action, resource) when { context.tool_name == "t" };',
        'forbid(principal, action, resource) when { context.tool_name == "t" };',
    ]
    engine = PolicyEngine(policies)
    assert engine.evaluate("t", {})[0] == "DENY"


def test_invalid_default_effect_rejected():
    with pytest.raises(ValueError):
        PolicyEngine([], default_effect="maybe")


@pytest.mark.parametrize(
    "value,expected",
    [(10, 10.0), ("5,000", 5000.0), ("$9999", 9999.0), ("1_000", 1000.0), ("abc", None), (True, None), (None, None)],
)
def test_coerce_number(value, expected):
    assert _coerce_number(value) == expected


def test_parse_unterminated_block_raises():
    with pytest.raises(PolicyParseError):
        parse_policy_statement('forbid(principal, action, resource) when { context.x == "y" ')
