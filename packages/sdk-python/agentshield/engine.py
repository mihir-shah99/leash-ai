"""AgentShield local policy engine.

A self-contained evaluator for a well-defined subset of Cedar policy syntax.
It replaces the previous string-splitting prototype that (a) crashed on any
clause containing two ``==``, (b) silently dropped ``!=``/``>=``/``<=``/``||``
conditions, and (c) let numeric guardrails be bypassed with formatted values
such as ``"5,000"`` or ``"$9999"``.

Supported grammar (inside ``when {{ ... }}`` / ``unless {{ ... }}``)::

    expr   := or
    or     := and ( "||" and )*
    and    := cmp ( "&&" cmp )*
    cmp    := primary ( OP primary )?
    primary:= "(" expr ")" | literal | attribute
    OP     := == | != | > | >= | < | <= | in
    literal:= STRING | NUMBER | true | false
    attr   := IDENT ( "." IDENT )*

Evaluation semantics (documented and deliberate):

* **Explicit deny wins.** Any matching ``forbid`` -> DENY. Otherwise any
  matching ``permit`` -> ALLOW. Otherwise the configured ``default_effect``.
* **Missing attributes do not match.** Referencing a context key that was not
  supplied makes the comparison ``False`` (the policy is simply not applicable).
  This prevents an ``amount``-based rule from firing on tools that have no
  ``amount``.
* **Indeterminate comparisons fail closed.** When an attribute *is* present but
  cannot be coerced for the operator (e.g. ``amount = "abc"`` against ``> 500``),
  the comparison resolves toward the safe direction: ``True`` inside a
  ``forbid`` (block it) and ``False`` inside a ``permit`` (don't grant it) when
  ``fail_closed`` is set (the default).
* **Numeric coercion.** ``>``/``>=``/``<``/``<=`` and numeric ``==``/``!=``
  strip currency symbols, thousands separators and underscores, so ``"5,000"``,
  ``"$9999"`` and ``5000`` all compare numerically.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Sentinel for "attribute referenced but not present in the request context".
class _Missing:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):  # pragma: no cover - debug aid
        return "MISSING"


MISSING = _Missing()


# --------------------------------------------------------------------------- #
# Tokenizer
# --------------------------------------------------------------------------- #

_TOKEN_RE = re.compile(
    r"""
      (?P<WS>\s+)
    | (?P<STRING>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')
    | (?P<NUMBER>-?\d+(?:\.\d+)?)
    | (?P<OP>==|!=|>=|<=|>|<|&&|\|\|)
    | (?P<LPAREN>\()
    | (?P<RPAREN>\))
    | (?P<IDENT>[A-Za-z_][A-Za-z0-9_.]*)
    """,
    re.VERBOSE,
)

_KEYWORD_OPS = {"in"}
_BOOLS = {"true": True, "false": False}


@dataclass
class Token:
    kind: str
    value: str


def _tokenize(text: str) -> List[Token]:
    tokens: List[Token] = []
    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise PolicyParseError(f"Unexpected character at offset {pos}: {text[pos:pos + 12]!r}")
        pos = m.end()
        kind = m.lastgroup
        value = m.group()
        if kind == "WS":
            continue
        if kind == "IDENT":
            low = value.lower()
            if low in _KEYWORD_OPS:
                tokens.append(Token("OP", low))
                continue
            if low in _BOOLS:
                tokens.append(Token("BOOL", low))
                continue
        tokens.append(Token(kind, value))
    return tokens


# --------------------------------------------------------------------------- #
# AST
# --------------------------------------------------------------------------- #

class Node:
    pass


@dataclass
class Literal(Node):
    value: Any


@dataclass
class Attribute(Node):
    path: str  # e.g. "context.amount"


@dataclass
class Compare(Node):
    op: str
    left: Node
    right: Node


@dataclass
class BoolOp(Node):
    op: str  # "&&" or "||"
    parts: List[Node]


class PolicyParseError(ValueError):
    """Raised when a policy statement cannot be parsed."""


# --------------------------------------------------------------------------- #
# Parser (recursive descent)
# --------------------------------------------------------------------------- #

class _Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.i = 0

    def _peek(self) -> Optional[Token]:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def _next(self) -> Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def parse(self) -> Node:
        node = self._or()
        if self._peek() is not None:
            raise PolicyParseError(f"Unexpected trailing token: {self._peek()}")
        return node

    def _or(self) -> Node:
        parts = [self._and()]
        while self._peek() and self._peek().kind == "OP" and self._peek().value == "||":
            self._next()
            parts.append(self._and())
        return parts[0] if len(parts) == 1 else BoolOp("||", parts)

    def _and(self) -> Node:
        parts = [self._cmp()]
        while self._peek() and self._peek().kind == "OP" and self._peek().value == "&&":
            self._next()
            parts.append(self._cmp())
        return parts[0] if len(parts) == 1 else BoolOp("&&", parts)

    def _cmp(self) -> Node:
        left = self._primary()
        tok = self._peek()
        if tok and tok.kind == "OP" and tok.value not in ("&&", "||"):
            op = self._next().value
            right = self._primary()
            return Compare(op, left, right)
        return left

    def _primary(self) -> Node:
        tok = self._peek()
        if tok is None:
            raise PolicyParseError("Unexpected end of expression")
        if tok.kind == "LPAREN":
            self._next()
            node = self._or()
            closing = self._peek()
            if not closing or closing.kind != "RPAREN":
                raise PolicyParseError("Missing closing parenthesis")
            self._next()
            return node
        if tok.kind == "STRING":
            self._next()
            return Literal(_unquote(tok.value))
        if tok.kind == "NUMBER":
            self._next()
            return Literal(float(tok.value) if "." in tok.value else int(tok.value))
        if tok.kind == "BOOL":
            self._next()
            return Literal(_BOOLS[tok.value])
        if tok.kind == "IDENT":
            self._next()
            return Attribute(tok.value)
        raise PolicyParseError(f"Unexpected token: {tok}")


def _unquote(s: str) -> str:
    inner = s[1:-1]
    return inner.replace('\\"', '"').replace("\\'", "'").replace("\\\\", "\\")


# --------------------------------------------------------------------------- #
# Number coercion
# --------------------------------------------------------------------------- #

_NUM_CLEAN_RE = re.compile(r"[,_\s]")


def _coerce_number(value: Any) -> Optional[float]:
    """Best-effort numeric coercion. Returns None if not interpretable."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        # Strip a leading currency symbol and grouping characters.
        s = s.lstrip("$£€¥").strip()
        s = _NUM_CLEAN_RE.sub("", s)
        if s == "":
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


# --------------------------------------------------------------------------- #
# Policy + Engine
# --------------------------------------------------------------------------- #

@dataclass
class Policy:
    effect: str  # "permit" | "forbid"
    when: Optional[Node]
    unless: Optional[Node]
    source: str

    def matches(self, context: Dict[str, Any], fail_closed: bool) -> bool:
        ev = _Evaluator(context, self.effect, fail_closed)
        if self.when is not None and not ev.truth(self.when):
            return False
        if self.unless is not None and ev.truth(self.unless):
            return False
        return True


class _Evaluator:
    def __init__(self, context: Dict[str, Any], effect: str, fail_closed: bool):
        self.context = context
        self.effect = effect
        self.fail_closed = fail_closed

    def truth(self, node: Node) -> bool:
        if isinstance(node, BoolOp):
            if node.op == "&&":
                return all(self.truth(p) for p in node.parts)
            return any(self.truth(p) for p in node.parts)
        if isinstance(node, Compare):
            return self._compare(node)
        if isinstance(node, (Literal, Attribute)):
            # A bare value/attribute used as a boolean condition.
            val = self._value(node)
            if val is MISSING:
                return False
            return bool(val)
        raise PolicyParseError(f"Cannot evaluate node: {node!r}")

    def _value(self, node: Node) -> Any:
        if isinstance(node, Literal):
            return node.value
        if isinstance(node, Attribute):
            return self._resolve(node.path)
        raise PolicyParseError(f"Not a value node: {node!r}")

    def _resolve(self, path: str) -> Any:
        # "context.amount" -> look up "amount"; bare "principal"/"resource"/"action"
        # and unknown prefixes fall through to a direct context lookup.
        key = path.split(".", 1)[1] if path.startswith("context.") else path
        return self.context.get(key, MISSING)

    def _indeterminate(self) -> bool:
        """Result for a comparison we cannot evaluate, in the safe direction."""
        if not self.fail_closed:
            return False
        return self.effect == "forbid"

    def _compare(self, node: Compare) -> bool:
        left = self._value(node.left)
        right = self._value(node.right)
        op = node.op

        if op == "in":
            # `left in right`: substring (str) or membership (list/tuple/set).
            if right is MISSING or left is MISSING:
                return False
            if isinstance(right, (list, tuple, set)):
                return left in right
            return str(left) in str(right)

        # Missing attribute -> policy not applicable (never matches).
        if left is MISSING or right is MISSING:
            return False

        ln, rn = _coerce_number(left), _coerce_number(right)

        if op in (">", ">=", "<", "<="):
            if ln is None or rn is None:
                return self._indeterminate()
            if op == ">":
                return ln > rn
            if op == ">=":
                return ln >= rn
            if op == "<":
                return ln < rn
            return ln <= rn

        if op in ("==", "!="):
            if ln is not None and rn is not None:
                eq = ln == rn
            else:
                eq = str(left) == str(right)
            return eq if op == "==" else not eq

        raise PolicyParseError(f"Unsupported operator: {op}")


_STMT_SPLIT_HINT = re.compile(r"\b(permit|forbid)\s*\(", re.IGNORECASE)


def _split_statements(content: str) -> List[str]:
    """Split a policy document into individual statements.

    Quote- and brace-aware so that ``;`` inside a string literal or a ``{}``
    block does not terminate a statement prematurely.
    """
    statements: List[str] = []
    buf: List[str] = []
    depth = 0
    quote: Optional[str] = None
    i = 0
    while i < len(content):
        ch = content[i]
        buf.append(ch)
        if quote:
            if ch == "\\" and i + 1 < len(content):
                buf.append(content[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        elif ch == ";" and depth == 0:
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def _extract_block(stmt: str, keyword: str) -> Optional[str]:
    """Extract the body of a ``when { ... }`` / ``unless { ... }`` clause."""
    m = re.search(rf"\b{keyword}\b\s*\{{", stmt)
    if not m:
        return None
    start = m.end()
    depth = 1
    quote: Optional[str] = None
    i = start
    while i < len(stmt):
        ch = stmt[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return stmt[start:i]
        i += 1
    raise PolicyParseError(f"Unterminated '{keyword}' block")


def parse_policy_statement(stmt: str) -> Policy:
    stmt = stmt.strip().rstrip(";").strip()
    lowered = stmt.lower()
    if lowered.startswith("permit"):
        effect = "permit"
    elif lowered.startswith("forbid"):
        effect = "forbid"
    else:
        raise PolicyParseError("Statement must start with 'permit' or 'forbid'")

    when_body = _extract_block(stmt, "when")
    unless_body = _extract_block(stmt, "unless")

    when_node = _Parser(_tokenize(when_body)).parse() if when_body and when_body.strip() else None
    unless_node = _Parser(_tokenize(unless_body)).parse() if unless_body and unless_body.strip() else None

    return Policy(effect=effect, when=when_node, unless=unless_node, source=stmt)


class PolicyEngine:
    """Cedar-subset policy evaluation engine.

    :param tenant_policies: optional list of policy document strings to load.
    :param default_effect: decision when no policy matches. ``"allow"`` matches
        AgentShield's blacklist guardrail packs; set to ``"deny"`` for a strict
        allowlist posture.
    :param fail_closed: when True (default), indeterminate comparisons resolve
        toward the safe direction (block for ``forbid``).
    """

    def __init__(
        self,
        tenant_policies: Optional[List[str]] = None,
        default_effect: str = "allow",
        fail_closed: bool = True,
    ):
        if default_effect not in ("allow", "deny"):
            raise ValueError("default_effect must be 'allow' or 'deny'")
        self.default_effect = default_effect
        self.fail_closed = fail_closed
        self.policies: List[Policy] = []
        if tenant_policies:
            for p in tenant_policies:
                self.load_policy(p)

    def load_policy(self, policy_content: str) -> int:
        """Parse and add policies from a document. Returns the number loaded.

        Invalid statements are skipped with a warning rather than crashing the
        engine, so one malformed policy can never take down enforcement.
        """
        loaded = 0
        for stmt in _split_statements(policy_content):
            try:
                policy = parse_policy_statement(stmt)
            except PolicyParseError as e:
                logger.warning(f"Skipping invalid policy statement: {e} | source={stmt!r}")
                continue
            self.policies.append(policy)
            loaded += 1
            logger.info(f"Loaded Cedar policy with effect: {policy.effect}")
        return loaded

    def evaluate(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[str, List[str]]:
        """Evaluate a tool execution against all loaded policies.

        Returns ``(decision, violations)`` where decision is ``"ALLOW"`` or
        ``"DENY"``.
        """
        context: Dict[str, Any] = {"tool_name": tool_name}
        if isinstance(arguments, dict):
            context.update(arguments)

        permitted = False
        for policy in self.policies:
            try:
                if not policy.matches(context, self.fail_closed):
                    continue
            except PolicyParseError as e:
                # A policy that parsed but errored at eval time: fail closed for
                # forbid (treat as a block) so we never silently allow.
                logger.warning(f"Policy evaluation error ({e}); source={policy.source!r}")
                if policy.effect == "forbid" and self.fail_closed:
                    return "DENY", [f"Action blocked by policy (evaluation error): {policy.source}"]
                continue

            if policy.effect == "forbid":
                return "DENY", [f"Action blocked by policy: {policy.source}"]
            permitted = True

        if permitted:
            return "ALLOW", []
        if self.default_effect == "deny":
            return "DENY", ["Denied by default policy posture (no matching permit)."]
        return "ALLOW", []
