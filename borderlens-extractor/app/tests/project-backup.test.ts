import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync,
  mkdirSync,
  writeFileSync,
  readFileSync,
  rmSync,
  existsSync,
  symlinkSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import AdmZip from "adm-zip";
import { Store, hash } from "../src/server/store.ts";
import { Worker } from "../src/server/worker.ts";
import { api } from "../src/server/http.ts";
import { exportProject, importProject } from "../src/server/project-backup.ts";
import { backupFilename, type BackupUI } from "../src/shared/project-backup.ts";
import type { Family } from "../src/shared/models.ts";
const ui: BackupUI = {
  selection: "one",
  groups: { Artifacts: false },
  tab: "sources",
  view: "catalogue",
  query: "kept",
  filter: "all",
};
function fixture(t: any) {
  const root = mkdtempSync(path.join(tmpdir(), "project-backup-")),
    dir = path.join(root, "project"),
    images = path.join(root, "images");
  mkdirSync(path.join(images, "artifacts"), { recursive: true });
  writeFileSync(
    path.join(images, "artifacts", "corrosive.png"),
    Buffer.from("fixture image bytes"),
  );
  const s = new Store(dir, images),
    w = new Worker(s, {
      run: async () => {
        throw Error("Unexpected AI call");
      },
    } as any);
  const family = (id: string): Family => ({
    id,
    name: id,
    category: "Artifacts",
    subtype: "Artifacts",
    character: "Brick",
    element: "Corrosive",
    aliases: [],
    roots: ["gd_fixture.title"],
    sourceUrls: [],
    history: [],
    revision: 5,
    status: "queued",
    stage: "draft",
    inputHash: "hash",
    issue: null,
    notes: "Keep correction",
    gameOnly: false,
    manualOutput: false,
    updatedAt: new Date().toISOString(),
  });
  s.state.families = [family("one"), family("two")];
  s.state.captures = [
    {
      id: "abc123",
      name: "game.zip",
      version: "fixture",
      importedAt: new Date().toISOString(),
      objects: 1,
      manifest: {},
    },
  ];
  writeFileSync(
    path.join(dir, "captures", "abc123.zip"),
    Buffer.from("original extractor archive"),
  );
  s.db.prepare("INSERT INTO raw VALUES(?,?,?,?,?)").run(
    "abc123",
    "raw-one",
    "gd_fixture.title",
    "WillowGame.WeaponNamePartDefinition",
    JSON.stringify({
      id: "raw-one",
      path: "gd_fixture.title",
      record_type: "object",
      class: "WillowGame.WeaponNamePartDefinition",
      properties: { PartName: "Kept" },
    }),
  );
  s.reloadRecords();
  w.setManualName("one", "Kept artifact");
  w.setManualType("one", "Artifacts");
  const source = w.addTextEvidence("one", {
    label: "Kept evidence",
    text: "Useful selected facts.\n\nDamage +25%.",
  });
  const parent = w.promoteSource("one", source.url);
  w.setSharedSourceMode("one", source.url, "always");
  w.setSharedSourceMode("two", source.url, "never");
  s.put("one", "output", { name: "Kept artifact", summary: "Saved JSON" });
  s.put("one", "draft", { entry: { summary: "Saved draft" } });
  s.put("one", "factualOutline", {
    version: "1",
    hash: "fixture-outline",
    fixed: { id: "one" },
    facts: [
      {
        id: "accepted",
        status: "accepted",
        provenance: [{ hash: "source-version" }],
      },
    ],
  });
  s.put("one", "factualDecisions", [
    {
      id: "accepted",
      status: "accepted",
      reason: "Validated source interpretation",
    },
  ]);
  s.put("one", "proseDraft", {
    hash: "fixture-outline",
    prose: { entry: { summary: "Original AI prose retained in backup." } },
  });
  s.put("_sharedSources", "readingCorrection:fixture", {
    sourceHash: "source-version",
    feedback: "Corrected interpretation",
    reading: { facts: [] },
  });
  s.put("one", "evidenceStatsHistory", [{ outcome: "completed", requests: 2 }]);
  s.images.set("one", "artifacts/corrosive.png");
  mkdirSync(path.join(dir, "ai", "codex", "nested"), { recursive: true });
  writeFileSync(
    path.join(dir, "ai", "codex", "nested", "answer.json"),
    '{"cached":true}',
  );
  writeFileSync(path.join(dir, "exports", "one.json"), '{"exported":true}');
  s.state.run = {
    ...s.state.run,
    status: "paused",
    queue: ["one", "two"],
    index: 1,
    currentId: "two",
    sourceMode: "saved",
    message: "Paused exactly here",
  };
  s.state.buildCheckpoint = structuredClone(s.state.run);
  s.save();
  t.after(() => {
    s.close();
    rmSync(root, { recursive: true, force: true });
  });
  return { s, w, root, dir, source, parent };
}
function rows(s: Store) {
  return Object.fromEntries(
    ["meta", "raw", "artifacts", "sources"].map((table) => [
      table,
      s.db.prepare(`SELECT * FROM ${table} ORDER BY 1,2`).all(),
    ]),
  );
}
test("timestamped ZIP round-trip retains every database table, sidecar, evidence, caches, images, UI and paused checkpoint", (t) => {
  const { s, w, dir, source } = fixture(t),
    before = rows(s),
    state = structuredClone(s.state);
  const backup = exportProject(w, ui),
    zip = new AdmZip(backup.buffer);
  assert.match(backup.filename, /^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}\.zip$/);
  assert.equal(
    backupFilename(new Date(2026, 9, 27, 13, 16)),
    "2026-10-27_13-16.zip",
  );
  for (const name of [
    "data/workshop.sqlite",
    "data/classification-overrides.json",
    "data/name-overrides.json",
    "data/image-overrides.json",
    "data/sources/" + source.filename,
    "data/captures/abc123.zip",
    "data/ai/codex/nested/answer.json",
    "data/exports/one.json",
    "images/artifacts/corrosive.png",
  ])
    assert.ok(zip.getEntry(name), name);
  assert.ok(
    !zip.getEntries().some((e) => /sqlite-(wal|shm)$/.test(e.entryName)),
  );
  assert.deepEqual(rows(s), before);
  assert.deepEqual(s.state, state);
  s.put("one", "output", { summary: "Changed after backup" });
  s.state.families[0].notes = "changed";
  s.save();
  writeFileSync(
    path.join(dir, "ai", "new-file.txt"),
    "must disappear after import",
  );
  let changed = 0;
  s.on("change", () => changed++);
  const restored = importProject(w, backup.buffer);
  assert.deepEqual(restored.ui, ui);
  assert.deepEqual(rows(s), before);
  assert.deepEqual(s.state, state);
  assert.ok(changed > 0);
  assert.ok(existsSync(restored.recoveryCopy));
  assert.equal(s.records.get("gd_fixture.title")?.properties?.PartName, "Kept");
  assert.equal(s.sourceInclusionMode("one", source.url), "always");
  assert.equal(s.sourceInclusionMode("two", source.url), "never");
  assert.equal(
    readFileSync(
      path.join(s.images.root, "artifacts", "corrosive.png"),
      "utf8",
    ),
    "fixture image bytes",
  );
  assert.equal(
    s.images.match(s.family("one")).image,
    "artifacts/corrosive.png",
  );
  assert.equal(
    readFileSync(path.join(dir, "sources", source.filename), "utf8"),
    source.text,
  );
  assert.equal(
    readFileSync(
      path.join(dir, "ai", "codex", "nested", "answer.json"),
      "utf8",
    ),
    '{"cached":true}',
  );
  assert.ok(!existsSync(path.join(dir, "ai", "new-file.txt")));
  const again = new AdmZip(exportProject(w, ui).buffer);
  assert.equal(
    again.getEntries().filter((e) => e.entryName.endsWith("corrosive.png"))
      .length,
    1,
  );
});
test("damaged, incomplete, foreign and traversal backups never change the current project", (t) => {
  const { s, w, root } = fixture(t),
    backup = exportProject(w, ui).buffer,
    before = rows(s);
  const damaged = new AdmZip(backup);
  damaged.updateFile("data/name-overrides.json", Buffer.from("damaged"));
  const missing = new AdmZip(backup);
  missing.deleteFile("data/workshop.sqlite");
  const slip = new AdmZip(backup);
  slip.addFile("../outside", Buffer.from("bad"));
  const foreign = new AdmZip();
  foreign.addFile("manifest.json", Buffer.from("{}"));
  for (const bytes of [
    damaged.toBuffer(),
    missing.toBuffer(),
    slip.toBuffer(),
    foreign.toBuffer(),
    Buffer.from("SQLite format 3\0"),
  ]) {
    assert.throws(() => importProject(w, bytes));
    assert.deepEqual(rows(s), before);
  }
  assert.ok(!existsSync(path.join(root, "outside")));
});
test("restore rolls back the old project if opening the replacement fails", (t) => {
  const { s, w } = fixture(t),
    backup = exportProject(w, ui).buffer;
  s.put("one", "output", { summary: "Current project must survive" });
  s.save();
  const before = rows(s);
  const original = s.reopenExact.bind(s);
  let first = true;
  s.reopenExact = (imageRoot?: string) => {
    if (first) {
      first = false;
      throw Error("Simulated reopen failure");
    }
    original(imageRoot);
  };
  assert.throws(() => importProject(w, backup), /Simulated reopen failure/);
  assert.deepEqual(rows(s), before);
  assert.equal(
    s.images.match(s.family("one")).image,
    "artifacts/corrosive.png",
  );
});
test("API exports/restores ZIPs and rejects active work/cross-origin restore", async (t) => {
  const { s, w } = fixture(t),
    server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((resolve) => server.once("listening", resolve));
  t.after(() => {
    server.closeAllConnections();
    server.close();
  });
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  const response = await fetch(base + "/api/project-backup/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(ui),
  });
  assert.equal(response.status, 200);
  assert.match(
    response.headers.get("Content-Disposition")!,
    /\d{4}-\d{2}-\d{2}_\d{2}-\d{2}\.zip/,
  );
  const bytes = await response.arrayBuffer(),
    body = () => {
      const form = new FormData();
      form.append("backup", new Blob([bytes]), "2026-10-27_13-16.zip");
      return form;
    };
  w.busy = true;
  assert.equal(
    (
      await fetch(base + "/api/project-backup/import", {
        method: "POST",
        body: body(),
      })
    ).status,
    409,
  );
  w.busy = false;
  assert.equal(
    (
      await fetch(base + "/api/project-backup/import", {
        method: "POST",
        headers: { Origin: "https://example.com" },
        body: body(),
      })
    ).status,
    403,
  );
  s.put("one", "output", { summary: "After export" });
  const imported = await fetch(base + "/api/project-backup/import", {
    method: "POST",
    body: body(),
  });
  assert.equal(imported.status, 200);
  assert.equal(s.get<any>("one", "output").summary, "Saved JSON");
});
