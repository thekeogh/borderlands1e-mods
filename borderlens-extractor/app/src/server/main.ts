import path from "node:path";
import { fileURLToPath } from "node:url";
import express from "express";
import { api } from "./http.ts";
import { Store } from "./store.ts";
import { Worker } from "./worker.ts";
const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const dir = path.resolve(
  process.env.BORDERLENS_DATA_DIR || path.join(root, ".data"),
);
const store = new Store(dir),
  worker = new Worker(store),
  app = api(store, worker);
if (process.argv.includes("--production")) {
  app.use(express.static(path.join(root, "dist/client")));
  app.get("/{*path}", (_req, res) =>
    res.sendFile(path.join(root, "dist/client/index.html")),
  );
} else {
  const { createServer } = await import("vite");
  const vite = await createServer({
    root,
    server: { middlewareMode: true },
    appType: "spa",
  });
  app.use(vite.middlewares);
}
const port = Number(process.env.PORT || 4317);
const server = app.listen(port, "127.0.0.1", () =>
  console.log(
    `Borderlens workshop: http://127.0.0.1:${port}\nProject data: ${dir}`,
  ),
);
for (const signal of ["SIGTERM", "SIGINT"])
  process.once(signal, () => {
    worker.closed = true;
    if (store.state.run.status !== "idle") worker.pause();
    server.close();
    const poll = setInterval(() => {
      if (!worker.busy && !worker.coverageBusy) {
        clearInterval(poll);
        store.close();
        process.exit(0);
      }
    }, 200);
    setTimeout(() => process.exit(0), 10000).unref();
  });
