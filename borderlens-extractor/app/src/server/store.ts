import { storedTextBytes } from "../shared/source-size.ts";
import { isManualTextUrl } from "../shared/manual-evidence.ts";
import { Names } from "./names.ts";
import type {
  InheritedEvidence,
  SourceInclusionMode,
} from "../shared/research.ts";
import {
  EvidenceScope,
  scopeLabel,
  scopeMatches,
} from "../shared/evidence-scopes.ts";
import { sourceKey, type ExcludedSource } from "../shared/research.ts";
import { reconcileCharacterFamilies } from "./importer.ts";
import { Images, defaultImageRoot } from "./images.ts";
import { parseSource } from "./source-content.ts";
import {
  CATALOGUE_SCHEMA_VERSION,
  COMPILER_VERSION,
} from "../shared/versions.ts";
import { Classifications } from "./classifications.ts";
import { catalogueOrder } from "../shared/taxonomy.ts";
import { DatabaseSync } from "node:sqlite";
import {
  mkdirSync,
  writeFileSync,
  renameSync,
  readFileSync,
  existsSync,
} from "node:fs";
import path from "node:path";
import { EventEmitter } from "node:events";
import { createHash } from "node:crypto";
import {
  initial,
  PublicEntry,
  now,
  type Project,
  type Family,
  type Raw,
  type Source,
} from "../shared/models.ts";
export const hash = (v: string | Buffer) =>
  createHash("sha256").update(v).digest("hex");
export const stable = (v: unknown): string =>
  JSON.stringify(v, (_k, x) =>
    x && typeof x === "object" && !Array.isArray(x)
      ? Object.fromEntries(
          Object.entries(x).sort(([a], [b]) => a.localeCompare(b)),
        )
      : x,
  );
