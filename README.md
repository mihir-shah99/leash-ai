# AgentShield 🛡️

**The Enterprise-Grade, Zero-Latency Security Gateway for Autonomous AI Agents.**

AgentShield is a lightweight, framework-agnostic Policy Decision Point (PDP) that enforces mathematically precise access controls on LLM tool executions *before* they run. It brings enterprise security, compliance, and tamper-proof auditing to autonomous agents running on Python, TypeScript, or the Model Context Protocol (MCP).

---

## Why AgentShield?

When you give an LLM access to tools (databases, internal APIs, file systems), prompt injection becomes a catastrophic risk. Traditional Web Application Firewalls (WAFs) are blind to application-level logic (e.g., they don't know that an LLM issuing a $10,000 refund violates a $500 budget policy).

AgentShield solves this by operating at the **Application Logic Boundary**:
1. **Deterministic Local Guardrails (<2ms):** Rules are written in **AWS Cedar** and evaluated locally in-memory. Zero network latency tax on your agents.
2. **Thread-Safe Telemetry:** Solves the notorious Python `asyncio` "Event loop is closed" crash. Our background queueing daemon ensures telemetry logging never blocks your agent's execution thread.
3. **Hybrid PII Redaction:** Fast, edge-based regex scrubbing combined with deep NLP (Microsoft Presidio) ensures no customer PII ever leaks into your audit logs.
4. **Cloud-Neutral:** Runs securely inside AWS Lambda, Vercel Edge, Azure, or on-prem. You are not locked into proprietary cloud infrastructures like Google VPC-SC or NVIDIA DGX sandboxes.

---

## 🏗️ Architecture overview

AgentShield consists of two primary layers:

### 1. The Data Plane (Local Execution)
*   **Python SDK (`packages/sdk-python`)**: Native decorator-based security (`@shield.govern`) for LangChain, CrewAI, and custom scripts.
*   **TypeScript SDK (`packages/sdk-typescript`)**: Vercel AI SDK adapters and local circuit breakers.
*   **MCP Gateway (`packages/mcp-gateway`)**: A universal proxy server that intercepts `CallToolRequest` events for *any* standard MCP tool server (Cursor, Claude Desktop, etc.) without requiring code changes.

### 2. The Control Plane (Managed SaaS)
*   **FastAPI Backend (`apps/api`)**: Ingests high-throughput telemetry, manages PostgreSQL databases, serves dynamic Cedar policies, and provides AI-driven Natural Language to Cedar translation.
*   **React Dashboard (`apps/web`)**: A premium, glassmorphism web interface for SecOps teams to monitor live interception feeds, compliance scores, and rule deployments.

---

## 🚀 Quickstart

### Option A: Python Developers (3-Line Integration)
No need to rewrite your agent logic. Simply decorate your existing tools.

```python
from agentshield import AgentShield

# 1. Initialize with an out-of-the-box local pack
shield = AgentShield(
    api_key="your_api_key",
    guardrails=[{"name": "financial_safety", "content": AgentShield.Packs.FINANCIAL}]
)

# 2. Decorate your existing tool
@shield.govern("issue_refund")
def issue_refund(amount: float, customer_id: str):
    return {"status": "success"}

# 3. If an LLM tries to call issue_refund with amount=10000,
# AgentShield evaluates the Cedar policy and throws a PolicyViolationError locally.
```

### Option B: Universal MCP Proxy (Zero-Code)
Secure any existing MCP server by wrapping its startup command with our gateway.

```bash
mcp-gateway npx -y @modelcontextprotocol/server-postgres postgresql://localhost/test
```
*The gateway intercepts all tool calls requested by the LLM client and evaluates them against your local Cedar policies before passing them to the target server.*

---

## 🛠️ Local Development & Running the Control Plane

To spin up the full Control Plane (API and Dashboard) locally:

1. **Start the FastAPI Backend**
   ```bash
   cd apps/api
   poetry install
   poetry run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Start the React Dashboard**
   ```bash
   cd apps/web
   npm install
   npm run dev
   ```
   Navigate to `http://localhost:5173` to view the live telemetry matrix and policy engine.

---

## 📜 License
AgentShield is open-source and released under the [MIT License](LICENSE).
