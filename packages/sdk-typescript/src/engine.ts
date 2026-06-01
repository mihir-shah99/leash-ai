export interface Decision {
  allowed: boolean;
  reason?: string;
}

export interface Condition {
  operator: string;
  key: string;
  value: any;
}

export class CircuitBreaker {
  private maxCalls: number;
  private timeWindowSec: number;
  private callHistory: Record<string, number[]> = {};

  constructor(maxCalls: number = 10, timeWindowSec: number = 60) {
    this.maxCalls = maxCalls;
    this.timeWindowSec = timeWindowSec;
  }

  public check(toolName: string): boolean {
    const now = Date.now() / 1000;
    if (!this.callHistory[toolName]) {
      this.callHistory[toolName] = [];
    }
    
    // Cleanup old timestamps
    this.callHistory[toolName] = this.callHistory[toolName].filter(ts => (now - ts) <= this.timeWindowSec);
    
    if (this.callHistory[toolName].length >= this.maxCalls) {
      return false; // Trip the breaker
    }
    
    this.callHistory[toolName].push(now);
    return true;
  }
}

export class CedarEvaluator {
  // A simplified Cedar policy evaluator for TS SDK
  // Policies are expected as a string like:
  // permit(principal, action == "Action::\"read\"", resource) when { resource.name == "config.json" };
  
  public static evaluate(policies: string[], toolName: string, args: Record<string, any>): Decision {
    if (!policies || policies.length === 0) {
      return { allowed: true }; // Default permit if no policies
    }
    
    let isPermitted = true;
    let reason = "Allowed by default";
    
    // Evaluate Deny rules first
    for (const policy of policies) {
      if (policy.trim().startsWith("forbid(")) {
        if (this.matches(policy, toolName, args)) {
          return { allowed: false, reason: `Blocked by policy: ${policy}` };
        }
      }
    }
    
    // If no forbid matched, it's allowed.
    return { allowed: isPermitted, reason };
  }
  
  private static matches(policy: string, toolName: string, args: Record<string, any>): boolean {
    // Very basic regex-based matching for MVP parity with the python AST engine
    // Real implementation would use a proper AST parser
    
    const actionMatch = policy.match(/action\s*==\s*"([^"]+)"/);
    if (actionMatch) {
      const pAction = actionMatch[1].replace("Action::\"", "").replace("\"", "");
      if (pAction !== toolName && pAction !== "*") {
        return false;
      }
    }
    
    // Check condition block
    const whenMatch = policy.match(/when\s*\{\s*(.*?)\s*\}/);
    if (whenMatch) {
      const conditionStr = whenMatch[1];
      // e.g., resource.path == "/etc/passwd"
      const condMatch = conditionStr.match(/resource\.([a-zA-Z0-9_]+)\s*(==|!=)\s*"([^"]+)"/);
      if (condMatch) {
        const key = condMatch[1];
        const op = condMatch[2];
        const val = condMatch[3];
        
        const actualVal = args[key];
        if (op === "==") {
          if (actualVal !== val) return false;
        } else if (op === "!=") {
          if (actualVal === val) return false;
        }
      }
    }
    
    return true;
  }
}

export class PolicyEngine {
  private circuitBreaker: CircuitBreaker;
  public policies: string[] = [];

  constructor() {
    this.circuitBreaker = new CircuitBreaker();
  }

  public updatePolicies(policies: string[]) {
    this.policies = policies;
  }

  public evaluate(toolName: string, args: Record<string, any>): Decision {
    // 1. Circuit Breaker
    if (!this.circuitBreaker.check(toolName)) {
      return { allowed: false, reason: `Circuit breaker tripped for tool: ${toolName}` };
    }
    
    // 2. Cedar Policies
    return CedarEvaluator.evaluate(this.policies, toolName, args);
  }
}
