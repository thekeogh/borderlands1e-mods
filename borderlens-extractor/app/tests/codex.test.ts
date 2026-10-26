import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync,
  writeFileSync,
  readFileSync,
  rmSync,
  readdirSync,
  existsSync,
} from "node:fs";
import path from "node:path";
import { tmpdir } from "node:os";
import { z } from "zod";
import { CodexRunner } from "../src/server/codex.ts";

test("Codex subprocess uses ChatGPT login, strips API billing env, validates and caches structured output", async () => {
  const dir = mkdtempSync(path.join(tmpdir(), "borderlens-cli-"));
  const binary = path.join(dir, "fake-codex.cjs");
  const previous = {
    OPENAI_API_KEY: process.env.OPENAI_API_KEY,
    CODEX_API_KEY: process.env.CODEX_API_KEY,
    OPENAI_BASE_URL: process.env.OPENAI_BASE_URL,
  };
  try {
    writeFileSync(
      binary,
      `#!/usr/bin/env node
const fs=require('node:fs');const args=process.argv.slice(2);if(args[0]==='--version'){console.log('codex-cli fixture');process.exit(0);}if(args[0]==='login'){console.log('Logged in using ChatGPT');process.exit(0);}fs.writeFileSync(${JSON.stringify(path.join(dir, "invocation.json"))},JSON.stringify({args,apiKey:!!process.env.OPENAI_API_KEY,codexKey:!!process.env.CODEX_API_KEY,base:!!process.env.OPENAI_BASE_URL}));fs.writeFileSync(args[args.indexOf('--output-last-message')+1],JSON.stringify({ok:true}));console.log(JSON.stringify({type:'turn.started'}));process.stdin.resume();process.stdin.on('end',()=>process.exit(0));`,
      { mode: 0o700 },
    );
    process.env.OPENAI_API_KEY = "test-not-a-real-key";
    process.env.CODEX_API_KEY = "test-not-a-real-key";
    process.env.OPENAI_BASE_URL = "http://example.invalid";
    const runner = new CodexRunner(path.join(dir, "ai"), binary);
    const schema = z.object({ ok: z.boolean() }).strict();
    assert.deepEqual(
      await runner.run("test", "Evidence fixture", schema, "", false, () => {}),
      { ok: true },
    );
    const invocation = JSON.parse(
      readFileSync(path.join(dir, "invocation.json"), "utf8"),
    );
    assert.equal(invocation.apiKey, false);
    assert.equal(invocation.codexKey, false);
    assert.equal(invocation.base, false);
    assert.ok(invocation.args.includes("--ignore-user-config"));
    assert.ok(invocation.args.includes("read-only"));
    assert.ok(invocation.args.includes("--output-schema"));
    rmSync(binary);
    assert.deepEqual(
      await runner.run("test", "Evidence fixture", schema, "", false, () => {}),
      { ok: true },
    );
  } finally {
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
    rmSync(dir, { recursive: true, force: true });
  }
});

