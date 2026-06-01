# Hardening the Data Plane: SDK Maturity Plan

You are absolutely right. The current structure of hardcoding security policies as strings in `packs.py` is amateurish for an enterprise security product, and the `Event loop is closed` telemetry bug signals that the SDK is not yet production-grade.

This implementation plan focuses entirely on **hardening the core Python SDK** to make it mature, robust, and truly ready to ship out-of-the-box.

## User Review Required
> [!IMPORTANT]
> **Action Required:** Please review the proposed structural changes and fixes below. Once approved, I will immediately execute them to stabilize the repository.

## Proposed Changes

---

### 1. Professional Policy Bundling

**Goal:** Move away from "simpleton" hardcoded strings. AgentShield should ship with a library of real `.cedar` files that developers can inspect, extend, and learn from.

#### [NEW] `packages/sdk-python/agentshield/policies/owasp.cedar`
#### [NEW] `packages/sdk-python/agentshield/policies/financial.cedar`
#### [NEW] `packages/sdk-python/agentshield/policies/pii.cedar`
- Create actual `.cedar` files containing the industry-standard guardrails.

#### [MODIFY] `packages/sdk-python/agentshield/packs.py`
- Refactor the `Packs` class to dynamically read `.cedar` files from the package directory using `importlib.resources`.
- This ensures the policies are properly bundled when the SDK is installed via pip, and allows users to easily reference or fork them.

#### [MODIFY] `packages/sdk-python/pyproject.toml`
- Ensure `include = ["agentshield/policies/*.cedar"]` is set so the policy files are packaged into the wheel.

---

### 2. Robust Telemetry Lifecycle (Fixing the Asyncio Bug)

**Goal:** Fix the `Event loop is closed` error during telemetry ingestion. The current implementation tries to mix `asyncio.run` with a globally instantiated `httpx.AsyncClient`, which causes event loop destruction errors in synchronous agent scripts.

#### [MODIFY] `packages/sdk-python/agentshield/client.py`
- **Synchronous Queueing:** Instead of hacky `asyncio.run` wrappers, we will implement a robust, thread-safe memory queue (`queue.Queue`).
- **Dedicated Background Worker:** The client will spin up a dedicated daemon `threading.Thread` that constantly consumes events from the queue and sends them to the Control Plane using a standard synchronous `httpx.Client`.
- **Graceful Shutdown:** This guarantees that telemetry is strictly "fire-and-forget" for the agent's main thread (zero latency impact) and never causes event loop crashes.

---

## Verification Plan

### Automated Tests
- Run `example.py` and verify that the `Event loop is closed` error is completely eliminated.
- Verify that the telemetry events still successfully reach the FastAPI backend without blocking the agent.

### Manual Verification
- Inspect the repository structure to confirm the presence of the `policies/` directory.
- Verify that `AgentShield.Packs.OWASP_TOP_10` correctly loads the contents of the `.cedar` file from disk.
