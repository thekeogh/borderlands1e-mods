import type {
  BlockedEvidenceMatch,
  EvidenceRequestNotice,
} from "../shared/evidence-notice.ts";
import type { EvidenceRequest } from "../shared/evidence-requests.ts";
import type { Family, Packet, Source } from "../shared/models.ts";
import { sourceKey } from "../shared/research.ts";
import { COMPILER_VERSION } from "../shared/versions.ts";
import { sourceExclusionReason } from "../shared/catalogue-policy.ts";
import { cachedSharedFacts, normalizedTarget } from "./shared-source-index.ts";
import {
  SourceReading,
  commonFields,
  sourceQuoteMatches,
  type SourceLedger,
} from "./source-analysis.ts";
import { Store, hash, stable } from "./store.ts";
export const MAX_FOLLOWUP_MATCHES = 4;
export const MAX_FOLLOWUP_QUOTE = 1200;
type Fact = SourceReading["facts"][number];
export type EvidenceMatch = {
  request: number;
  topic: string;
  sourceId: string;
  url: string;
  title: string;
  hash: string;
  origin: "index" | "passage";
  fact: Fact;
};
export type EvidenceFollowup = {
  inputKey: string;
  roundUsed: boolean;
  status:
    | "not_requested"
    | "no_match"
    | "supplied"
    | "search_failed"
    | "writer_failed";
  requests: EvidenceRequest[];
  matches: EvidenceMatch[];
  missing: string[];
  error?: string;
  ignoredRequests?: number;
  blocked?: BlockedEvidenceMatch[];
};
const otherGame =
  /borderlands\s*[_ -]*[234](?!\d)|\bbl[234]\b|[-_]bl[234]|pre[ -]?sequel|wonderlands/i;
const content = (source: Source) =>
  source.text +
  "\n\nSTORED SECTIONS AND TABLES\n" +
  JSON.stringify({
    sections: source.sections || [],
    tables: source.tables || [],
  });
/** Library lookup is read-only and never resurrects an item or ancestor exclusion. */
export function evidenceAllowed(store: Store, f: Family, url: string) {
  if (
    store.sourceInclusionMode(f.id, url) === "never" ||
    store.isSourceExcluded(f.id, url)
  )
    return false;
  const owners = store.sharedScopesFor(f),
    key = sourceKey(url);
  const permittedBinding = owners.some(
    (owner) =>
      !store.isSourceExcluded(owner.id, url) &&
      owner.sourceUrls.some((candidate) => sourceKey(candidate) === key),
  );
  return (
    permittedBinding ||
    !owners.some((owner) => store.isSourceExcluded(owner.id, url))
  );
}
export function evidenceLibrary(store: Store, f: Family) {
  return store.storedArticles().filter((source) => {
    if (
      (source.manualText || source.selectedContent) &&
      source.familyId !== f.id &&
      !store
        .sharedScopesFor(f)
        .some(
          (owner) =>
            owner.id === source.familyId &&
            !store.isSourceExcluded(owner.id, source.url) &&
            owner.sourceUrls.some(
              (url) => sourceKey(url) === sourceKey(source.url),
            ),
        )
    )
      return false;
    if (!evidenceAllowed(store, f, source.url)) return false;
    let name = source.title + " " + source.url;
    try {
      name = decodeURIComponent(name);
    } catch {}
    return !otherGame.test(name);
  });
}
export function followupInputKey(
  store: Store,
  f: Family,
  packet: Packet,
  ledger: SourceLedger[],
) {
  return hash(
    stable({
      version: COMPILER_VERSION,
      packet,
      ledger,
      inclusion: store.sourceInclusionSnapshot(f.id),
      model: store.state.settings.model,
      agent: store.state.settings.agent,
      style: store.state.settings.writingStyle,
      library: evidenceLibrary(store, f)
        .map((source) => [sourceKey(source.url), source.id, source.hash])
        .sort(),
    }),
  );
}
const commonTerms = new Set([
  "item",
  "weapon",
  "weapons",
  "mod",
  "mods",
  "skill",
  "skills",
  "damage",
  "stats",
  "details",
  "bonus",
  "effect",
  "effects",
  "level",
  "borderlands",
  "enhanced",
]);
function requestTerms(request: EvidenceRequest) {
  const terms = [...new Set(request.terms.map((term) => term.trim()))];
  return terms.some((term) => !commonTerms.has(normalizedTarget(term)))
    ? terms
    : [];
}

