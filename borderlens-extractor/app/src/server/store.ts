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
  now,
  type Project,
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
  classifications: Classifications;
  db: DatabaseSync;
  state: Project;
  records: Map<string, Raw> = new Map();
  constructor(public dir: string) {
    super();
    mkdirSync(dir, { recursive: true });
    for (const d of ["captures", "sources", "ai", "exports"])
      mkdirSync(path.join(dir, d), { recursive: true });
    this.classifications = new Classifications(
      path.join(dir, "classification-overrides.json"),
    );
    this.db = new DatabaseSync(path.join(dir, "workshop.sqlite"));
    this.db.exec(
      "PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL); CREATE TABLE IF NOT EXISTS raw(capture TEXT,id TEXT,path TEXT,class TEXT,value TEXT,PRIMARY KEY(capture,id)); CREATE TABLE IF NOT EXISTS artifacts(family TEXT,kind TEXT,value TEXT,PRIMARY KEY(family,kind)); CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,family TEXT,value TEXT);",
    );
    const r = this.db
      .prepare("SELECT value FROM meta WHERE key=?")
      .get("project") as { value: string } | undefined;
    this.state = r ? JSON.parse(r.value) : initial();
    if (this.state.schemaVersion !== 1)
      throw new Error(
        "Unsupported project database version; keep this folder for migration.",
      );
    for (const f of this.state.families)
      if (f.status === "running") f.status = "queued";
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
    for (const f of this.state.families) {
      const output = this.get<any>(f.id, "output");
      const provenance = this.get<any>(f.id, "provenance");
      if (
        output &&
        (output.schemaVersion !== CATALOGUE_SCHEMA_VERSION ||
          provenance?.compilerVersion !== COMPILER_VERSION) &&
        f.status !== "excluded"
      ) {
        f.stage = "evidence";
        f.status = f.manualOutput ? "blocked" : "queued";
        f.issue = f.manualOutput
          ? "Saved manual entry uses an older schema. Its content is retained; update it to schema 2 before saving."
          : null;
        this.forget(f.id, ["packet", "draft", "validationFeedback"]);
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
      if (effective) f.classification = effective;
      else delete f.classification;
      if (
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
  syncClassifications() {
    if (this.classifications.reload()) this.save();
  }
  save() {
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
  sources(family: string): Source[] {
    return (
      this.db
        .prepare("SELECT value FROM sources WHERE family=?")
        .all(family) as { value: string }[]
    ).map((r) => {
      const source = JSON.parse(r.value) as Source;
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
    });
  }
  source(id: string): Source | undefined {
    const r = this.db
      .prepare("SELECT value FROM sources WHERE id=?")
      .get(id) as { value: string } | undefined;
    return r ? JSON.parse(r.value) : undefined;
  }
  putSource(s: Source, html: string) {
    atomic(path.join(this.dir, "sources", s.filename), html);
    this.db
      .prepare("INSERT OR REPLACE INTO sources VALUES(?,?,?)")
      .run(s.id, s.familyId, JSON.stringify(s));
  }
  family(id: string) {
    const f = this.state.families.find((f) => f.id === id);
    if (!f) throw new HttpError(404, "Item not found.");
    return f;
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
