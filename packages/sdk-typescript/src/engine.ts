// AgentShield TypeScript policy engine.
//
// This mirrors the Python engine's Cedar-subset semantics so a policy authored
// once in the control plane enforces identically in both SDKs:
//   * dialect: conditions reference `context.<attr>` (and `context.tool_name`)
//   * operators: == != > >= < <= && || in
//   * numeric coercion: "5,000" / "$9999" / 5000 compare numerically
//   * missing attribute -> condition is false (policy not applicable)
//   * indeterminate comparison -> fail closed for `forbid`
//   * explicit deny wins; otherwise permit; otherwise the default effect

export interface Decision {
  allowed: boolean;
  reason?: string;
}

export interface Condition {
  operator: string;
  key: string;
  value: any;
}

const MISSING = Symbol("MISSING");

export class CircuitBreaker {
  private maxCalls: number;
  private timeWindowSec: number;
  private callHistory: Record<string, number[]> = {};

  constructor(maxCalls: number = 60, timeWindowSec: number = 60) {
    this.maxCalls = maxCalls;
    this.timeWindowSec = timeWindowSec;
  }

  public check(toolName: string): boolean {
    const now = Date.now() / 1000;
    if (!this.callHistory[toolName]) {
      this.callHistory[toolName] = [];
    }
    this.callHistory[toolName] = this.callHistory[toolName].filter(
      (ts) => now - ts <= this.timeWindowSec
    );
    if (this.callHistory[toolName].length >= this.maxCalls) {
      return false;
    }
    this.callHistory[toolName].push(now);
    return true;
  }
}

// --------------------------------------------------------------------------- //
// Tokenizer / parser
// --------------------------------------------------------------------------- //

type Token = { kind: string; value: string };

const TOKEN_RE =
  /\s+|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(-?\d+(?:\.\d+)?)|(==|!=|>=|<=|>|<|&&|\|\|)|(\()|(\))|([A-Za-z_][A-Za-z0-9_.]*)/y;

function tokenize(text: string): Token[] {
  const tokens: Token[] = [];
  TOKEN_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  let lastIndex = 0;
  while (lastIndex < text.length) {
    TOKEN_RE.lastIndex = lastIndex;
    m = TOKEN_RE.exec(text);
    if (!m) {
      throw new Error(`Unexpected character at ${lastIndex}: ${text.slice(lastIndex, lastIndex + 12)}`);
    }
    lastIndex = TOKEN_RE.lastIndex;
    const [, str, num, op, lp, rp, ident] = m;
    if (str !== undefined) tokens.push({ kind: "STRING", value: str });
    else if (num !== undefined) tokens.push({ kind: "NUMBER", value: num });
    else if (op !== undefined) tokens.push({ kind: "OP", value: op });
    else if (lp !== undefined) tokens.push({ kind: "LPAREN", value: lp });
    else if (rp !== undefined) tokens.push({ kind: "RPAREN", value: rp });
    else if (ident !== undefined) {
      const low = ident.toLowerCase();
      if (low === "in") tokens.push({ kind: "OP", value: "in" });
      else if (low === "true" || low === "false") tokens.push({ kind: "BOOL", value: low });
      else tokens.push({ kind: "IDENT", value: ident });
    }
    // whitespace match: skip
  }
  return tokens;
}

type Node =
  | { t: "lit"; value: any }
  | { t: "attr"; path: string }
  | { t: "cmp"; op: string; left: Node; right: Node }
  | { t: "bool"; op: string; parts: Node[] };

class Parser {
  private i = 0;
  constructor(private tokens: Token[]) {}

  private peek(): Token | undefined {
    return this.tokens[this.i];
  }
  private next(): Token {
    return this.tokens[this.i++];
  }

  parse(): Node {
    const node = this.or();
    if (this.peek()) throw new Error(`Unexpected trailing token: ${this.peek()!.value}`);
    return node;
  }

  private or(): Node {
    const parts = [this.and()];
    while (this.peek() && this.peek()!.kind === "OP" && this.peek()!.value === "||") {
      this.next();
      parts.push(this.and());
    }
    return parts.length === 1 ? parts[0] : { t: "bool", op: "||", parts };
  }

  private and(): Node {
    const parts = [this.cmp()];
    while (this.peek() && this.peek()!.kind === "OP" && this.peek()!.value === "&&") {
      this.next();
      parts.push(this.cmp());
    }
    return parts.length === 1 ? parts[0] : { t: "bool", op: "&&", parts };
  }

