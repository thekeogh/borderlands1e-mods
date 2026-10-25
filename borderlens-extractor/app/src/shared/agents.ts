export type Agent = "grok" | "codex";
export type Effort = "low" | "medium";
export const GROK_MODEL = "grok-4.6";
export const AGENT_TIMEOUT_MS = 5 * 60 * 1000;
export const effortForTask = (label: string): Effort =>
  /^(Build |Rewrite prose )/.test(label) ? "low" : "medium";
export type AgentRun = {
  agent: Agent;
  model: string;
  effort: Effort;
  cacheId: string;
  cached: boolean;
  fallbackFrom?: Agent;
};

export const agentNames: Record<Agent, string> = {
  grok: "Grok 4.6",
  codex: "Codex",
};
