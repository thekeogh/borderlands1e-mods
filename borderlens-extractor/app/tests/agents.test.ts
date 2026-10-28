import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { z } from "zod";
import { Store } from "../src/server/store.ts";
import { AgentRouter } from "../src/server/agents.ts";
import { Worker, type AI } from "../src/server/worker.ts";
import { api } from "../src/server/http.ts";
import { effortForTask } from "../src/shared/agents.ts";
function setup(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "borderlens-agents-")),
    s = new Store(dir);
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  return s;
}
const shape = z.object({ ok: z.boolean() }).strict();
function fake(run: () => Promise<unknown>): AI {
  return {
    status: async () => ({ available: true, ready: true, chatgpt: true }),
    run: async (_l, _p, schema) => schema.parse(await run()),
  };
}
test("Grok is default; failed default switches once, failure cooldown persists, recheck restores priority", async (t) => {
  const s = setup(t),
    calls: string[] = [],
    messages: string[] = [];
  const runners = {
    grok: fake(async () => {
      calls.push("grok");
      throw Error("privacy mode required");
    }),
    codex: fake(async () => {
      calls.push("codex");
      return { ok: true };
    }),
  };
  const router = new AgentRouter(s, runners);
  assert.equal(s.state.settings.agent, "grok");
  assert.deepEqual(
    await router.run("Build fixture", "data", shape, "", false, (m) =>
      messages.push(m),
    ),
    { ok: true },
  );
  assert.deepEqual(calls, ["grok", "codex"]);
  assert.ok(messages.some((m) => m.includes("switching to Codex")));
  const reopened = new AgentRouter(s, runners);
  await reopened.run("Build fixture", "data", shape, "", false, () => {});
  assert.deepEqual(calls, ["grok", "codex", "codex"]);
  reopened.resetFailures();
  await reopened.run("Build fixture", "data", shape, "", false, () => {});
  assert.deepEqual(calls.slice(-2), ["grok", "codex"]);
  assert.match((await reopened.status()).providers.grok.lastError, /privacy/);
});
test("Codex selection reverses fallback order; both failures stop without bouncing forever", async (t) => {
  const s = setup(t),
    calls: string[] = [];
  s.state.settings.agent = "codex";
  const router = new AgentRouter(s, {
    grok: fake(async () => {
      calls.push("grok");
      throw Error("grok offline");
    }),
    codex: fake(async () => {
      calls.push("codex");
      throw Error("codex offline");
    }),
  });
  await assert.rejects(
    router.run("Read source fixture", "data", shape, "", false, () => {}),
    /No agent completed.*codex offline.*grok offline/,
  );
  assert.deepEqual(calls, ["codex", "grok"]);
  await assert.rejects(
    router.run("Read source fixture", "data", shape, "", false, () => {}),
    /No agent/,
  );
  assert.equal(calls.length, 2);
});
test("effort stays low for writing, medium for extraction, classification and source discovery", () => {
  assert.equal(effortForTask("Build HellFire"), "low");
  assert.equal(effortForTask("Rewrite prose HellFire"), "low");
  for (const label of [
    "Read source HellFire",
    "Classify Ajax",
    "Find missing sources for Bessie",
  ])
    assert.equal(effortForTask(label), "medium");
});
test("agent preference is persisted and can change during a call without rewriting completed work", async (t) => {
  const s = setup(t),
    w = new Worker(
      s,
      fake(async () => ({ ok: true })),
    ),
    server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => server.close());
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  w.busy = true;
  let r = await fetch(base + "/api/settings", {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ agent: "codex" }),
  });
  assert.equal(r.status, 200);
  assert.equal((await r.json()).agent, "codex");
  r = await fetch(base + "/api/settings", {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ writingStyle: "changed" }),
  });
  assert.equal(r.status, 409);
  w.busy = false;
  r = await fetch(base + "/api/settings", {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ agent: "invalid" }),
  });
  assert.equal(r.status, 400);
  const state = JSON.parse(
    (s.db.prepare("SELECT value FROM meta WHERE key='project'").get() as any)
      .value,
  );
  assert.equal(state.settings.agent, "codex");
});