  private cmp(): Node {
    const left = this.primary();
    const tok = this.peek();
    if (tok && tok.kind === "OP" && tok.value !== "&&" && tok.value !== "||") {
      const op = this.next().value;
      const right = this.primary();
      return { t: "cmp", op, left, right };
    }
    return left;
  }

  private primary(): Node {
    const tok = this.peek();
    if (!tok) throw new Error("Unexpected end of expression");
    if (tok.kind === "LPAREN") {
      this.next();
      const node = this.or();
      if (!this.peek() || this.peek()!.kind !== "RPAREN") throw new Error("Missing closing parenthesis");
      this.next();
      return node;
    }
    if (tok.kind === "STRING") {
      this.next();
      return { t: "lit", value: unquote(tok.value) };
    }
    if (tok.kind === "NUMBER") {
      this.next();
      return { t: "lit", value: Number(tok.value) };
    }
    if (tok.kind === "BOOL") {
      this.next();
      return { t: "lit", value: tok.value === "true" };
    }
    if (tok.kind === "IDENT") {
      this.next();
      return { t: "attr", path: tok.value };
    }
    throw new Error(`Unexpected token: ${tok.value}`);
  }
}

function unquote(s: string): string {
  return s.slice(1, -1).replace(/\\"/g, '"').replace(/\\'/g, "'").replace(/\\\\/g, "\\");
}

function coerceNumber(value: any): number | null {
  if (typeof value === "boolean") return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "string") {
    let s = value.trim().replace(/^[$£€¥]/, "").trim().replace(/[,_\s]/g, "");
    if (s === "") return null;
    const n = Number(s);
    return Number.isNaN(n) ? null : n;
  }
  return null;
}

// --------------------------------------------------------------------------- //
// Policy + evaluation
// --------------------------------------------------------------------------- //

interface Policy {
  effect: "permit" | "forbid";
  when: Node | null;
  unless: Node | null;
  source: string;
}

function extractBlock(stmt: string, keyword: string): string | null {
  const re = new RegExp(`\\b${keyword}\\b\\s*\\{`);
  const m = re.exec(stmt);
  if (!m) return null;
  let depth = 1;
  let quote: string | null = null;
  let i = m.index + m[0].length;
  const start = i;
  for (; i < stmt.length; i++) {
    const ch = stmt[i];
    if (quote) {
      if (ch === "\\") {
        i++;
        continue;
      }
      if (ch === quote) quote = null;
    } else if (ch === '"' || ch === "'") quote = ch;
    else if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) return stmt.slice(start, i);
    }
  }
  throw new Error(`Unterminated '${keyword}' block`);
}

function splitStatements(content: string): string[] {
  const statements: string[] = [];
  let buf = "";
  let depth = 0;
  let quote: string | null = null;
  for (let i = 0; i < content.length; i++) {
    const ch = content[i];
    buf += ch;
    if (quote) {
      if (ch === "\\" && i + 1 < content.length) {
        buf += content[i + 1];
        i++;
        continue;
      }
      if (ch === quote) quote = null;
    } else if (ch === '"' || ch === "'") quote = ch;
    else if (ch === "{") depth++;
    else if (ch === "}") depth = Math.max(0, depth - 1);
    else if (ch === ";" && depth === 0) {
      const s = buf.trim();
      if (s) statements.push(s);
      buf = "";
    }
  }
  const tail = buf.trim();
  if (tail) statements.push(tail);
  return statements;
}

function parseStatement(stmt: string): Policy {
  const trimmed = stmt.trim().replace(/;+\s*$/, "").trim();
  const lowered = trimmed.toLowerCase();
  let effect: "permit" | "forbid";
  if (lowered.startsWith("permit")) effect = "permit";
  else if (lowered.startsWith("forbid")) effect = "forbid";
  else throw new Error("Statement must start with 'permit' or 'forbid'");

  const whenBody = extractBlock(trimmed, "when");
  const unlessBody = extractBlock(trimmed, "unless");
  const when = whenBody && whenBody.trim() ? new Parser(tokenize(whenBody)).parse() : null;
  const unless = unlessBody && unlessBody.trim() ? new Parser(tokenize(unlessBody)).parse() : null;
  return { effect, when, unless, source: trimmed };
}

