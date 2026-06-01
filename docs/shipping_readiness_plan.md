# Shipping Readiness Plan

> A prioritized remediation plan covering everything that must be fixed before AgentShield
> can be considered shippable. Findings are ordered by **severity × need**, not by effort.
>
> Status legend: `[ ]` not started · `[~]` in progress · `[x]` done
>
> Severity tiers:
> - **P0 — Ship blocker / the product does not do what we sell.** Fix before any external use.
> - **P1 — Critical correctness or security gap.** Fix before any non-local deployment.
> - **P2 — Required for a credible private beta.** Fix before inviting design partners.
> - **P3 — Hardening & polish.** Fix before GA.

---

## Executive summary

The strategy is strong, but as an engineering artifact this is a demo, not a shippable
product. Several capabilities we actively sell are broken or faked in code:

- The flagship "deterministically block a refund over $500" guarantee is bypassable in
  seconds (string-formatted numbers, unsupported operators, parser crashes).
- The primary LangChain integration silently emits **zero** telemetry.
- "True NLP PII redaction" detects nothing in deep mode.
- Multi-tenancy, auth, and the "immutable signed audit trail" are stubs/leaks.
- There is no CI, no Dockerfiles, no reproducible build, and the compliance-template
  "moat" directories are empty.

This plan sequences the work to close the gap between the pitch and the code.

**Recommended gating:** do not run a private beta until all **P0** and **P1** items are
closed. Do not market "compliance" / "deterministic enforcement" until P0 is closed and
backed by the conformance test suite (P0-7).

---

## Progress log

### Sprint 1 — P0 ship blockers: ✅ COMPLETE

All eight P0 items are fixed and verified by tests.

| Item | Status | Verification |
|---|---|---|
| P0-1 Bypassable enforcement | ✅ | `"5,000"`, `"$9999"`, `"5_000"`, `" 600 "` now all DENY; covered in `test_engine.py` + conformance suite |
| P0-2 Engine crash on `&&`/multi-`==` | ✅ | Real parser; invalid statements skipped not fatal; `test_engine.py` |
| P0-3 Fake regex "Cedar AST" | ✅ | Rewrote `engine.py` as tokenizer + recursive-descent parser + typed evaluator (full `== != > >= < <= && \|\| in`, parens) |
| P0-4 Undefined fail posture | ✅ | `default_effect` + `fail_closed` config; missing-attr → not-applicable; indeterminate → fail closed; degraded sync now logs at WARNING |
| P0-5 LangChain zero telemetry | ✅ | Routed through `send_audit_event_fire_and_forget`; removed dead asyncio path |
| P0-6 `AgentShield()` crash | ✅ | `import os` added; `AgentShield()` constructs cleanly |
| P0-7 Divergent Py/TS dialects | ✅ | Both SDKs aligned to `context.*`; shared `packages/conformance/cases.json` (18 cases) passes in **both** Python (pytest) and TypeScript (vitest) |
| P0-8 No-op deep PII redaction | ✅ | `entities=None` in SDK + API; safe fallback on missing model |

Test results at time of writing: Python SDK `51 passed`, API `5 passed`, TS SDK
`18 passed`. Decision parity between the Python and TypeScript engines is enforced by the
shared conformance suite.

> Note on P0-3 decision: rather than take a heavy native dependency on the Rust
> `cedar-policy` engine inside the SDK, we implemented a self-contained parser/evaluator
> for a documented Cedar subset. This is testable, dependency-free, and identical across
> SDKs. Revisit binding the official engine if/when we need full Cedar semantics
> (entities, schema, `like`, sets) — tracked as a future item.

### Sprint 2 — P1 security core: ✅ COMPLETE (infra items deferred)

Per decision, this sprint covered the security core (P1-1/2/3/6). P1-5 (shared-state
circuit breaker — needs Redis) and P1-7 (MCP proxy transport rewrite — needs a design
decision) are intentionally deferred to their own PRs.