export class Store extends EventEmitter {
  private articleIndex?: { changes: string; pages: Map<string, Source> };
  classifications: Classifications;
  names: Names;
  images: Images;
  db: DatabaseSync;
  state: Project;
  records: Map<string, Raw> = new Map();
  constructor(
    public dir: string,
    imageRoot = defaultImageRoot,
  ) {
    super();
    mkdirSync(dir, { recursive: true });
    for (const d of ["captures", "sources", "ai", "exports"])
      mkdirSync(path.join(dir, d), { recursive: true });
    this.images = new Images(
      existsSync(path.join(dir, "image-library"))
        ? path.join(dir, "image-library")
        : imageRoot,
      path.join(dir, "image-overrides.json"),
      imageRoot,
    );
    this.classifications = new Classifications(
      path.join(dir, "classification-overrides.json"),
    );
    this.names = new Names(path.join(dir, "name-overrides.json"));
    this.db = new DatabaseSync(path.join(dir, "workshop.sqlite"));
    this.db.exec(
      "PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL); CREATE TABLE IF NOT EXISTS raw(capture TEXT,id TEXT,path TEXT,class TEXT,value TEXT,PRIMARY KEY(capture,id)); CREATE TABLE IF NOT EXISTS artifacts(family TEXT,kind TEXT,value TEXT,PRIMARY KEY(family,kind)); CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,family TEXT,value TEXT);",
    );
    const r = this.db
      .prepare("SELECT value FROM meta WHERE key=?")
      .get("project") as { value: string } | undefined;
    this.state = r ? JSON.parse(r.value) : initial();
    if (!["saved", "fresh", "auto"].includes(this.state.run.sourceMode))
      this.state.run.sourceMode = "auto";
    if (this.state.run.continueOnError === undefined)
      this.state.run.continueOnError = this.state.run.queue.length > 1;
    this.state.sharedScopes ||= [];
    if (!Array.isArray(this.state.run.sourcePrepared))
      this.state.run.sourcePrepared = [];
    if (!["grok", "codex"].includes(this.state.settings.agent))
      this.state.settings.agent = "grok";
    if (this.state.schemaVersion !== 1)
      throw new Error(
        "Unsupported project database version; keep this folder for migration.",
      );
    for (const f of this.state.families)
      if (f.status === "running") f.status = "queued";
    if (this.state.run.cancelRequested) {
      const old = this.state.run;
      for (const id of new Set([
        ...old.queue,
        ...old.deferred,
        ...(old.pendingFrom ? [old.pendingFrom] : []),
        ...(this.state.buildCheckpoint?.queue || []),
      ]))
        this.forget(id, ["pendingRebuild"]);
      const stats = this.state.evidenceStats;
      if (stats && !stats.finishedAt) {
        stats.finishedAt = new Date().toISOString();
        stats.outcome = "cancelled";
        const history =
          this.get<import("../shared/evidence-stats.ts").EvidenceStats[]>(
            stats.familyId,
            "evidenceStatsHistory",
          ) || [];
        history.push(structuredClone(stats));
        this.put(stats.familyId, "evidenceStatsHistory", history);
      }
      delete this.state.buildCheckpoint;
      this.state.run = {
        ...initial().run,
        sourceMode: old.sourceMode === "fresh" ? "fresh" : "saved",
        message:
          "Run cancelled. Saved work is kept; start a new run when ready.",
      };
    }
    if (["running", "pausing"].includes(this.state.run.status)) {
      this.state.run.status = "paused";
      this.state.run.pauseRequested = false;
      this.state.run.message =
        "Interrupted run recovered. Resume from the saved checkpoint.";
    }
    if (this.state.coverage.status === "running") {
      this.state.coverage.status = "partial";
      this.state.coverage.message =
        "Coverage interrupted; scan again to reuse saved work.";
    }
    this.state.families.sort(catalogueOrder);
    this.reloadRecords();
    reconcileCharacterFamilies(this);
    for (const f of this.state.families) {
      const output = this.get<any>(f.id, "output");
      const provenance = this.get<any>(f.id, "provenance");
      let pending = this.get<any>(f.id, "draft");
      const resumable =
        ["draft", "validate"].includes(f.stage) &&
        PublicEntry.safeParse(pending?.entry).success;
      if (
        !resumable &&
        ((output &&
          (output.schemaVersion !== CATALOGUE_SCHEMA_VERSION ||
            provenance?.compilerVersion !== COMPILER_VERSION)) ||
          (pending?.entry &&
            (pending.entry.schemaVersion !== CATALOGUE_SCHEMA_VERSION ||
              pending.entry.compilerVersion !== COMPILER_VERSION))) &&
        f.status !== "excluded"
      ) {
        if (pending)
          this.put(
            f.id,
            "draft:compiler:" + (pending.entry?.compilerVersion || "unknown"),
            pending,
          );
        f.stage = "evidence";
        f.status = f.manualOutput ? "blocked" : "queued";
        f.issue = f.manualOutput
          ? "Saved manual entry uses an older schema. Its content is retained; update it to the current website schema before saving."
          : null;
        this.forget(f.id, [
          "packet",
          "draft",
          "validationFeedback",
          "modifierRepairs",
          "statRepairs",
          "proseRepairs",
          "buildAttempt",
        ]);
      }
    }
    this.save();
  }
  reloadRecords() {
    this.records.clear();
    for (const c of this.state.captures)
      for (const r of this.db
        .prepare("SELECT value FROM raw WHERE capture=?")
        .all(c.id) as { value: string }[]) {
        const obj = JSON.parse(r.value) as Raw;
        if (obj.record_type === "object")
          this.records.set(obj.path.toLowerCase(), obj);
      }
  }
  applyClassifications() {
    for (const f of this.state.families) {
      const effective = this.classifications.effective(f.id);
      const previous = f.classification?.weaponType;
      const previousCategory = f.category;
      if (effective?.category && effective.category !== f.category) {
        f.rawCategory ||= f.category;
        f.rawSubtype ||= f.subtype;
        f.category = effective.category;
        f.subtype =
          f.category === "Weapons"
            ? f.rawCategory === "Weapons"
              ? f.rawSubtype
              : "Other weapons"
            : f.category;
      } else if (
        !effective?.category &&
        f.rawCategory &&
        f.category !== f.rawCategory
      ) {
        f.category = f.rawCategory;
        f.subtype = f.rawSubtype || f.category;
      }
      if (effective) f.classification = effective;
      else delete f.classification;
      if (previousCategory !== f.category) {
        // Category is compiler metadata. Keep identity, content and evidence;
        // validate the saved draft before promoting a corrected completed item.
        const draft = this.get<any>(f.id, "draft");
        for (const key of ["draft", "manualDraft"]) {
          const saved = key === "draft" ? draft : this.get<any>(f.id, key);
          if (saved?.entry) {
            saved.entry.category = f.category;
            if (f.category !== "Weapons") saved.entry.weaponType = null;
            this.put(f.id, key, saved);
          }
        }
        for (const key of ["packet", "validatedPacket"]) {
          const packet = this.get<any>(f.id, key);
          if (packet) {
            packet.category = f.category;
            packet.subtype = f.subtype;
            this.put(f.id, key, packet);
          }
        }
        if (f.status === "done" && this.get(f.id, "output")) {
          f.status = "queued";
          f.stage = draft?.entry ? "validate" : "draft";
          f.issue = null;
        }
      } else if (
        previous !== effective?.weaponType &&
        f.status === "done" &&
        this.get(f.id, "output")
      ) {
        f.stage = "draft";
        f.status = "queued";
        f.issue = null;
        this.forget(f.id, ["draft"]);
      }
    }
    this.state.families.sort(catalogueOrder);
  }
  applyNames() {
    for (const f of this.state.families) {
      const override = this.names.data.entries[f.id];
      const previous = f.name;
      if (override) {
        f.rawName ||= override.originalName || previous;
        f.name = override.name;
        f.nameOverride = override;
        f.aliases = [
          ...new Set([
            ...f.aliases,
            f.rawName,
            ...(previous !== f.name ? [previous] : []),
          ]),
        ].filter((name) => name !== f.name);
      } else if (f.rawName) {
        f.name = f.rawName;
        delete f.nameOverride;
      }
      if (
        previous !== f.name &&
        f.status === "done" &&
        this.get(f.id, "output")
      ) {
        f.status = "queued";
        f.stage = "draft";
        f.issue = null;
        this.forget(f.id, ["packet", "draft", "workingSourceLedger"]);
      }
    }
  }
  syncClassifications() {
    const classificationsChanged = this.classifications.reload();
    const namesChanged = this.names.reload();
    if (classificationsChanged || namesChanged) this.save();
  }
  save() {
    this.applyNames();
    this.applyClassifications();
    this.state.revision++;
    this.db
      .prepare("INSERT OR REPLACE INTO meta VALUES(?,?)")
      .run("project", JSON.stringify(this.state));
    this.emit("change", this.state.revision);
  }
  activity(message: string, stage = "workshop") {
    this.state.activity.push({ at: now(), stage, message });
    this.state.activity = this.state.activity.slice(-150);
    this.save();
  }
  put(family: string, kind: string, value: unknown) {
    this.db
      .prepare("INSERT OR REPLACE INTO artifacts VALUES(?,?,?)")
      .run(family, kind, JSON.stringify(value));
  }
  get<T = unknown>(family: string, kind: string): T | null {
    const r = this.db
      .prepare("SELECT value FROM artifacts WHERE family=? AND kind=?")
      .get(family, kind) as { value: string } | undefined;
    return r ? JSON.parse(r.value) : null;
  }
  forget(family: string, kinds: string[]) {
    for (const k of kinds)
      this.db
        .prepare("DELETE FROM artifacts WHERE family=? AND kind=?")
        .run(family, k);
  }
  sourceExclusions(family: string): ExcludedSource[] {
    return this.get<ExcludedSource[]>(family, "sourceExclusions") || [];
  }
  isSourceExcluded(family: string, url: string): boolean {
    return this.sourceExclusions(family).some(
      (source) => sourceKey(source.url) === sourceKey(url),
    );
  }
  sharedScopesFor(f: Family): Family[] {
    return (this.state.sharedScopes || []).filter((scope) =>
      scopeMatches(scope.evidenceScope!, f),
    );
  }
  ensureScope(definition: unknown): Family {
    const scope = EvidenceScope.parse(definition),
      id = "shared-" + hash(stable(scope)).slice(0, 20);
    const existing = this.state.sharedScopes?.find((f) => f.id === id);
    if (existing) return existing;
    const owner: Family = {
      id,
      name: scopeLabel(scope),
      category:
        scope.category === "Everything" ? "Other equipment" : scope.category,
      subtype: scope.group || scope.category,
      character: scope.character,
      evidenceScope: scope,
      aliases: [],
      roots: [],
      status: "queued",
      stage: "evidence",
      inputHash: "",
      issue: null,
      notes: "",
      gameOnly: false,
      sourceUrls: [],
      history: [],
      updatedAt: now(),
      manualOutput: false,
      revision: 0,
    };
    (this.state.sharedScopes ||= []).push(owner);
    this.save();
    return owner;
  }
  scopeChildren(owner: Family): Family[] {
    return owner.evidenceScope
      ? this.state.families.filter(
          (f) =>
            !f.supersededBy &&
            f.status !== "excluded" &&
            scopeMatches(owner.evidenceScope!, f),
        )
      : [owner];
  }
  storedArticles(): Source[] {
    const pages = new Map<string, Source>();
    for (const row of this.db
      .prepare("SELECT value FROM sources ORDER BY rowid")
      .all() as { value: string }[]) {
      let source: Source;
      try {
        source = JSON.parse(row.value) as Source;
      } catch {
        continue;
      }
      if (
        !source ||
        ![
          source.id,
          source.url,
          source.title,
          source.hash,
          source.text,
          source.filename,
        ].every((value) => typeof value === "string")
      )
        continue;
      const key =
          sourceKey(source.url) +
          (source.selectedContent ? "|selected:" + source.id : ""),
        previous = pages.get(key);
      if (
        !source.error &&
        source.text &&
        (!previous || (source.fetchedAt || "") >= (previous.fetchedAt || ""))
      )
        pages.set(key, source);
    }
    return [...pages.values()];
  }
  cachedSource(url: string): Source | undefined {
    const changes =
      String(
        (this.db.prepare("SELECT total_changes() AS n").get() as { n: number })
          .n,
      ) +
      ":" +
      String(
        (
          this.db.prepare("PRAGMA data_version").get() as {
            data_version: number;
          }
        ).data_version,
      );
    if (!this.articleIndex || this.articleIndex.changes !== changes) {
      const pages = new Map<string, Source>();
      for (const row of this.db
        .prepare("SELECT value FROM sources ORDER BY rowid")
        .all() as { value: string }[]) {
        const source = JSON.parse(row.value) as Source,
          key = sourceKey(source.url),
          previous = pages.get(key);
        if (
          !source.error &&
          !source.selectedContent &&
          (!previous || (source.fetchedAt || "") >= (previous.fetchedAt || ""))
        )
          pages.set(key, source);
      }
      this.articleIndex = { changes, pages };
    }
    const source = this.articleIndex.pages.get(sourceKey(url));
    return source ? this.hydrateSource(source) : undefined;
  }
  sharedCached(url: string): Source | undefined {
    return this.cachedSource(url);
  }
  private hydrateSource(source: Source): Source {
    const file = path.join(this.dir, "sources", source.filename);
    if (source.contentVersion !== 2 && existsSync(file)) {
      const parsed = parseSource(readFileSync(file, "utf8"));
      source.contentVersion = 2;
      source.sections = parsed.sections;
      source.tables = parsed.tables;
      this.db
        .prepare("UPDATE sources SET value=? WHERE id=?")
        .run(JSON.stringify(source), source.id);
    }
    return source;
  }
  sourceConsumers(url: string): Family[] {
    const key = sourceKey(url),
      physical = new Set(
        (
          this.db.prepare("SELECT family,value FROM sources").all() as {
            family: string;
            value: string;
          }[]
        )
          .filter(
            (row) => sourceKey((JSON.parse(row.value) as Source).url) === key,
          )
          .map((row) => row.family),
      );
    return this.state.families.filter(
      (f) =>
        f.status !== "excluded" &&
        !f.supersededBy &&
        !this.isSourceExcluded(f.id, url) &&
        !this.sourceNeverIncluded(f.id, url) &&
        (f.sourceUrls.some((candidate) => sourceKey(candidate) === key) ||
          physical.has(f.id) ||
          this.sharedScopesFor(f).some(
            (owner) =>
              !this.isSourceExcluded(owner.id, url) &&
              owner.sourceUrls.some(
                (candidate) => sourceKey(candidate) === key,
              ),
          )),
    );
  }
  scopeSources(owner: Family): Source[] {
    const raw = this.rawSources(owner.id).filter((source) =>
        owner.sourceUrls.some(
          (url) => sourceKey(url) === sourceKey(source.url),
        ),
      ),
      cached = owner.sourceUrls
        .filter(
          (url) =>
            !raw.some(
              (source) =>
                source.selectedContent &&
                sourceKey(source.url) === sourceKey(url),
            ),
        )
        .map((url) => this.sharedCached(url))
        .filter(Boolean) as Source[];
    return [
      ...new Map(
        [...cached, ...raw]
          .sort((a, b) => (a.fetchedAt || "").localeCompare(b.fetchedAt || ""))
          .map((source) => [sourceKey(source.url), source]),
      ).values(),
    ];
  }
  alwaysIncludedSources(family: string): string[] {
    return [
      ...new Set(
        (this.get<string[]>(family, "alwaysIncludeSources") || []).map(
          sourceKey,
        ),
      ),
    ].sort();
  }
  neverIncludedSources(family: string): string[] {
    return [
      ...new Set(
        (this.get<string[]>(family, "neverIncludeSources") || []).map(
          sourceKey,
        ),
      ),
    ].sort();
  }
  sourceInclusionMode(family: string, url: string): SourceInclusionMode {
    const key = sourceKey(url);
    if (this.neverIncludedSources(family).includes(key)) return "never";
    return this.alwaysIncludedSources(family).includes(key) ? "always" : "auto";
  }
  sourceInclusionSnapshot(family: string): string[] {
    return [
      ...this.alwaysIncludedSources(family),
      ...this.neverIncludedSources(family).map((key) => "never:" + key),
    ].sort();
  }
  sourceNeverIncluded(family: string, url: string) {
    // A saved Never preference remains authoritative even if its binding moves.
    return this.sourceInclusionMode(family, url) === "never";
  }