test("quiet live Codex calls report elapsed/silence and enforce the timeout; events remain inspectable mid-call", async () => {
  const dir = mkdtempSync(path.join(tmpdir(), "borderlens-cli-live-")),
    binary = path.join(dir, "fake-codex.cjs");
  try {
    writeFileSync(
      binary,
      `#!/usr/bin/env node
const fs=require('node:fs'),a=process.argv.slice(2);if(a[0]==='--version'){console.log('fixture');process.exit(0)}if(a[0]==='login'){console.log('Logged in using ChatGPT');process.exit(0)}console.log(JSON.stringify({type:'turn.started'}));setInterval(()=>{},1000);`,
      { mode: 0o700 },
    );
    const messages: string[] = [];
    const runner = new CodexRunner(path.join(dir, "ai"), binary, {
      timeoutMs: 800,
      heartbeatMs: 80,
    });
    let sawLive = false;
    await assert.rejects(
      runner.run(
        "quiet fixture",
        "fixture",
        z.object({ ok: z.boolean() }).strict(),
        "",
        false,
        (message) => {
          messages.push(message);
          if (message.includes("last output")) {
            const folders = readdirSync(path.join(dir, "ai"));
            const file = path.join(dir, "ai", folders[0], "activity.json");
            if (existsSync(file)) {
              const state = JSON.parse(readFileSync(file, "utf8"));
              assert.equal(state.state, "running");
              assert.ok(state.pid);
              sawLive = true;
            }
          }
        },
      ),
      /timed out/,
    );
    assert.ok(sawLive);
    assert.ok(messages.filter((m) => m.includes("last output")).length > 1);
    const cache = path.join(dir, "ai", readdirSync(path.join(dir, "ai"))[0]);
    assert.equal(
      JSON.parse(readFileSync(path.join(cache, "activity.json"), "utf8")).state,
      "failed",
    );
    assert.match(
      readFileSync(path.join(cache, "events.jsonl"), "utf8"),
      /turn.started/,
    );
    const count = messages.length;
    await new Promise((r) => setTimeout(r, 120));
    assert.equal(messages.length, count);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
test("Codex crashes fail promptly and retain the process error", async () => {
  const dir = mkdtempSync(path.join(tmpdir(), "borderlens-cli-crash-")),
    binary = path.join(dir, "fake-codex.cjs");
  try {
    writeFileSync(
      binary,
      `#!/usr/bin/env node
const a=process.argv.slice(2);if(a[0]==='--version'){console.log('fixture');process.exit(0)}if(a[0]==='login'){console.log('Logged in using ChatGPT');process.exit(0)}console.log(JSON.stringify({type:'turn.failed',error:{message:'fixture process failure'}}));process.exit(1);`,
      { mode: 0o700 },
    );
    await assert.rejects(
      new CodexRunner(path.join(dir, "ai"), binary).run(
        "crash",
        "fixture",
        z.object({ ok: z.boolean() }).strict(),
        "",
        false,
        () => {},
      ),
      /fixture process failure/,
    );
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("writer schema includes every structured-output key, including nullable character", async () => {
  const { WriterDraft, PublicEntry } = await import("../src/shared/models.ts");
  const schema = z.toJSONSchema(WriterDraft, { target: "draft-7" }) as any;
  const visit = (node: any) => {
    if (!node || typeof node !== "object") return;
    if (node.properties)
      assert.deepEqual(
        new Set(node.required),
        new Set(Object.keys(node.properties)),
      );
    for (const value of Object.values(node))
      if (Array.isArray(value)) value.forEach(visit);
      else visit(value);
  };
  visit(schema);
  assert.ok(schema.properties.entry.required.includes("character"));
  assert.ok(PublicEntry.shape.character.safeParse(undefined).success);
  assert.ok(WriterDraft.shape.entry.shape.character.safeParse(null).success);
});

test("sync name uses an object-root schema for both nullable outcomes; invalid roots fail locally before any CLI call", async () => {
  const { NameSyncResponse } = await import("../src/shared/identity-sync.ts");
  const { agentOutputSchema } = await import("../src/shared/agent-schema.ts");
  const json = agentOutputSchema(NameSyncResponse) as any;
  assert.equal(json.type, "object");
  assert(!json.anyOf);
  assert.deepEqual(json.required, ["decision"]);
  assert.deepEqual(NameSyncResponse.parse({ decision: null }), {
    decision: null,
  });
  const dir = mkdtempSync(path.join(tmpdir(), "bad-root-"));
  try {
    const runner = new CodexRunner(dir, path.join(dir, "must-not-run"));
    await assert.rejects(
      runner.run(
        "Sync item name",
        "fixture",
        z.object({ ok: z.boolean() }).nullable(),
        "",
        false,
        () => {},
      ),
      /root must be an object/,
    );
    assert.deepEqual(readdirSync(dir), []);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
