import { sourceKey } from "./research";
import type { Agent } from "./agents";
export type EvidencePhase =
  "read" | "index" | "write" | "verify" | "repair" | "other";
export type EvidenceSourceInput = { id: string; url?: string; title?: string };
export type EvidenceInput = {
  phase: EvidencePhase;
  sources: EvidenceSourceInput[];
  onEvent?: (kind: "submitted" | "response-cache") => void;
};
export type EvidenceSourceStat = EvidenceSourceInput & {
  mode: "direct" | "auto" | "always" | "never";
};
export type EvidenceStatsEvent = {
  at: string;
  label: string;
  phase: EvidencePhase;
  kind: "submitted" | "response-cache" | "analysis-cache";
  sources: EvidenceSourceStat[];
  agent?: Agent;
  promptCharacters?: number;
  promptBytes?: number;
  elapsedMs?: number;
  inputTokens?: number;
  outputTokens?: number;
  chunks?: number;
};
export type EvidenceStats = {
  id: string;
  familyId: string;
  name: string;
  startedAt: string;
  finishedAt?: string;
  outcome?: "complete" | "failed" | "cancelled";
  events: EvidenceStatsEvent[];
};
/** Inspect the same structured value that is serialized into the outgoing prompt. */
export function evidenceInput(
  phase: EvidencePhase,
  payload: unknown,
): EvidenceInput {
  const sources = new Map<string, EvidenceSourceInput>();
  const remember = (id: string, source: EvidenceSourceInput) => {
    const previous = sources.get(id);
    sources.set(id, {
      id,
      url: source.url || previous?.url,
      title: source.title || previous?.title,
    });
  };
  const visit = (value: any) => {
    if (!value || typeof value !== "object") return;
    if (Array.isArray(value)) {
      value.forEach(visit);
      return;
    }
    if (
      value.kind === "page" &&
      typeof value.id === "string" &&
      value.value?.url
    )
      remember(value.id, {
        id: value.id,
        url: value.value.url,
        title: value.label,
      });
    else if (
      typeof value.sourceId === "string" &&
      (value.chunks ||
        value.facts ||
        value.quote ||
        value.fact ||
        typeof value.text === "string")
    )
      remember(value.sourceId, {
        id: value.sourceId,
        url: value.url,
        title: value.title,
      });
    else if (
      typeof value.id === "string" &&
      value.url &&
      typeof value.text === "string"
    )
      remember(value.id, {
        id: value.id,
        url: value.url,
        title: value.title,
      });
    Object.values(value).forEach(visit);
  };
  visit(payload);
  return { phase, sources: [...sources.values()] };
}
export function evidenceTotals(stats: EvidenceStats) {
  const submitted = stats.events.filter((e) => e.kind === "submitted");
  const unique = (events: EvidenceStatsEvent[]) =>
    new Set(
      events.flatMap((e) =>
        e.sources.map((s) => (s.url ? sourceKey(s.url) : s.id)),
      ),
    ).size;
  return {
    sources: unique(submitted),
    sends: submitted.reduce((n, e) => n + e.sources.length, 0),
    calls: submitted.length,
    readSends: submitted
      .filter((e) => e.phase === "read" || e.phase === "index")
      .reduce((n, e) => n + e.sources.length, 0),
    writeSends: submitted
      .filter((e) => e.phase === "write")
      .reduce((n, e) => n + e.sources.length, 0),
    cachedSources: unique(
      stats.events.filter((e) => e.kind === "analysis-cache"),
    ),
    cachedChunks: stats.events
      .filter((e) => e.kind === "analysis-cache")
      .reduce((n, e) => n + (e.chunks || 1), 0),
    cachedResponses: stats.events.filter((e) => e.kind === "response-cache")
      .length,
  };
}
