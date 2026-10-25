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
import { tmpdir } from "node:os";
import path from "node:path";
import { z } from "zod";
import { GrokRunner } from "../src/server/grok.ts";
import { CodexRunner } from "../src/server/codex.ts";
import { AgentRouter } from "../src/server/agents.ts";
import { Store } from "../src/server/store.ts";
const schema = z.object({ ok: z.boolean() }).strict();
function fixture(dir: string, mode = "success") {
  const binary = path.join(dir, "fake-grok.cjs"),
    log = path.join(dir, "invocations.jsonl"),
    pid = path.join(dir, "grok.pid");
  writeFileSync(
    binary,
    `#!/usr/bin/env node
const fs=require('node:fs'),a=process.argv.slice(2);if(a[0]==='--version'){console.log('fixture');process.exit(0)}if(a[0]==='models'){console.log('You are logged in with grok.com. Available models: grok-4.6');process.exit(0)}if(a[0]==='login'){console.log('Logged in using ChatGPT');process.exit(0)}fs.appendFileSync(${JSON.stringify(log)},JSON.stringify({args:a,xai:!!process.env.XAI_API_KEY,openai:!!process.env.OPENAI_API_KEY})+'\\n');
if(a.includes('--prompt-file')){fs.writeFileSync(${JSON.stringify(pid)},String(process.pid));
if(${JSON.stringify(mode)}==='hang'){setInterval(()=>{},1000);return;}
if(${JSON.stringify(mode)}==='privacy'){console.log(JSON.stringify({type:'result',subtype:'error_during_execution',is_error:true,errors:['Grok Build is not supported in Legacy (no storage). Switch to Privacy Mode.']}));process.exit(1)}
console.log(JSON.stringify({type:'system',apiKeySource:'oauth',model:'grok-4.6'}));console.log(JSON.stringify({type:'result',subtype:'success',is_error:false,stop_reason:'end_turn',structured_output:{ok:true}}));
}else{const p=Number(fs.readFileSync(${JSON.stringify(pid)},'utf8'));try{process.kill(p,0);console.error('previous agent still alive');process.exit(9)}catch{}fs.writeFileSync(a[a.indexOf('--output-last-message')+1],JSON.stringify({ok:true}));}
`,
    { mode: 0o700 },
  );
  return { binary, log, pid };
}
test("Grok pins 4.6, uses subscription auth, effort, schema, prompt files, restrictions and provider cache", async () => {
  const dir = mkdtempSync(path.join(tmpdir(), "borderlens-grok-")),
    { binary, log } = fixture(dir),
    old = process.env.XAI_API_KEY;
  try {
    process.env.XAI_API_KEY = "not-a-real-test-key";
    const r = new GrokRunner(path.join(dir, "ai"), binary);
    assert.deepEqual(
      await r.run(
        "Build fixture",
        "Evidence",
        schema,
        "gpt-ignore",
        false,
        () => {},
      ),
      { ok: true },
    );
    let calls = readFileSync(log, "utf8")
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line));
    assert.equal(calls.length, 1);
    assert.equal(calls[0].xai, false);
    assert.equal(calls[0].openai, false);
    const a = calls[0].args;
    assert.equal(a[a.indexOf("--model") + 1], "grok-4.6");
    assert.equal(a[a.indexOf("--reasoning-effort") + 1], "low");
    assert.ok(a.includes("--json-schema"));
    assert.ok(a.includes("read-only"));
    assert.ok(a.includes("--no-subagents"));
    assert.ok(a.includes("--disable-web-search"));
    assert.ok(a.includes("MCPTool(*)"));
    assert.equal(
      readFileSync(a[a.indexOf("--prompt-file") + 1], "utf8"),
      "Evidence",
    );
    await r.run("Read source fixture", "Evidence", schema, "", false, () => {});
    calls = readFileSync(log, "utf8")
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line));
    assert.equal(
      calls[1].args[calls[1].args.indexOf("--reasoning-effort") + 1],
      "medium",
    );
    await r.run(
      "Find missing sources for fixture",
      "Evidence",
      schema,
      "",
      true,
      () => {},
    );
    calls = readFileSync(log, "utf8")
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line));
    assert.equal(calls[2].args[calls[2].args.indexOf("--max-turns") + 1], "6");
    assert.ok(!calls[2].args.includes("--disable-web-search"));
    assert.equal(
      calls[2].args[calls[2].args.indexOf("--tools") + 1],
      "web_search,web_fetch",
    );
    rmSync(binary);
    await r.run(
      "Build fixture",
      "Evidence",
      schema,
      "gpt-ignore",
      false,
      () => {},
    );
    assert.equal(r.lastRun?.cached, true);
    assert.equal(readdirSync(path.join(dir, "ai")).length, 3);
  } finally {
    if (old === undefined) delete process.env.XAI_API_KEY;
    else process.env.XAI_API_KEY = old;
    rmSync(dir, { recursive: true, force: true });
  }
});
test("a timed-out Grok process is gone before Codex fallback starts", async () => {
  const dir = mkdtempSync(path.join(tmpdir(), "borderlens-failover-")),
    { binary, pid } = fixture(dir, "hang"),
    s = new Store(path.join(dir, "project"));
  try {
    const router = new AgentRouter(s, {
      grok: new GrokRunner(path.join(dir, "grok"), binary, {
        timeoutMs: 250,
        heartbeatMs: 50,
      }),
      codex: new CodexRunner(path.join(dir, "codex"), binary, {
        timeoutMs: 1000,
      }),
    });
    const messages: string[] = [];
    assert.deepEqual(
      await router.run("Build fixture", "Evidence", schema, "", false, (m) =>
        messages.push(m),
      ),
      { ok: true },
    );
    const child = Number(readFileSync(pid, "utf8"));
    assert.throws(() => process.kill(child, 0));
    assert.ok(messages.some((m) => m.includes("switching to Codex")));
    assert.equal(router.lastRun?.agent, "codex");
    assert.equal(router.lastRun?.fallbackFrom, "grok");
  } finally {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  }
});
test("Grok account errors retain the actionable privacy-mode reason and do not become cached successes", async () => {
  const dir = mkdtempSync(path.join(tmpdir(), "borderlens-grok-privacy-")),
    { binary } = fixture(dir, "privacy");
  try {
    const r = new GrokRunner(path.join(dir, "ai"), binary);
    await assert.rejects(
      r.run("Build fixture", "Evidence", schema, "", false, () => {}),
      /Switch to Privacy Mode/,
    );
    const cache = path.join(dir, "ai", readdirSync(path.join(dir, "ai"))[0]);
    assert.equal(existsSync(path.join(cache, "validated.json")), false);
    assert.equal(
      JSON.parse(readFileSync(path.join(cache, "activity.json"), "utf8")).state,
      "failed",
    );
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