test("removed provider preferences migrate back to Grok without losing writing settings", () => {
  const dir = mkdtempSync(path.join(tmpdir(), "borderlens-agent-migration-"));
  let store = new Store(dir);
  try {
    (store.state.settings as any).agent = "ollama";
    store.state.settings.writingStyle = "Keep my editorial preference.";
    store.save();
    store.close();
    store = new Store(dir);
    assert.equal(store.state.settings.agent, "grok");
    assert.equal(
      store.state.settings.writingStyle,
      "Keep my editorial preference.",
    );
  } finally {
    store.close();
    rmSync(dir, { recursive: true, force: true });
  }
});

test("fallback errors and cooldown skips persist in the item's History", async (t) => {
  const s = setup(t);
  const { discover } = await import("../src/server/importer.ts");
  const f = discover(
    new Map([
      [
        "fixture",
        {
          id: "fixture",
          record_type: "object",
          path: "gd_weap_sniper.Title.Fixture",
          class: "WillowGame.WeaponNamePartDefinition",
          properties: { PartName: "Fixture" },
        },
      ],
    ]),
  )[0];
  s.state.families = [f];
  s.state.run.currentId = f.id;
  s.state.settings.agent = "codex";
  const router = new AgentRouter(s, {
    codex: fake(async () => {
      throw Error("Synthetic schema rejection");
    }),
    grok: fake(async () => ({ ok: true })),
  });
  await router.run("Build fixture", "evidence", shape, "", false, () => {});
  await router.run("Build fixture", "evidence", shape, "", false, () => {});
  assert.equal(f.history.length, 2);
  assert.match(
    f.history[0].message,
    /Codex failed: Synthetic schema rejection; switching to Grok/,
  );
  assert.match(
    f.history[1].message,
    /Codex temporarily unavailable until .*Synthetic schema rejection/,
  );
  const saved = JSON.parse(
    (s.db.prepare("select value from meta where key='project'").get() as any)
      .value,
  );
  assert.equal(saved.families[0].history.length, 2);
  const other = {
    ...structuredClone(f),
    id: "sync-context-fixture",
    history: [],
  };
  s.state.families.push(other);
  router.setItemContext(other.id);
  await router.run(
    "Sync item type for fixture",
    "saved evidence",
    shape,
    "",
    false,
    () => {},
  );
  router.setItemContext(null);
  assert.equal(f.history.length, 2);
  assert.equal(other.history.length, 1);
  assert.equal(s.state.run.currentId, f.id);
});

test("fixed nullable-root schema errors do not keep Codex in provider cooldown; real failures are retained", async (t) => {
  const s = setup(t),
    file = path.join(s.dir, "ai", "agent-failures.json"),
    at = new Date().toISOString(),
    until = Date.now() + 600000;
  writeFileSync(
    file,
    JSON.stringify({
      codex: {
        message:
          "Invalid schema for response_format 'codex_output_schema': schema must be a JSON Schema of type object, got type None.",
        at,
        until,
      },
      grok: { message: "Real capacity failure", at, until },
    }),
  );
  const router = new AgentRouter(s, {
    codex: fake(async () => ({ ok: true })),
    grok: fake(async () => ({ ok: true })),
  });
  const persisted = JSON.parse(readFileSync(file, "utf8"));
  assert(!persisted.codex);
  assert.equal(persisted.grok.message, "Real capacity failure");
  const original = readFileSync(file, "utf8");
  await assert.rejects(
    router.run(
      "Sync item name",
      "bad schema",
      shape.nullable(),
      "",
      false,
      () => {},
    ),
    /root must be an object/,
  );
  assert.equal(readFileSync(file, "utf8"), original);
});

test("fixed nested oneOf rejection clears only the affected provider cooldown", (t) => {
  const s = setup(t),
    file = path.join(s.dir, "ai", "agent-failures.json");
  const failure = { at: new Date().toISOString(), until: Date.now() + 600000 };
  writeFileSync(
    file,
    JSON.stringify({
      codex: {
        ...failure,
        message:
          "Invalid schema for response_format 'codex_output_schema': 'schema.properties.facts.items.properties.structured.anyOf.0.oneOf' is not permitted when strict is true.",
      },
      grok: { ...failure, message: "Real capacity failure" },
    }),
  );
  new AgentRouter(s, {});
  const persisted = JSON.parse(readFileSync(file, "utf8"));
  assert(!persisted.codex);
  assert.equal(persisted.grok.message, "Real capacity failure");
});
