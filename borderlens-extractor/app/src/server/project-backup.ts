import AdmZip from "adm-zip";
import { DatabaseSync } from "node:sqlite";
import { randomUUID } from "node:crypto";
import { tmpdir } from "node:os";
import path from "node:path";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  writeFileSync,
  renameSync,
  rmSync,
  lstatSync,
} from "node:fs";
import { z } from "zod";
import { Category, Stage } from "../shared/models.ts";
import { EvidenceScope } from "../shared/evidence-scopes.ts";
import { BackupUI, backupFilename } from "../shared/project-backup.ts";
import {
  CATALOGUE_SCHEMA_VERSION,
  COMPILER_VERSION,
} from "../shared/versions.ts";
import { ClassificationFile } from "../shared/classification.ts";
import { NameFile } from "../shared/names.ts";
import { Images } from "./images.ts";
import { Store, HttpError, hash } from "./store.ts";
import { AgentRouter } from "./agents.ts";
import { Research } from "./research.ts";
import { BrowserImports } from "./browser-imports.ts";
import type { Worker } from "./worker.ts";

const Manifest = z
  .object({
    format: z.literal("borderlens-project-backup"),
    version: z.literal(1),
    createdAt: z.string(),
    compilerVersion: z.string(),
    catalogueSchemaVersion: z.string(),
    ui: BackupUI,
    files: z
      .array(
        z
          .object({
            path: z.string(),
            bytes: z.number().int().nonnegative(),
            sha256: z.string().regex(/^[a-f0-9]{64}$/),
          })
          .strict(),
      )
      .max(100000),
  })
  .strict();
const FamilyState = z
  .object({
    id: z.string().min(1),
    name: z.string(),
    category: Category,
    subtype: z.string(),
    aliases: z.array(z.string()),
    roots: z.array(z.string()),
    sourceUrls: z.array(z.string()),
    status: z.enum(["queued", "running", "blocked", "done", "excluded"]),
    stage: Stage,
    inputHash: z.string(),
    notes: z.string(),
    gameOnly: z.boolean(),
    manualOutput: z.boolean(),
    revision: z.number().int().nonnegative(),
    updatedAt: z.string(),
    history: z.array(
      z
        .object({ at: z.string(), stage: z.string(), message: z.string() })
        .passthrough(),
    ),
    evidenceScope: EvidenceScope.optional(),
  })
  .passthrough();
const RunState = z
  .object({
    status: z.enum([
      "idle",
      "running",
      "pausing",
      "paused",
      "blocked",
      "complete",
    ]),
    queue: z.array(z.string()),
    index: z.number().int().nonnegative(),
    message: z.string(),
    pauseRequested: z.boolean(),
  })
  .passthrough();
const ProjectState = z
  .object({
    schemaVersion: z.literal(1),
    revision: z.number().int().nonnegative(),
    families: z.array(FamilyState),
    sharedScopes: z.array(FamilyState).optional(),
    captures: z.array(
      z
        .object({
          id: z.string().regex(/^[a-f0-9]+$/),
          name: z.string(),
          version: z.string(),
          objects: z.number(),
          importedAt: z.string(),
        })
        .passthrough(),
    ),
    run: RunState,
    buildCheckpoint: RunState.optional(),
    settings: z
      .object({
        agent: z.enum(["grok", "codex"]),
        model: z.string(),
        writingStyle: z.string(),
        research: z.boolean(),
        maxItems: z.number().int().positive(),
      })
      .passthrough(),
    coverage: z
      .object({
        status: z.enum(["idle", "running", "complete", "partial", "failed"]),
        message: z.string(),
        entries: z.array(z.unknown()),
        errors: z.array(z.unknown()),
      })
      .passthrough(),
    activity: z.array(z.unknown()),
  })
  .passthrough();