| Item | Status | Verification |
|---|---|---|
| P1-1 No auth on control plane | ✅ | Hashed-API-key Bearer auth; `get_current_tenant` dependency on all `/v1/*` routes; 401 on missing/invalid; `test_auth.py` |
| P1-2 Fake/leaky multi-tenancy | ✅ | tenant resolved from key (no more random ids); `/policies/sync` & list scoped to tenant + system policies only; telemetry scoped + attributed |
| P1-3 Dummy audit hash | ✅ | SHA-256 hash-chaining (`event_hash` = hash(canonical ‖ previous_hash)); tamper-evident; `test_audit_hash.py` incl. a chain-tamper detection test |
| P1-6 CORS misconfig + SQL echo leak | ✅ | CORS origins from `ALLOWED_ORIGINS` (no wildcard+credentials); `SQL_ECHO` defaults off |
| P1-5 Per-process circuit breaker | ⏸ Deferred | Needs shared state (Redis); own PR |
| P1-7 MCP proxy can't proxy | ⏸ Deferred | Needs transport redesign; own PR |

Supporting changes: removed dead/conflicting `models/core.py` (second `Base`); added
`api_key_hash`/`api_key_prefix` columns + Alembic migration `a1b2c3d4e5f6`; added
`scripts/create_tenant.py` to provision a tenant + key.

Test results: API `22 passed`, Python SDK `51 passed`, TS SDK `18 passed`.

> Note: telemetry/policy endpoints now require a valid API key. Mint one with
> `python -m scripts.create_tenant --name ... --slug ...` and pass it as the SDK's
> `api_key`. Local DB-backed integration tests run in CI once Postgres is wired (P2).

**Next:** Sprint 3 (P2 — CI, Dockerfiles/runnable stack, frontend config, compliance
packs) plus the deferred P1-5/P1-7.

---

## P0 — Ship blockers (the product must actually do what we claim)

### P0-1 · Deterministic policy enforcement is bypassable
- **What:** A `>`/`<` comparison against a formatted string silently fails open.
  `engine.py:58-60` does `float(actual_value)`; a `ValueError` is swallowed and treated
  as "condition not met," so the `forbid` never fires.
- **Proof:** `issue_refund(amount=10000)` → DENY (the demo), but `amount="5,000"` and
  `amount="$9999"` → **ALLOW**. The guarantee defeats itself with a comma.