class Evaluator {
  constructor(
    private context: Record<string, any>,
    private effect: "permit" | "forbid",
    private failClosed: boolean
  ) {}

  truth(node: Node): boolean {
    if (node.t === "bool") {
      return node.op === "&&"
        ? node.parts.every((p) => this.truth(p))
        : node.parts.some((p) => this.truth(p));
    }
    if (node.t === "cmp") return this.compare(node);
    if (node.t === "lit" || node.t === "attr") {
      const v = this.value(node);
      if (v === MISSING) return false;
      return Boolean(v);
    }
    throw new Error("Cannot evaluate node");
  }

  private value(node: Node): any {
    if (node.t === "lit") return node.value;
    if (node.t === "attr") return this.resolve(node.path);
    throw new Error("Not a value node");
  }

  private resolve(path: string): any {
    const key = path.startsWith("context.") ? path.slice("context.".length) : path;
    return key in this.context ? this.context[key] : MISSING;
  }

  private indeterminate(): boolean {
    if (!this.failClosed) return false;
    return this.effect === "forbid";
  }

  private compare(node: { op: string; left: Node; right: Node }): boolean {
    const left = this.value(node.left);
    const right = this.value(node.right);
    const op = node.op;

    if (op === "in") {
      if (left === MISSING || right === MISSING) return false;
      if (Array.isArray(right)) return right.includes(left);
      return String(right).includes(String(left));
    }

    if (left === MISSING || right === MISSING) return false;

    const ln = coerceNumber(left);
    const rn = coerceNumber(right);

    if (op === ">" || op === ">=" || op === "<" || op === "<=") {
      if (ln === null || rn === null) return this.indeterminate();
      if (op === ">") return ln > rn;
      if (op === ">=") return ln >= rn;
      if (op === "<") return ln < rn;
      return ln <= rn;
    }

    if (op === "==" || op === "!=") {
      const eq = ln !== null && rn !== null ? ln === rn : String(left) === String(right);
      return op === "==" ? eq : !eq;
    }

    throw new Error(`Unsupported operator: ${op}`);
  }
}

export class CedarEvaluator {
  static evaluate(
    policies: string[],
    toolName: string,
    args: Record<string, any>,
    opts: { defaultEffect?: "allow" | "deny"; failClosed?: boolean } = {}
  ): Decision {
    const defaultEffect = opts.defaultEffect ?? "allow";
    const failClosed = opts.failClosed ?? true;
    const context: Record<string, any> = { tool_name: toolName, ...args };

    let permitted = false;
    for (const doc of policies || []) {
      for (const stmt of splitStatements(doc)) {
        let policy: Policy;
        try {
          policy = parseStatement(stmt);
        } catch (e) {
          // Skip invalid statements rather than crash enforcement.
          // eslint-disable-next-line no-console
          console.warn(`[AgentShield] Skipping invalid policy: ${(e as Error).message}`);
          continue;
        }
        const ev = new Evaluator(context, policy.effect, failClosed);
        if (policy.when && !ev.truth(policy.when)) continue;
        if (policy.unless && ev.truth(policy.unless)) continue;
        if (policy.effect === "forbid") {
          return { allowed: false, reason: `Blocked by policy: ${policy.source}` };
        }
        permitted = true;
      }
    }

    if (permitted) return { allowed: true };
    if (defaultEffect === "deny") {
      return { allowed: false, reason: "Denied by default policy posture (no matching permit)." };
    }
    return { allowed: true };
  }
}

export class PolicyEngine {
  private circuitBreaker: CircuitBreaker;
  public policies: string[] = [];
  private defaultEffect: "allow" | "deny";
  private failClosed: boolean;

  constructor(opts: { defaultEffect?: "allow" | "deny"; failClosed?: boolean } = {}) {
    this.circuitBreaker = new CircuitBreaker();
    this.defaultEffect = opts.defaultEffect ?? "allow";
    this.failClosed = opts.failClosed ?? true;
  }

  public updatePolicies(policies: string[]) {
    this.policies = policies;
  }

  public evaluate(toolName: string, args: Record<string, any>): Decision {
    if (!this.circuitBreaker.check(toolName)) {
      return { allowed: false, reason: `Circuit breaker tripped for tool: ${toolName}` };
    }
    return CedarEvaluator.evaluate(this.policies, toolName, args, {
      defaultEffect: this.defaultEffect,
      failClosed: this.failClosed,
    });
  }
}