  sourceAlwaysIncluded(family: string, url: string) {
    return this.sourceInclusionMode(family, url) === "always";
  }
  inheritedEvidence(f: Family): InheritedEvidence[] {
    if (f.evidenceScope) return [];
    const entries = new Map<string, InheritedEvidence>(),
      pages = new Map(
        this.sources(f.id).map((page) => [sourceKey(page.url), page]),
      );
    for (const owner of this.sharedScopesFor(f))
      for (const url of owner.sourceUrls) {
        if (
          this.isSourceExcluded(owner.id, url) ||
          this.isSourceExcluded(f.id, url)
        )
          continue;
        const key = sourceKey(url),
          page =
            pages.get(key) ||
            (this.sourceNeverIncluded(f.id, url)
              ? this.scopeSources(owner).find(
                  (source) => sourceKey(source.url) === key,
                )
              : undefined);
        let entry = entries.get(key);
        if (!entry) {
          let title = url;
          try {
            title = decodeURIComponent(
              new URL(url).pathname.split("/").pop() || url,
            ).replaceAll("_", " ");
          } catch {}
          entry = {
            url,
            title: page?.title || title,
            parents: [],
            captured: !!page,
            textBytes: page ? storedTextBytes(page.text) : null,
            ...(page?.selectedContent
              ? { selectedContent: page.selectedContent }
              : {}),
            alwaysInclude: this.sourceAlwaysIncluded(f.id, url),
            inclusionMode: this.sourceInclusionMode(f.id, url),
          };
          entries.set(key, entry);
        }
        if (!entry.parents.some((parent) => parent.id === owner.id))
          entry.parents.push({ id: owner.id, name: owner.name });
      }
    return [...entries.values()];
  }
  effectiveSourceUrls(f: Family): string[] {
    const urls = [
      ...f.sourceUrls,
      ...this.sharedScopesFor(f).flatMap((scope) =>
        scope.sourceUrls.filter((url) => !this.isSourceExcluded(scope.id, url)),
      ),
    ];
    return [
      ...new Map(
        urls
          .filter(
            (url) =>
              !isManualTextUrl(url) &&
              !this.isSourceExcluded(f.id, url) &&
              !this.sourceNeverIncluded(f.id, url),
          )
          .map((url) => [sourceKey(url), url]),
      ).values(),
    ];
  }
  sourceOwner(f: Family, url: string): Family {
    if (f.evidenceScope) return f;
    return (
      this.sharedScopesFor(f).find(
        (scope) =>
          scope.sourceUrls.some(
            (candidate) => sourceKey(candidate) === sourceKey(url),
          ) && !this.isSourceExcluded(scope.id, url),
      ) || f
    );
  }
  sources(family: string): Source[] {
    const scope = this.state.sharedScopes?.find((f) => f.id === family);
    const pages = scope ? this.scopeSources(scope) : this.allSources(family);
    return [
      ...new Map(
        pages
          .filter(
            (source) =>
              !this.isSourceExcluded(family, source.url) &&
              !this.sourceNeverIncluded(family, source.url),
          )
          .sort((a, b) => (a.fetchedAt || "").localeCompare(b.fetchedAt || ""))
          .map((source) => [sourceKey(source.url), source]),
      ).values(),
    ];
  }
  allSources(family: string): Source[] {
    const f = this.state.families.find((f) => f.id === family),
      scope = this.state.sharedScopes?.find((f) => f.id === family);
    if (scope) return this.scopeSources(scope);
    const inherited = f
      ? this.sharedScopesFor(f).flatMap((owner) =>
          this.scopeSources(owner)
            .filter((source) => !this.isSourceExcluded(owner.id, source.url))
            .map((source) => ({
              ...source,
              inheritedFrom: { id: owner.id, name: owner.name },
            })),
        )
      : [];
    const owned = this.rawSources(family);
    const referenced = f
      ? [...new Set([...f.sourceUrls, ...owned.map((source) => source.url)])]
          .filter(
            (url) =>
              ![...owned, ...inherited].some(
                (source) =>
                  source.selectedContent &&
                  sourceKey(source.url) === sourceKey(url),
              ),
          )
          .map((url) => this.cachedSource(url))
          .filter(Boolean)
          .map((source) => {
            const page = source as Source;
            if (page.familyId === f.id) return page;
            const owner =
              this.state.families.find((owner) => owner.id === page.familyId) ||
              this.state.sharedScopes?.find(
                (owner) => owner.id === page.familyId,
              );
            return {
              ...page,
              reusedFrom: {
                id: page.familyId,
                name: owner
                  ? [owner.name, owner.character].filter(Boolean).join(" · ")
                  : "another item",
              },
            };
          })
      : [];
    // A matching URL is a binding to the newest stored article, not another HTML copy.
    return [...inherited, ...owned, ...referenced];
  }
  rawSources(family: string): Source[] {
    return (
      this.db
        .prepare("SELECT value FROM sources WHERE family=?")
        .all(family) as { value: string }[]
    ).map((row) => this.hydrateSource(JSON.parse(row.value) as Source));
  }