function matchingCount(text: string, terms: string[]) {
  const key = normalizedTarget(text);
  return terms.filter((term) => key.includes(normalizedTarget(term))).length;
}
function rawPassages(source: Source, terms: string[]) {
  // Mixed-game pages use the stored heading boundaries. Unlabelled ambiguity is not guessed.
  const mixed = (source.sections || []).some((section) =>
    otherGame.test(section.heading),
  );
  let blocked = false;
  const texts = mixed
    ? (source.sections || []).flatMap((section) => {
        if (otherGame.test(section.heading)) blocked = true;
        else if (/^borderlands(?:\s*1)?$/i.test(section.heading.trim()))
          blocked = false;
        return blocked ? [] : [section.text];
      })
    : [source.text];
  const passages = new Set<string>();
  for (const text of texts) {
    const lower = text.toLowerCase();
    for (const term of terms) {
      const words = term.toLowerCase().match(/[a-z0-9]+/g) || [];
      const needle =
        words.find((word) => word.length > 3 && !commonTerms.has(word)) ||
        words[0];
      if (!needle) continue;
      const positions: number[] = [];
      let at = lower.indexOf(needle);
      while (at >= 0 && positions.length < 20) {
        positions.push(at);
        at = lower.indexOf(needle, at + needle.length);
      }
      const last = lower.lastIndexOf(needle);
      if (last >= 0) positions.push(last);
      for (const position of positions) {
        const start = Math.max(0, position - 250),
          quote = text.slice(start, start + MAX_FOLLOWUP_QUOTE).trim();
        if (
          sourceQuoteMatches(content(source), quote) &&
          !sourceExclusionReason(quote)
        )
          passages.add(quote);
      }
    }
  }
  return [...passages];
}
/** Local ranking only: no scraping, external requests, AI calls or automatic source attachment. */
export function searchSavedEvidence(
  store: Store,
  f: Family,
  requests: EvidenceRequest[],
  ledger: SourceLedger[],
  inputKey: string,
): EvidenceFollowup {
  const report: EvidenceFollowup = {
    inputKey,
    roundUsed: true,
    status: "no_match",
    requests: requests.slice(0, 3),
    matches: [],
    missing: [],
    blocked: [],
  };
  const library = evidenceLibrary(store, f);
  const selected = new Set(
    ledger.flatMap((page) =>
      page.chunks.flatMap((chunk) =>
        chunk.facts.map(
          (fact) => sourceKey(page.url) + ":" + normalizedTarget(fact.quote),
        ),
      ),
    ),
  );
  for (const [requestIndex, request] of report.requests.entries()) {
    const terms = requestTerms(request);
    if (!terms.length) {
      report.missing.push(request.topic);
      continue;
    }
    // Only an explicit AI request triggers local matching against blocked pages.
    // No excluded text, index facts or metadata are returned to any agent.
    for (const source of store.storedArticles()) {
      if (store.sourceInclusionMode(f.id, source.url) !== "never") continue;
      let label = source.title + " " + source.url;
      try {
        label = decodeURIComponent(label);
      } catch {}
      if (otherGame.test(label)) continue;
      if (
        matchingCount(label, terms) < Math.min(2, terms.length) &&
        !rawPassages(source, terms).some(
          (quote) =>
            matchingCount(label + " " + quote, terms) >=
            Math.min(2, terms.length),
        )
      )
        continue;
      report.blocked!.push({
        topic: request.topic,
        reason: request.reason,
        url: source.url,
        title: source.title,
      });
    }
    const candidates: { score: number; match: EvidenceMatch }[] = [];
    for (const source of library) {
      const indexed = cachedSharedFacts(store, source);
      const facts: { fact: Fact; origin: "index" | "passage" }[] = indexed.map(
        ({ scope, ...fact }) => {
          const names = [f.name, ...(f.aliases || [])].map(normalizedTarget);
          const contextual =
            !!scope &&
            (scope.skills.length > 0 ||
              (scope.items.length > 0 &&
                !scope.items.some((name) =>
                  names.includes(normalizedTarget(name)),
                )) ||
              (scope.categories.length > 0 &&
                !scope.categories.includes(f.category)));
          return {
            fact:
              contextual && fact.field === "stats"
                ? { ...fact, field: "details" as const }
                : fact,
            origin: "index" as const,
          };
        },
      );
      for (const quote of rawPassages(source, terms))
        facts.push({
          fact: {
            field: "details",
            detail:
              "Additional original saved passage; assess its scope before using it for this item.",
            quote,
            stat: null,
          },
          origin: "passage",
        });
      for (const candidate of facts) {
        const fact = SourceReading.shape.facts.element.safeParse(
          candidate.fact,
        );
        if (
          !fact.success ||
          fact.data.quote.length > MAX_FOLLOWUP_QUOTE ||
          fact.data.detail.length > 1000 ||
          sourceExclusionReason(fact.data.detail + " " + fact.data.quote)
        )
          continue;
        if (!sourceQuoteMatches(content(source), fact.data.quote)) continue;
        const key =
          sourceKey(source.url) + ":" + normalizedTarget(fact.data.quote);
        if (selected.has(key)) continue;
        const titleMatches = matchingCount(
          source.title + " " + source.url,
          terms,
        );
        const count = matchingCount(
          source.title +
            " " +
            fact.data.quote +
            (candidate.origin === "index" ? " " + fact.data.detail : ""),
          terms,
        );
        if (count < Math.min(2, terms.length)) continue;
        candidates.push({
          score:
            count * 10 +
            titleMatches * 4 +
            (candidate.origin === "index" ? 5 : 0),
          match: {
            request: requestIndex,
            topic: request.topic,
            sourceId: source.id,
            url: source.url,
            title: source.title,
            hash: source.hash,
            origin: candidate.origin,
            fact: fact.data,
          },
        });
      }
    }
    candidates.sort(
      (a, b) => b.score - a.score || a.match.url.localeCompare(b.match.url),
    );
    let found = 0;
    const perRequestPages = new Set<string>();
    for (const candidate of candidates) {
      if (found >= 2 || report.matches.length >= MAX_FOLLOWUP_MATCHES) break;
      const key =
        sourceKey(candidate.match.url) +
        ":" +
        normalizedTarget(candidate.match.fact.quote);
      if (perRequestPages.has(sourceKey(candidate.match.url))) continue;
      if (
        report.matches.some(
          (match) =>
            sourceKey(match.url) + ":" + normalizedTarget(match.fact.quote) ===
            key,
        )
      ) {
        found++;
        continue;
      }
      report.matches.push(candidate.match);
      perRequestPages.add(sourceKey(candidate.match.url));
      found++;
    }
    if (!found) report.missing.push(request.topic);
  }
  if (report.matches.length) report.status = "supplied";
  return report;
}
/** Durable, private notification; dismissing never changes inclusion or queues. */
export function recordBlockedEvidenceNotice(
  store: Store,
  f: Family,
  report: EvidenceFollowup,
) {
  if (!report.blocked?.length) return;
  const id = hash(
    stable({ inputKey: report.inputKey, blocked: report.blocked }),
  );
  const previous = store.get<EvidenceRequestNotice>(
    f.id,
    "evidenceRequestNotice",
  );
  if (previous?.id === id) return; // A retry must not resurrect a dismissed notice.
  store.put(f.id, "evidenceRequestNotice", {
    id,
    requestedAt: new Date().toISOString(),
    blocked: report.blocked,
  } satisfies EvidenceRequestNotice);
}
/** Supplement only this draft's packet/ledger; canonical source bindings and saved full readings stay untouched. */
export function applySavedEvidence(
  store: Store,
  f: Family,
  packet: Packet,
  ledger: SourceLedger[],
  report: EvidenceFollowup,
) {
  const p = structuredClone(packet),
    merged = structuredClone(ledger);
  for (const [at, match] of report.matches.entries()) {
    if (!evidenceAllowed(store, f, match.url))
      throw new Error(
        "Requested saved evidence is now excluded. Rebuild this item.",
      );
    const source = store.cachedSource(match.url);
    if (
      !source ||
      source.hash !== match.hash ||
      source.id !== match.sourceId ||
      !sourceQuoteMatches(content(source), match.fact.quote)
    )
      throw new Error("Requested saved evidence changed. Rebuild this item.");
    if (!p.evidence.some((evidence) => evidence.id === source.id))
      p.evidence.push({
        id: source.id,
        kind: "page",
        label: source.title,
        value: {
          url: source.url,
          hash: source.hash,
          retrievedAt: source.fetchedAt,
          text: source.text,
          sections: source.sections || [],
          tables: source.tables || [],
        },
      });
    let page = merged.find((page) => page.sourceId === source.id);
    if (!page) {
      page = {
        sourceId: source.id,
        url: source.url,
        hash: source.hash,
        characters: 0,
        chunks: [],
      };
      merged.push(page);
    }
    const fact = structuredClone(match.fact);
    page.chunks.push({
      index: page.chunks.length,
      characters: fact.quote.length,
      reading: {
        facts: [fact],
        fields: commonFields.map((name) => ({
          name,
          status: name === fact.field ? "found" : "not_found",
          reason:
            "Additional saved context, retrieved on request; excerpt only.",
        })),
        proposedFields: [],
      },
      facts: [
        {
          ...fact,
          id: `${source.id}:followup:${at}`,
          retrieval: { topic: match.topic },
        },
      ],
    });
    page.characters += fact.quote.length;
  }
  return { packet: p, ledger: merged };
}
export function validateSavedEvidence(store: Store, f: Family) {
  const report = store.get<EvidenceFollowup>(f.id, "evidenceFollowup");
  if (report?.status === "supplied")
    applySavedEvidence(
      store,
      f,
      { evidence: [] } as unknown as Packet,
      [],
      report,
    );
}
