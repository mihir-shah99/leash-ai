import { AgentShieldClient } from "./client.js";

/**
 * Adapter for Vercel AI SDK `tool()` function.
 * Wraps an existing tool definition and injects AgentShield checks.
 */
export function withAgentShield<TArgs, TResult>(
  shield: AgentShieldClient,
  toolName: string,
  toolDef: {
    description: string;
    parameters: any;
    execute: (args: TArgs) => Promise<TResult> | TResult;
  }
) {
  return {
    description: toolDef.description,
    parameters: toolDef.parameters,
    execute: async (args: TArgs) => {
      const decision = shield.checkAction(toolName, args as any);
      if (!decision.allowed) {
        throw new Error(`AgentShield blocked action: ${decision.reason}`);
      }
      return toolDef.execute(args);
    }
  };
}
