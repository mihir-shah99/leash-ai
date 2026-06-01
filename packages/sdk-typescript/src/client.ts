import fetch from "node-fetch";
import { PolicyEngine } from "./engine.js";

export class AgentShieldClient {
  private engine: PolicyEngine;
  private apiKey: string;
  private baseUrl: string;
  private pollIntervalMs: number;
  private timer: NodeJS.Timeout | null = null;

  constructor(apiKey: string, baseUrl: string = "http://localhost:8000", pollIntervalMs: number = 30000) {
    this.apiKey = apiKey;
    this.baseUrl = baseUrl;
    this.pollIntervalMs = pollIntervalMs;
    this.engine = new PolicyEngine();
    
    // Start background sync
    this.startSync();
  }

  private async fetchPolicies() {
    try {
      const response = await fetch(`${this.baseUrl}/v1/policies/sync`, {
        headers: {
          "Authorization": `Bearer ${this.apiKey}`
        }
      });
      
      if (response.ok) {
        // The control plane returns policy objects ({ id, name, content, language });
        // older builds returned bare strings. Accept both and extract the Cedar text.
        const data = (await response.json()) as {
          policies?: Array<string | { content?: string }>;
        };
        if (data.policies) {
          const contents = data.policies
            .map((p) => (typeof p === "string" ? p : p?.content ?? ""))
            .filter((c) => c.trim().length > 0);
          this.engine.updatePolicies(contents);
        }
      } else {
        console.error("[AgentShield] Failed to sync policies:", response.statusText);
      }
    } catch (e) {
      console.error("[AgentShield] Error syncing policies:", e);
    }
  }

  public startSync() {
    if (this.timer) {
      clearInterval(this.timer);
    }
    // Initial fetch
    this.fetchPolicies();
    // Start loop
    this.timer = setInterval(() => this.fetchPolicies(), this.pollIntervalMs);
  }

  public stopSync() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  public checkAction(toolName: string, args: Record<string, any>) {
    return this.engine.evaluate(toolName, args);
  }
}
