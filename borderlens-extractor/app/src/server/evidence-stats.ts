import { randomUUID } from "node:crypto";
import type { Family } from "../shared/models.ts";
import type {
  EvidenceInput,
  EvidenceStats,
  EvidenceStatsEvent,
} from "../shared/evidence-stats.ts";
import { sourceKey } from "../shared/research.ts";
import type { Store } from "./store.ts";
export function beginEvidenceStats(store: Store, f: Family) {
  const current = store.state.evidenceStats;
  if (current?.familyId === f.id && !current.finishedAt) return current;
  const stats: EvidenceStats = {
    id: randomUUID(),
    familyId: f.id,
    name: f.name,
    startedAt: new Date().toISOString(),
    events: [],
  };
  store.state.evidenceStats = stats;
  store.save();
  return stats;
}
export function recordEvidenceEvent(
  store: Store,
  f: Family,
  input: EvidenceInput,
  event: Omit<EvidenceStatsEvent, "sources" | "phase" | "at">,
) {
  const stats = beginEvidenceStats(store, f);
  const shared = new Set(
    store.sharedScopesFor(f).flatMap((o) => o.sourceUrls.map(sourceKey)),
  );
  const sources = new Map<string, EvidenceStatsEvent["sources"][number]>();
  for (const ref of input.sources) {
    const page = store.source(ref.id);
    const url = ref.url || page?.url;
    const mode = url ? store.sourceInclusionMode(f.id, url) : "auto";
    sources.set(url ? sourceKey(url) : ref.id, {
      ...ref,
      url,
      title: ref.title || page?.title || url || ref.id,
      mode:
        mode === "never"
          ? "never"
          : mode === "always"
            ? "always"
            : url && shared.has(sourceKey(url))
              ? "auto"
              : "direct",
    });
  }
  stats.events.push({
    ...event,
    at: new Date().toISOString(),
    phase: input.phase,
    sources: [...sources.values()],
  });
  store.save();
}
export function finishEvidenceStats(
  store: Store,
  f: Family,
  outcome: "complete" | "failed" | "cancelled",
) {
  const stats = store.state.evidenceStats;
  if (!stats || stats.familyId !== f.id || stats.finishedAt) return;
  stats.finishedAt = new Date().toISOString();
  stats.name = f.name;
  stats.outcome = outcome;
  const history =
    store.get<EvidenceStats[]>(f.id, "evidenceStatsHistory") || [];
  history.push(structuredClone(stats));
  store.put(f.id, "evidenceStatsHistory", history);
  store.save();
}
export function analysisCacheHit(
  store: Store,
  f: Family,
  source: { id: string; url: string; title?: string },
  chunks = 1,
) {
  recordEvidenceEvent(
    store,
    f,
    { phase: "read", sources: [source] },
    { kind: "analysis-cache", label: "Saved source analysis", chunks },
  );
}
