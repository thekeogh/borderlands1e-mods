import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, readFileSync, rmSync } from "node:fs";
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
