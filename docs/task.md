# SDK Hardening Tasks

## 1. Professional Policy Bundling
- `[x]` 1.1 Create `agentshield/policies/` directory.
- `[x]` 1.2 Create `owasp.cedar`, `financial.cedar`, and `pii.cedar` files.
- `[x]` 1.3 Refactor `packs.py` to dynamically load `.cedar` files using `importlib.resources`.
- `[x]` 1.4 Update `pyproject.toml` to include `*.cedar` files in the package.

## 2. Robust Telemetry Lifecycle
- `[x]` 2.1 Refactor `AgentShieldClient` in `client.py`.
- `[x]` 2.2 Implement a thread-safe memory queue (`queue.Queue`).
- `[x]` 2.3 Spin up a dedicated `threading.Thread` daemon for synchronous telemetry processing.
- `[x]` 2.4 Remove all `asyncio` dependencies from the client to prevent event loop crashes.

## 3. Verification
- `[x]` 3.1 Run `example.py` to ensure the `Event loop is closed` error is eliminated.
- `[x]` 3.2 Verify that telemetry successfully reaches the FastAPI backend.
