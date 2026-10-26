import { agentOutputSchema } from "../shared/agent-schema.ts";
import path from "node:path";
import { mkdirSync, existsSync, readFileSync } from "node:fs";
import type { z } from "zod";
import {
  AGENT_TIMEOUT_MS,
  agentNames,
  type Agent,
  type AgentRun,
} from "../shared/agents.ts";
import type { Store } from "./store.ts";
import { atomic } from "./store.ts";
import { CodexRunner } from "./codex.ts";
import { GrokRunner } from "./grok.ts";
import type { AI } from "./worker.ts";
type Failure = { message: string; at: string; until: number };
export class AgentRouter implements AI {
  lastRun?: AgentRun;
  private itemContext: string | null = null;
  setItemContext(id: string | null) {
    this.itemContext = id;
  }
  private failures: Partial<Record<Agent, Failure>> = {};
  private file: string;
  readonly runners: Partial<Record<Agent, AI>>;
  constructor(
    public store: Store,
    runners?: Partial<Record<Agent, AI>>,
    public cooldownMs = 10 * 60 * 1000,
  ) {
    const dir = path.join(store.dir, "ai");
    mkdirSync(dir, { recursive: true });
    this.file = path.join(dir, "agent-failures.json");
    if (existsSync(this.file))
      try {
        const saved = JSON.parse(readFileSync(this.file, "utf8"));
        this.failures = {
          ...(saved.grok ? { grok: saved.grok } : {}),
          ...(saved.codex ? { codex: saved.codex } : {}),
        };
      } catch {}
    // A fixed caller-side nullable-root bug is not a provider outage/capacity limit.
    let repaired = false;
    for (const agent of ["grok", "codex"] as const)
      if (
        /Invalid schema[\s\S]*codex_output_schema[\s\S]*schema must be a JSON Schema[\s\S]*None/.test(
          this.failures[agent]?.message || "",
        )
      ) {
        delete this.failures[agent];
        repaired = true;
      }
    if (repaired) atomic(this.file, JSON.stringify(this.failures));
    this.runners = runners || {
      grok: new GrokRunner(path.join(dir, "grok"), undefined, {
        timeoutMs: AGENT_TIMEOUT_MS,
      }),
      codex: new CodexRunner(path.join(dir, "codex"), undefined, {
        timeoutMs: AGENT_TIMEOUT_MS,
      }),
    };
  }
  resetFailures() {
    this.failures = {};
    atomic(this.file, JSON.stringify(this.failures));
  }
  async status(agent?: Agent): Promise<any> {
    if (agent) return this.runners[agent]?.status();
    const entries = await Promise.all(
      (["grok", "codex"] as Agent[]).map(async (name) => {
        const status = (await this.runners[name]?.status()) || {
          available: false,
          ready: false,
          message: "Agent not configured.",
        };
        return [
          name,
          {
            ...status,
            lastError: this.failures[name]?.message || null,
            cooldownUntil: this.failures[name]
              ? new Date(this.failures[name]!.until).toISOString()
              : null,
          },
        ];
      }),
    );
    return {
      selected: this.store.state.settings.agent,
      providers: Object.fromEntries(entries),
      timeoutSeconds: AGENT_TIMEOUT_MS / 1000,
      message: "Subscription CLIs; automatic fallback enabled.",
    };
  }
  async run<T>(
    label: string,
    prompt: string,
    schema: z.ZodType<T>,
    model: string,
    search: boolean,
    onProgress: (message: string) => void,
  ): Promise<T> {
    agentOutputSchema(schema);
    const selected = this.store.state.settings.agent;
    const other: Agent = selected === "grok" ? "codex" : "grok";
    const order: Agent[] = [selected, other].filter((agent) =>
      Boolean(this.runners[agent]),
    );
    const family = this.store.state.families.find(
      (f) => f.id === (this.itemContext || this.store.state.run.currentId),
    );
    const notifySwitch = (message: string) => {
      if (family) {
        family.history.push({
          at: new Date().toISOString(),
          stage: family.stage,
          message: `${label}: ${message}`,
        });
        family.history = family.history.slice(-100);
        this.store.save();
      }
      onProgress(message);
    };
    const errors: string[] = [];
    for (const agent of order) {
      const prior = this.failures[agent];
      if (prior && prior.until > Date.now()) {
        errors.push(`${agent}: ${prior.message}`);
        notifySwitch(
          `${agentNames[agent]} temporarily unavailable until ${new Date(prior.until).toISOString()}: ${prior.message.slice(0, 500)}; trying the other agent.`,
        );
        continue;
      }
      try {
        onProgress(`${agentNames[agent]} — starting ${label.toLowerCase()}…`);
        const output = await this.runners[agent]!.run(
          label,
          prompt,
          schema,
          model,
          search,
          onProgress,
        );
        delete this.failures[agent];
        atomic(this.file, JSON.stringify(this.failures));
        this.lastRun = this.runners[agent]!.lastRun
          ? {
              ...this.runners[agent]!.lastRun!,
              ...(agent !== selected ? { fallbackFrom: selected } : {}),
            }
          : undefined;
        return output;
      } catch (error: any) {
        const message = String(error.message || error).slice(0, 1500);
        this.failures[agent] = {
          message,
          at: new Date().toISOString(),
          until: Date.now() + this.cooldownMs,
        };
        atomic(this.file, JSON.stringify(this.failures));
        errors.push(`${agent}: ${message}`);
        notifySwitch(
          `${agentNames[agent]} failed: ${message.slice(0, 1000)}${agent === selected ? `; switching to ${agentNames[other]}…` : ""}`,
        );
      }
    }
    throw new Error(
      "No agent completed this step. Saved progress is retained. " +
        errors.join(" | "),
    );
  }
}
