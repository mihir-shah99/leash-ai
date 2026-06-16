import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { CedarEvaluator } from "../src/engine.js";

const here = dirname(fileURLToPath(import.meta.url));
const casesPath = join(here, "..", "..", "conformance", "cases.json");

interface ConformanceCase {
  name: string;
  policies: string[];
  tool_name: string;
  args: Record<string, unknown>;
  default_effect?: "allow" | "deny";
  fail_closed?: boolean;
  expected: "ALLOW" | "DENY";
}

const cases: ConformanceCase[] = JSON.parse(readFileSync(casesPath, "utf-8")).cases;

describe("cross-SDK conformance", () => {
  for (const c of cases) {
    it(c.name, () => {
      const decision = CedarEvaluator.evaluate(c.policies, c.tool_name, c.args as Record<string, any>, {
        defaultEffect: c.default_effect ?? "allow",
        failClosed: c.fail_closed ?? true,
      });
      const got = decision.allowed ? "ALLOW" : "DENY";
      expect(got).toBe(c.expected);
    });
  }
});