- **Why it matters:** This is the core USP ("operational determinism for probabilistic
  AI"). If it can be bypassed by output formatting, we have no product.
- **Fix:**
  - Normalize/validate operand types before comparison (strip currency/grouping, coerce
    numerics; reject ambiguous values).
  - Treat unparseable operands as a **policy match failure that fails closed**, not open.
  - Add adversarial test vectors (`"5,000"`, `"$9999"`, `"5_000"`, `1e4`, `" 600 "`).
- **Effort:** S–M.

### P0-2 · A normal user-authored policy crashes the engine
- **What:** Any `when { ... }` term with two `==` in one `&&` clause hits
  `left, right = expr.split("==")` (`engine.py:27`) → `ValueError: too many values to
  unpack`. Construction of `PolicyEngine` throws.
- **Why it matters:** A CISO editing a policy in the dashboard can crash SDK policy
  loading. In the live-sync path the exception is caught at `debug` (`shield.py:84-86`),
  so **the SDK keeps enforcing the stale ruleset with no error surfaced.**
- **Fix:** Replace ad-hoc `str.split` parsing with a real tokenizer/parser (see P0-3),
  validate policies at author time in the API, and fail closed + alert on load errors
  rather than swallowing them.
- **Effort:** M (subsumed by P0-3).

### P0-3 · Replace the hand-rolled regex "Cedar AST" with a real evaluator
- **What:** `engine.py` only understands `==`, `>`, `<`, `in`. `!=`, `>=`, `<=`, `||`,
  parentheses, and set/record operations are silently dropped (`engine.py:41-42`), which
  produces wrong decisions (e.g. `role != "admin"` still blocks admins).
- **Why it matters:** "Mathematical Cedar AST parsing" is a stated differentiator. The
  current parser is neither Cedar nor sound.
- **Fix (choose one):**
  - **Preferred:** bind the official `cedar-policy` engine (Rust) via its Python
    bindings; treat policy strings as real Cedar.
  - **Interim:** implement a proper lexer/parser + typed evaluator with full operator
    support and explicit, documented semantics.
- **Decision needed:** real Cedar vs. controlled subset. This drives P0-7 and the TS SDK.
- **Effort:** L.

### P0-4 · Define the default enforcement posture (fail-open vs fail-closed)
- **What:** `engine.evaluate` returns `ALLOW` when there are no policies and when no
  `forbid` matched (`engine.py:96,116`). On control-plane unreachability the SDK runs on
  whatever packs it has (or nothing).
- **Why it matters:** A compliance product that defaults to ALLOW — and stays ALLOW when
  it can't reach the control plane — is a silent liability. This must be a deliberate,
  documented, configurable choice, not an accident.
- **Fix:** Make posture explicit per deployment (`fail_open` / `fail_closed`), default to
  fail-closed for governed action types, log/alert when running degraded, and surface the
  posture in telemetry.
- **Effort:** S–M.

### P0-5 · LangChain integration silently emits zero telemetry
- **What:** `integrations/langchain.py:78,81` call `self.shield.client.send_audit_event_async(...)`,
  a method that does not exist on `AgentShieldClient`. Every governed tool call raises
  `AttributeError`, which is caught and logged.
- **Why it matters:** LangChain is our headline "1 line of code" integration and the
  audit trail is the product. Enforcement happens but **no audit record is ever written.**
  Also contradicts task.md 2.4 ("remove all asyncio from the client").
- **Fix:** Route through the existing `send_audit_event_fire_and_forget` (thread-queue)
  path; delete the async/`asyncio.run` code. Add a test asserting an event reaches the
  queue/backend per governed call.
- **Effort:** S.

### P0-6 · `AgentShield()` crashes on default construction
- **What:** `shield.py:34,38` reference `os.environ` but `os` is never imported →
  `NameError`. Only works today because `example.py` passes both `api_key` and `base_url`.
- **Fix:** `import os`; add a smoke test that constructs `AgentShield()` with no args.
- **Effort:** XS.

### P0-7 · One Cedar dialect + shared conformance suite (Python ⇄ TypeScript)
- **What:** The Python engine matches `context.tool_name` / `context.*`; the TS engine
  (`engine.ts:70-95`) matches `action == "..."` / `resource.*`. The control-plane
  translator emits `context.*`, which the **TS SDK will never match.** Same policy,
  different (or no) enforcement per language.
- **Why it matters:** We sell cross-language governance. Divergent semantics make the
  guarantee meaningless and are impossible to audit.
- **Fix:** Pick the canonical dialect (output of P0-3), align both SDKs to it, and add a
  shared, language-agnostic conformance test suite (policy + input → expected decision)
  that both SDKs must pass in CI.
- **Effort:** M–L.

### P0-8 · "True NLP" PII redaction detects nothing in deep mode
- **What:** `pii.py:53` and `routers/telemetry.py:44` call
  `analyzer.analyze(text=..., entities=[], language='en')`. An empty `entities` list
  filters results to the empty set, so deep mode only catches the one hand-added SSN
  *regex* recognizer.
- **Why it matters:** "Local Presidio NLP redaction" is how we promise customers keep PHI
  private. Deep mode ≈ the regex we said we replaced — a real privacy gap.
- **Fix:** Pass `entities=None` (analyze all) or an explicit entity list; load the SpaCy
  model and verify NER actually fires; add tests with conversational/nested PII.
- **Effort:** S.

---

## P1 — Critical correctness & security (before any non-local deployment)

### P1-1 · No authentication on the control plane
- **What:** The SDK sends `Authorization: Bearer`, but no endpoint validates it
  (`routers/telemetry.py`, `routers/policies.py`).
- **Fix:** API-key/JWT auth dependency on all `/v1/*` routes; reject unauthenticated
  requests; derive tenant from the validated credential.
- **Effort:** M.

### P1-2 · Multi-tenancy is fake and leaks across tenants
- **What:** Ingest assigns a **random** `dummy_tenant_id`/`dummy_agent_id` per event
  (`telemetry.py:62-63`). `/policies/sync` returns **all enabled policies to every
  caller** with `tenant_id: "mock_tenant"` (`policies.py:45-54`).
- **Why it matters:** Cross-tenant policy disclosure; audit events not attributable.
- **Fix:** Derive `tenant_id` from auth (P1-1); scope every query by tenant; add a test
  proving tenant A cannot read tenant B's policies or events.
- **Effort:** M.

### P1-3 · "Immutable signed audit trail" is a constant string
- **What:** `telemetry.py:75` sets `event_hash="dummy_hash_for_mvp"`.
- **Why it matters:** The Evidence Vault / tamper-evidence is a listed moat and a
  compliance artifact auditors actually check.
- **Fix:** Compute a real per-event hash and chain it (hash of canonical event +
  previous hash) so the log is tamper-evident; document the scheme.
- **Effort:** M.

### P1-4 · CORS misconfiguration
- **What:** `main.py:11-17` sets `allow_origins=["*"]` with `allow_credentials=True` —
  invalid per spec and unsafe.
- **Fix:** Explicit allowed origins from config; drop the wildcard when credentials are
  allowed.
- **Effort:** XS.

### P1-5 · Circuit breaker is per-process and misnamed
- **What:** Docstring claims "Semantic Loop Detection" but logic is pure call-count /
  velocity and ignores arguments (`circuit_breaker.py:48`). State is in-memory per
  process, so with N workers the "60/min" limit is really 60×N and resets each deploy.
- **Fix:** Back limits with shared state (e.g. Redis) for multi-worker correctness;
  rename to reflect actual behavior; if we want semantic detection, add argument
  similarity/embedding-based loop detection as a separate, honestly-labeled feature.
- **Effort:** M.

### P1-6 · SQL logging leaks payloads in production
- **What:** `session.py:12` sets `echo=True`, logging all SQL (including action details)
  unconditionally.
- **Fix:** Drive `echo` from config; default off outside local dev.
- **Effort:** XS.

### P1-7 · MCP gateway cannot proxy as written
- **What:** `server.py:75-86` nests `stdio_server()` inside `stdio_client()` over the same
  process stdio; a transparent stdio proxy cannot bind both ends to one stdin/stdout.
- **Fix:** Re-architect the transport (separate streams/process boundaries); add an
  integration test that proxies a real downstream MCP server and blocks a tool call.
- **Effort:** M–L.

---

## P2 — Required for a credible private beta

### P2-1 · No CI/CD
- **What:** No `.github/workflows`. Nothing lints, type-checks, tests, or builds on push.
- **Fix:** Add CI running, per package: lint (ruff/eslint), typecheck (mypy/tsc), tests
  (pytest/vitest), and the P0-7 conformance suite. Block merge on failure.
- **Effort:** M.

### P2-2 · No reproducible build / runnable stack
- **What:** No Dockerfiles for API or web; `docker-compose.yml` only starts Postgres
  (obsolete `version: '3.8'`, hardcoded password) — the app can't actually be run.
- **Fix:** Dockerfiles for API and web; compose that brings up db + api + web; pin and
  verify dependency versions actually resolve on a clean machine (several pins —
  `pytest ^9`, `mypy ^2.1`, `ruff ^0.15`, `langchain-core ^1.4` — need confirmation).
- **Effort:** M.

### P2-3 · Tests that can't fail
- **What:** `test_cedar_engine.py`, `test_circuit_breaker.py`, `test_presidio.py` are
  `print()` scripts with no assertions. Real tests cover only happy paths.
- **Fix:** Convert to assertion-based tests; add the bypass/crash vectors from P0-1/P0-2;
  set a coverage floor in CI.
- **Effort:** M.

### P2-4 · Frontend is not deployable
- **What:** `Dashboard.tsx:33` hardcodes `http://localhost:8000`.
- **Fix:** API base URL from build/runtime config (`VITE_API_BASE_URL`); add `.env.example`.
- **Effort:** S.

### P2-5 · Dead/unwired code
- **What:** `discovery.py` router is implemented but never included in `main.py` and
  hardcodes `tenant-1234-abcd`.
- **Fix:** Either wire it up behind auth/tenancy or remove it until ready.
- **Effort:** S.

### P2-6 · The compliance-template "moat" is empty
- **What:** `policies/hipaa`, `pci_dss`, `sox`, `base_security` contain only `.gitkeep`.
  The differentiator ("regulatory knowledge encoded as product") has no content.
- **Fix:** Author and validate at least one real, tested pack per launch framework, each
  passing the P0-7 conformance suite.
- **Effort:** L (domain work).

---

## P3 — Hardening & polish (before GA)

- **P3-1 · Async LangChain (`_arun`) + streaming coverage** — confirm the callback path
  covers async tools, not just sync.
- **P3-2 · Remove unused/incorrect deps** — e.g. `psycopg2-binary` while the app uses
  `asyncpg`; audit both lockfiles.
- **P3-3 · Replace anonymous `type('Decision', ...)` objects** (`shield.py:105,124,126`)
  with a typed dataclass/Pydantic model shared across call paths.
- **P3-4 · Telemetry durability** — fire-and-forget drops events on backpressure/crash;
  consider disk-backed spooling and retry with backoff for the audit trail.
- **P3-5 · Docs & DX** — real SDK README (currently one line), quickstart, config
  reference, `LICENSE` (docs claim MIT — confirm a license file ships).
- **P3-6 · `datetime.utcnow()` deprecation** (`client.py:60`) → timezone-aware UTC.
- **P3-7 · Observability** — structured logging, metrics, health/readiness probes beyond
  the single `/health`.

---

## Suggested sequencing

1. **Sprint 1 — Make the guarantee real (P0):** P0-6, P0-5, P0-8 (quick, high-impact),
   then P0-3 → P0-1/P0-2/P0-4 → P0-7. Exit: the determinism demo cannot be bypassed and
   both SDKs pass one conformance suite.
2. **Sprint 2 — Make it safe to host (P1):** P1-1 → P1-2 → P1-3, then P1-4/P1-6 (quick),
   P1-5, P1-7. Exit: authenticated, tenant-isolated, tamper-evident, deployable safely.
3. **Sprint 3 — Make it shippable to design partners (P2):** P2-1/P2-2 (CI + Docker),
   P2-3, P2-4/P2-5, then begin P2-6. Exit: reproducible build, green CI, one real
   compliance pack.
4. **Ongoing — P3** alongside the above as capacity allows.

## Definition of "shippable" (exit criteria)

- [ ] All **P0** and **P1** items closed.
- [ ] Determinism demo resists the documented bypass vectors; engine fails **closed**.
- [ ] Python and TS SDKs pass a shared conformance suite in CI.
- [ ] Auth + tenant isolation enforced and tested (no cross-tenant reads).
- [ ] Audit events are tamper-evident with real hashes.
- [ ] Green CI (lint + typecheck + tests + conformance) on every PR.
- [ ] `docker compose up` brings up the full stack from a clean checkout.
- [ ] At least one real, tested compliance pack shipped.
</content>
</invoke>
