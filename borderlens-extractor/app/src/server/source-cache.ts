import { interpretationContent } from "./deterministic-source.ts";
import { SHARED_READING_POLICY } from "./shared-source-index.ts";
import {
  SourceReading,
  sourceChunks,
  type SourceLedger,
} from "./source-analysis.ts";
import { buildPacket, packetHash } from "./evidence.ts";
import type { Store } from "./store.ts";
import { stable } from "./store.ts";
import type { Family } from "../shared/models.ts";
export function savedSourceCache(
  store: Store,
  f: Family,
): { available: boolean; reason: string; ledger?: SourceLedger[] } {
  const pages = store.sources(f.id),
    ledger = store.get<SourceLedger[]>(f.id, "sourceLedger");
  if (!pages.length)
    return {
      available: false,
      reason: "Save at least one source page first.",
    };
  const needsReading = {
    available: true,
    reason:
      "Use saved pages without fetching; missing or changed source facts will be read before writing.",
  };
  if (
    !ledger ||
    ledger.length !== pages.length ||
    store.get(f.id, "sourceLedgerPolicy") !== SHARED_READING_POLICY ||
    stable(store.get(f.id, "sourceLedgerInclusion") || []) !==
      stable(store.sourceInclusionSnapshot(f.id))
  )
    return needsReading;
  const expected = packetHash(buildPacket(store, f));
  const snapshot = store.get<string>(f.id, "sourceLedgerInput");
  if ((snapshot || f.inputHash) !== expected) return needsReading;
  try {
    for (const page of pages) {
      const entry = ledger.find(
        (row) => row.sourceId === page.id && row.hash === page.hash,
      );
      const interpreted = interpretationContent(store, f, page);
      const content = interpreted.content;
      const chunks = content ? sourceChunks(content) : [];
      const parsedChunk = entry?.chunks.find((chunk) => chunk.index === -1);
      if (
        entry?.interpretationHash &&
        (entry.interpretationHash !== interpreted.hash ||
          entry.parserPolicy !== interpreted.policy)
      )
        throw Error();
      if (
        stable(parsedChunk?.reading.facts || []) !== stable(interpreted.facts)
      )
        throw Error();
      const remaining = entry?.chunks.filter((chunk) => chunk.index >= 0) || [];
      if (
        !entry ||
        entry.characters !== content.length ||
        remaining.length !== chunks.length
      )
        throw Error();
      for (const [index, text] of chunks.entries()) {
        const chunk = remaining[index],
          reading = SourceReading.parse(chunk.reading);
        if (
          chunk.index !== index ||
          chunk.characters !== text.length ||
          chunk.facts.length !== reading.facts.length
        )
          throw Error();
        for (const [at, fact] of chunk.facts.entries()) {
          const { id, excludedReason, relevance, ...raw } = fact;
          if (
            id !== `${page.id}:${index}:${at}` ||
            stable(raw) !== stable(reading.facts[at])
          )
            throw Error();
        }
      }
    }
  } catch {
    return needsReading;
  }
  return {
    available: true,
    reason:
      "Reuse saved pages and extracted facts; skip fetching and source reading.",
    ledger,
  };
}