  source(id: string): Source | undefined {
    const r = this.db
      .prepare("SELECT value FROM sources WHERE id=?")
      .get(id) as { value: string } | undefined;
    return r ? JSON.parse(r.value) : undefined;
  }
  putSource(s: Source, html: string) {
    if (this.isSourceExcluded(s.familyId, s.url))
      throw new HttpError(
        409,
        "This source was removed from this item. Restore it before importing or fetching it again.",
      );
    atomic(path.join(this.dir, "sources", s.filename), html);
    this.db
      .prepare("INSERT OR REPLACE INTO sources VALUES(?,?,?)")
      .run(s.id, s.familyId, JSON.stringify(s));
  }
  family(id: string) {
    const f =
      this.state.families.find((f) => f.id === id) ||
      this.state.sharedScopes?.find((f) => f.id === id);
    if (!f) throw new HttpError(404, "Item not found.");
    return f;
  }
  clearArticleCache() {
    this.articleIndex = undefined;
  }
  /** Reopen a validated full-project snapshot without running startup migrations. */
  reopenExact(imageRoot = this.images.localRoot) {
    for (const folder of ["captures", "sources", "ai", "exports"])
      mkdirSync(path.join(this.dir, folder), { recursive: true });
    this.db = new DatabaseSync(path.join(this.dir, "workshop.sqlite"));
    this.db.exec("PRAGMA journal_mode=WAL");
    const row = this.db
      .prepare("SELECT value FROM meta WHERE key='project'")
      .get() as { value: string };
    this.state = JSON.parse(row.value);
    this.articleIndex = undefined;
    this.classifications = new Classifications(
      path.join(this.dir, "classification-overrides.json"),
    );
    this.names = new Names(path.join(this.dir, "name-overrides.json"));
    this.images = new Images(
      existsSync(path.join(this.dir, "image-library"))
        ? path.join(this.dir, "image-library")
        : imageRoot,
      path.join(this.dir, "image-overrides.json"),
      imageRoot,
    );
    this.records = new Map();
    this.reloadRecords();
    this.emit("change", this.state.revision);
  }
  close() {
    this.db.close();
  }
}
export function atomic(filename: string, value: string | Buffer) {
  mkdirSync(path.dirname(filename), { recursive: true });
  writeFileSync(filename + ".tmp", value);
  renameSync(filename + ".tmp", filename);
}
export class HttpError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
