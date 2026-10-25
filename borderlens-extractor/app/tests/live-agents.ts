// Optional live subscription check: sends one tiny prompt, with automatic fallback.
import { mkdtempSync } from "node:fs";
import path from "node:path";
import assert from "node:assert/strict";
import { z } from "zod";
import { Store } from "../src/server/store.ts";
import { AgentRouter } from "../src/server/agents.ts";
const dir = mkdtempSync(path.resolve("../temp/agents-live-"));
const store = new Store(dir);
try {
  const router = new AgentRouter(store);
  const result = await router.run(
    "Rewrite prose connection check",
    'Return only the JSON object {"ok":true}. Do not use tools, web search, files or commands.',
    z.object({ ok: z.boolean() }).strict(),
    "",
    false,
    (message) => console.log(message),
  );
  assert.deepEqual(result, { ok: true });
  console.log(
    JSON.stringify({
      result,
      actualAgent: router.lastRun,
      artifactDirectory: dir,
    }),
  );
} finally {
  store.close();
}
