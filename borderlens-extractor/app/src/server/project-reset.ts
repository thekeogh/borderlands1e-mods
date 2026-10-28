import { mkdirSync, readdirSync, rmSync } from "node:fs";
import path from "node:path";
import { initial } from "../shared/models.ts";
import { Store, HttpError } from "./store.ts";
import { defaultImageRoot } from "./images.ts";
import { AgentRouter } from "./agents.ts";
import { Research } from "./research.ts";
import { BrowserImports } from "./browser-imports.ts";
import type { Worker } from "./worker.ts";
const transient = new Set([
  "pendingRebuild",
  "rebuildPlan",
  "validationFeedback",
  "proseAssemblyFeedback",
  "buildAttempt",
  "draftAgent",
  "modifierRepairs",
  "proseRepairs",
  "statRepairs",
  "sourcePriorityRepair",
  "workingSourceLedger",
  "evidenceFollowup",
  "evidenceRequestNotice",
  "additionalEvidenceUsage",
]);
const compiled = new Set([
  "packet",
  "draft",
  "manualDraft",
  "factualOutline",
  "proseDraft",
  "outlineMeasurements",
  "matches",
  "parts",
  "output",
  "validatedPacket",
  "provenance",
  "finalValidation",
]);
function resetServices(worker: Worker) {
  if (worker.ai instanceof AgentRouter)
    worker.ai = new AgentRouter(worker.store);
  else {
    worker.ai.resetFailures?.();
    worker.ai.resetCancellation?.();
    worker.ai.setItemContext?.(null);
  }
  worker.research = new Research(worker.store);
  worker.browserImports = new BrowserImports(worker.store, worker);
}
export function resetProject(worker: Worker, scope: "all" | "generated") {
  if (
    worker.busy ||
    worker.coverageBusy ||
    worker.identitySync ||
    worker.closed ||
    ["running", "pausing"].includes(worker.store.state.run.status)
  )
    throw new HttpError(
      409,
      "Pause processing and wait for coverage/metadata sync to finish first.",
    );
  const store = worker.store;
  if (scope === "all") {
    const imageRelative = path.relative(
      path.resolve(store.dir),
      path.resolve(store.images.root),
    );
    const imageRoot =
      !imageRelative ||
      (!imageRelative.startsWith(".." + path.sep) &&
        imageRelative !== ".." &&
        !path.isAbsolute(imageRelative))
        ? defaultImageRoot
        : store.images.root;
    // Only owned recovery/staging directories; exported backups elsewhere are never touched.
    const parent = path.dirname(store.dir),
      name = path.basename(store.dir);
    for (const entry of readdirSync(parent))
      if (
        entry.startsWith(name + ".before-restore-") ||
        entry.startsWith(".borderlens-restore-" + name + "-")
      )
        rmSync(path.join(parent, entry), { recursive: true, force: true });
    store.close();
    rmSync(store.dir, { recursive: true, force: true });
    const fresh = new Store(store.dir, imageRoot);
    // Keep the Store/EventEmitter identity used by HTTP/SSE and existing services.
    store.db = fresh.db;
    store.state = fresh.state;
    store.records = fresh.records;
    store.images = fresh.images;
    store.names = fresh.names;
    store.classifications = fresh.classifications;
    store.clearArticleCache();
    resetServices(worker);
    store.emit("change", store.state.revision);
  } else {
    const manual = new Set(
      store.state.families.filter((f) => f.manualOutput).map((f) => f.id),
    );
    const remove = store.db.prepare(
      "DELETE FROM artifacts WHERE family=? AND kind=?",
    );
    for (const row of store.db
      .prepare("SELECT family,kind FROM artifacts")
      .all() as { family: string; kind: string }[]) {
      const generated =
        compiled.has(row.kind) ||
        row.kind.startsWith("draft:compiler:") ||
        row.kind.startsWith("revision:") ||
        row.kind.startsWith("factualRevision:");
      if (
        transient.has(row.kind) ||
        (!manual.has(row.family) && generated) ||
        (row.family === "_parts" && !manual.size)
      )
        remove.run(row.family, row.kind);
    }
    for (const f of store.state.families) {
      if (f.manualOutput) continue;
      f.stage = "evidence";
      if (f.status !== "excluded") f.status = "queued";
      f.issue = null;
      delete f.compiledCompilerVersion;
      delete f.compiledSchemaVersion;
    }
    delete store.state.buildCheckpoint;
    delete store.state.evidenceStats;
    store.state.run = {
      ...initial().run,
      message: "Processing reset; research and corrections retained.",
    };
    for (const directory of ["ai", "exports"]) {
      rmSync(path.join(store.dir, directory), { recursive: true, force: true });
      mkdirSync(path.join(store.dir, directory), { recursive: true });
    }
    resetServices(worker);
    store.save();
  }
}