const MAX_BYTES = 4 * 1024 ** 3;
export function requireBackupIdle(worker: Worker) {
  if (
    worker.busy ||
    worker.coverageBusy ||
    worker.identitySync ||
    worker.closed ||
    ["running", "pausing"].includes(worker.store.state.run.status)
  )
    throw new HttpError(
      409,
      "Pause processing and wait for the current step to finish before exporting or importing project data.",
    );
}
function walk(
  root: string,
  visit: (name: string, full: string) => void,
  exclude?: (full: string) => boolean,
  relative = "",
) {
  for (const item of readdirSync(root, { withFileTypes: true })) {
    const name = relative ? relative + "/" + item.name : item.name,
      full = path.join(root, item.name);
    if (exclude?.(full)) continue;
    if (item.isSymbolicLink())
      throw new HttpError(
        400,
        "Project backup cannot include symbolic links: " + name,
      );
    if (item.isDirectory())
      walk(full, (n, p) => visit(item.name + "/" + n, p), exclude);
    else if (item.isFile()) visit(name, full);
    else throw new HttpError(400, "Unsupported project file: " + name);
  }
}
export function exportProject(worker: Worker, ui: BackupUI) {
  requireBackupIdle(worker);
  const store = worker.store;
  validateProject(store.dir);
  const temporary = mkdtempSync(path.join(tmpdir(), "borderlens-backup-"));
  try {
    const snapshot = path.join(temporary, "workshop.sqlite");
    // VACUUM INTO includes committed WAL state in one standalone consistent database.
    store.db.exec("VACUUM INTO '" + snapshot.replaceAll("'", "''") + "'");
    const zip = new AdmZip(),
      files: z.infer<typeof Manifest>["files"] = [];
    let total = 0;
    const add = (name: string, full: string) => {
      safeName(name);
      total += lstatSync(full).size;
      if (total > MAX_BYTES)
        throw new HttpError(413, "Project exceeds the 4 GB backup limit.");
      const bytes = readFileSync(full);
      zip.addFile(name, bytes);
      files.push({ path: name, bytes: bytes.length, sha256: hash(bytes) });
    };
    const images = path.resolve(store.images.root);
    walk(
      store.dir,
      (name, full) => {
        if (
          [
            "workshop.sqlite",
            "workshop.sqlite-wal",
            "workshop.sqlite-shm",
          ].includes(name)
        )
          return;
        add("data/" + name, full);
      },
      (full) => path.resolve(full) === images,
    );
    add("data/workshop.sqlite", snapshot);
    if (existsSync(images))
      walk(images, (name, full) => add("images/" + name, full));
    const manifest = Manifest.parse({
      format: "borderlens-project-backup",
      version: 1,
      createdAt: new Date().toISOString(),
      compilerVersion: COMPILER_VERSION,
      catalogueSchemaVersion: CATALOGUE_SCHEMA_VERSION,
      ui: BackupUI.parse(ui),
      files,
    });
    const metadata = Buffer.from(JSON.stringify(manifest, null, 2));
    if (metadata.length > 32 * 1024 ** 2)
      throw new HttpError(413, "Backup inventory exceeds the supported size.");
    zip.addFile("backup.json", metadata);
    const buffer = zip.toBuffer();
    if (buffer.length > 1024 ** 3)
      throw new HttpError(
        413,
        "Compressed backup exceeds the 1 GB import limit.",
      );
    return { filename: backupFilename(), buffer };
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
}
function safeName(name: string) {
  if (
    !name ||
    name.includes("\\") ||
    /[\x00-\x1f:]/.test(name) ||
    name.startsWith("/") ||
    name.split("/").some((part) => !part || part === "." || part === "..")
  )
    throw new HttpError(400, "Backup contains an unsafe file path.");
  if (
    name !== "backup.json" &&
    !name.startsWith("data/") &&
    !name.startsWith("images/")
  )
    throw new HttpError(400, "Backup contains an unexpected file.");
  if (
    name.startsWith("data/image-library/") ||
    ["data/workshop.sqlite-wal", "data/workshop.sqlite-shm"].includes(name)
  )
    throw new HttpError(
      400,
      "Backup contains an invalid database or image-library layout.",
    );
}
function validateProject(dir: string) {
  const filename = path.join(dir, "workshop.sqlite");
  if (!existsSync(filename))
    throw new HttpError(400, "Backup is missing its project database.");
  const db = new DatabaseSync(filename, { readOnly: true });
  try {
    const objects = db
      .prepare(
        "SELECT name,type,sql FROM sqlite_master WHERE name NOT GLOB 'sqlite_*'",
      )
      .all() as { name: string; type: string; sql: string }[];
    if (
      objects.some(
        (row) =>
          row.type !== "table" ||
          !["meta", "raw", "artifacts", "sources"].includes(row.name) ||
          /\bvirtual\b/i.test(row.sql),
      )
    )
      throw new HttpError(400, "Unsupported backup database objects.");
    const columns = {
      meta: ["key", "value"],
      raw: ["capture", "id", "path", "class", "value"],
      artifacts: ["family", "kind", "value"],
      sources: ["id", "family", "value"],
    };
    for (const [table, names] of Object.entries(columns)) {
      const actual = db
        .prepare(`PRAGMA table_info(${table})`)
        .all()
        .map((row) => row.name);
      if (JSON.stringify(actual) !== JSON.stringify(names))
        throw new HttpError(400, "Unsupported backup database schema.");
    }
    if (Object.values(db.prepare("PRAGMA quick_check").get() || {})[0] !== "ok")
      throw new HttpError(400, "Backup database integrity check failed.");
    const row = db
      .prepare("SELECT value FROM meta WHERE key='project'")
      .get() as { value: string } | undefined;
    const state = ProjectState.parse(JSON.parse(row?.value || "null"));
    for (const table of ["raw", "artifacts"])
      for (const row of db.prepare(`SELECT value FROM ${table}`).iterate())
        JSON.parse(String(row.value));
    if (["running", "pausing"].includes(state.run.status))
      throw new HttpError(
        400,
        "This backup contains active processing. Export a paused project instead.",
      );
    for (const page of db.prepare("SELECT value FROM sources").all()) {
      const source = JSON.parse(String(page.value));
      if (
        !source ||
        !["id", "familyId", "url", "title", "text", "hash"].every(
          (key) => typeof source[key] === "string",
        )
      )
        throw new HttpError(400, "Invalid backup evidence metadata.");
      if (
        typeof source.filename !== "string" ||
        source.filename !== path.basename(source.filename) ||
        !source.filename ||
        source.filename === ".." ||
        !existsSync(path.join(dir, "sources", source.filename))
      )
        throw new HttpError(400, "Backup is missing a saved evidence file.");
    }
    for (const capture of state.captures)
      if (
        typeof capture.id !== "string" ||
        !/^[a-f0-9]+$/.test(capture.id) ||
        !existsSync(path.join(dir, "captures", capture.id + ".zip"))
      )
        throw new HttpError(
          400,
          "Backup is missing a game extraction archive.",
        );
    ClassificationFile.parse(
      JSON.parse(
        readFileSync(path.join(dir, "classification-overrides.json"), "utf8"),
      ),
    );
    NameFile.parse(
      JSON.parse(readFileSync(path.join(dir, "name-overrides.json"), "utf8")),
    );
    new Images(
      path.join(dir, "image-library"),
      path.join(dir, "image-overrides.json"),
    );
  } finally {
    db.close();
  }
}
export function importProject(worker: Worker, archive: string | Buffer) {
  requireBackupIdle(worker);
  const store = worker.store,
    stage = mkdtempSync(
      path.join(
        path.dirname(store.dir),
        ".borderlens-restore-" + path.basename(store.dir) + "-",
      ),
    );
  let moved = false,
    installed = false,
    closed = false;
  const oldImageRoot = store.images.root;
  const previous =
    store.dir +
    ".before-restore-" +
    backupFilename().replace(".zip", "") +
    "-" +
    randomUUID().slice(0, 8);
  try {
    const zip = new AdmZip(archive),
      entries = zip.getEntries();
    if (entries.length > 100001)
      throw new HttpError(413, "Backup contains too many files.");
    let total = 0;
    const byName = new Map<string, ReturnType<AdmZip["getEntries"]>[number]>();
    for (const entry of entries) {
      if (entry.isDirectory) {
        const directory = entry.entryName.replace(/\/$/, "");
        if (!["data", "images"].includes(directory)) safeName(directory);
        continue;
      }
      safeName(entry.entryName);
      if (
        byName.has(entry.entryName) ||
        ((entry.attr >>> 16) & 0o170000) === 0o120000
      )
        throw new HttpError(
          400,
          "Backup contains duplicate paths or symbolic links.",
        );
      total += entry.header.size;
      if (total > MAX_BYTES || entry.header.size > 2 * 1024 ** 3)
        throw new HttpError(413, "Backup exceeds the supported expanded size.");
      byName.set(entry.entryName, entry);
    }
    const metadata = byName.get("backup.json");
    if (!metadata || metadata.header.size > 32 * 1024 ** 2)
      throw new HttpError(
        400,
        "Choose a complete Borderlens project backup ZIP, not a game extraction or SQLite file.",
      );
    const manifest = Manifest.parse(
      JSON.parse(metadata.getData().toString("utf8")),
    );
    if (manifest.files.length !== byName.size - 1)
      throw new HttpError(
        400,
        "Backup file inventory does not match the archive.",
      );
    const seen = new Set<string>();
    for (const file of manifest.files) {
      safeName(file.path);
      if (file.path === "backup.json" || seen.has(file.path))
        throw new HttpError(400, "Invalid backup file inventory.");
      seen.add(file.path);
      const entry = byName.get(file.path);
      if (!entry || entry.header.size !== file.bytes)
        throw new HttpError(
          400,
          "Backup file is missing or has changed size: " + file.path,
        );
      const bytes = entry.getData();
      if (bytes.length !== file.bytes || hash(bytes) !== file.sha256)
        throw new HttpError(400, "Backup checksum failed: " + file.path);
      const target = path.join(stage, file.path);
      mkdirSync(path.dirname(target), { recursive: true });
      writeFileSync(target, bytes);
    }
    const data = path.join(stage, "data"),
      images = path.join(stage, "images");
    mkdirSync(images, { recursive: true });
    renameSync(images, path.join(data, "image-library"));
    validateProject(data);
    // No current data is touched before every archive/database check succeeds.
    store.close();
    closed = true;
    renameSync(store.dir, previous);
    moved = true;
    renameSync(data, store.dir);
    installed = true;
    try {
      store.reopenExact();
    } catch (error) {
      try {
        store.close();
      } catch {}
      throw error;
    }
    const ai =
        worker.ai instanceof AgentRouter ? new AgentRouter(store) : worker.ai,
      research = new Research(store),
      imports = new BrowserImports(store, worker);
    worker.ai = ai;
    worker.research = research;
    worker.browserImports = imports;
    return {
      ok: true,
      ui: manifest.ui,
      createdAt: manifest.createdAt,
      recoveryCopy: previous,
    };
  } catch (error: any) {
    if (moved) {
      try {
        store.close();
      } catch {}
      if (installed) rmSync(store.dir, { recursive: true, force: true });
      renameSync(previous, store.dir);
      store.reopenExact(oldImageRoot);
    } else if (closed) {
      store.reopenExact(oldImageRoot);
    }
    if (error instanceof HttpError) throw error;
    throw new HttpError(
      400,
      "Could not restore project backup: " + error.message,
    );
  } finally {
    rmSync(stage, { recursive: true, force: true });
  }
}
