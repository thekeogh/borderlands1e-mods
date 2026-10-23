// Optional local verification. Never edits or uploads the supplied ZIP.
import { readFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
import { Store } from "../src/server/store.ts";
import { importZip } from "../src/server/importer.ts";
import { buildPacket } from "../src/server/evidence.ts";
import { Worker } from "../src/server/worker.ts";
const input = process.argv[2];
if (!input)
  throw new Error(
    "Supply a capture ZIP path. Add --codex to test one live game-evidence draft.",
  );
const dir = mkdtempSync(path.join(tmpdir(), "borderlens-real-")),
  s = new Store(dir);
try {
  console.log(importZip(s, readFileSync(input), path.basename(input)));
  const f = s.state.families.find((f) => /^hellfire$/i.test(f.name));
  assert.ok(f, "Hellfire discovered");
  const p = buildPacket(s, f);
  assert.ok(p.evidence.length > 1);
  assert.deepEqual(p.facts.elements, ["incendiary"]);
  assert.equal(p.facts.redText, "We don't need no water...");
  console.log(
    JSON.stringify(
      {
        id: f.id,
        evidence: p.evidence.length,
        facts: p.facts,
        categories: Object.fromEntries(
          [...new Set(s.state.families.map((f) => f.category))].map((c) => [
            c,
            s.state.families.filter((f) => f.category === c).length,
          ]),
        ),
      },
      null,
      2,
    ),
  );
  if (process.argv.includes("--codex")) {
    s.state.settings.research = false;
    const w = new Worker(s);
    await w.action(f.id, "rebuild", {});
    while (w.busy) await new Promise((r) => setTimeout(r, 500));
    console.log(
      JSON.stringify(
        { status: f.status, issue: f.issue, entry: s.get(f.id, "output") },
        null,
        2,
      ),
    );
    assert.equal(f.status, "done");
  }
} finally {
  s.close();
  rmSync(dir, { recursive: true, force: true });
}
