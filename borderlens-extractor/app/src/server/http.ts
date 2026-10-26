import { gameData } from "./game-data.ts";
import { EvidenceScope } from "../shared/evidence-scopes.ts";
import { sourceKey } from "../shared/research.ts";
import { sourceUrl } from "./research.ts";
import { savedSourceCache } from "./source-cache.ts";
import { ImagePath } from "../shared/images.ts";
import { chromeRoutes } from "./chrome-http.ts";
import { websiteZip, websiteEntry } from "./website-export.ts";
import { weaponTypes } from "../shared/taxonomy.ts";
import express from "express";
import multer from "multer";
import { z } from "zod";
import { Store, HttpError, hash } from "./store.ts";
import { Worker } from "./worker.ts";
import { compareCoverage } from "./research.ts";
import { importZip } from "./importer.ts";
import { PublicEntry, PartDefinition, now } from "../shared/models.ts";
import { mkdirSync, rmSync, readFileSync } from "node:fs";
import path from "node:path";
export function api(store: Store, worker: Worker) {
  const app = express();
  app.disable("x-powered-by");
  app.use((req, res, next) => {
    const host = req.headers.host || "";
    if (!/^(localhost|127\.0\.0\.1)(:\d+)?$/.test(host))
      return res.status(403).json({ error: "Local access only." });
    const origin = req.headers.origin;
    if (origin && origin !== `http://${host}`)
      return res
        .status(403)
        .json({ error: "Cross-origin requests are not allowed." });
    res.setHeader("X-Content-Type-Options", "nosniff");
    next();
  });
  app.use(express.json({ limit: "6mb" }));
  chromeRoutes(app, worker);
  const scopeDetail = (owner: ReturnType<Store["ensureScope"]>) => ({
    family: owner,
    sources: store.sources(owner.id),
    excludedSources: store.sourceExclusions(owner.id),
    children: store.scopeChildren(owner).length,
  });
  app.get("/api/shared-sources", (_req, res) =>
    res.json((store.state.sharedScopes || []).map(scopeDetail)),
  );
  app.post("/api/shared-sources", (req, res) => {
    const body = z
      .object({
        scope: EvidenceScope,
        url: z.string().max(4000).optional(),
        html: z.string().max(5000000).optional(),
        remove: z.boolean().optional(),
      })
      .strict()
      .parse(req.body);
    if (body.html && !body.url)
      throw new HttpError(400, "HTML requires its original article URL.");
    if (body.url) {
      try {
        sourceUrl(body.url);
      } catch (error: any) {
        throw new HttpError(400, error.message);
      }
    }
    if (body.html && worker.research.parse(body.html).text.length < 60)
      throw new HttpError(400, "Source has too little readable content.");
    const owner = store.ensureScope(body.scope);
    if (body.url) {
      if (
        worker.evidenceOwnerIsBusy(owner) ||
        (body.html && worker.sharedArticleIsBusy(body.url))
      )
        throw new HttpError(
          409,
          "Pause processing before changing shared evidence used by the current item.",
        );
      const key = sourceKey(body.url),
        exists = owner.sourceUrls.some((url) => sourceKey(url) === key);
      if (body.remove) {
        if (!store.isSourceExcluded(owner.id, body.url)) {
          const source = store
            .sources(owner.id)
            .find((source) => sourceKey(source.url) === key);
          store.put(owner.id, "sourceExclusions", [
            ...store.sourceExclusions(owner.id),
            {
              sourceId: source?.id || "url:" + hash(key).slice(0, 20),
              url: body.url,
              title: source?.title || body.url,
              excludedAt: now(),
            },
          ]);
        }
        owner.sourceUrls = owner.sourceUrls.filter(
          (url) => sourceKey(url) !== key,
        );
      } else {
        if (!exists) owner.sourceUrls.push(body.url);
        store.put(
          owner.id,
          "sourceExclusions",
          store
            .sourceExclusions(owner.id)
            .filter((row) => sourceKey(row.url) !== key),
        );
        if (body.html) worker.research.save(owner, body.url, body.html, true);
      }
      if (body.html) worker.sharedArticleChanged(owner, body.url);
      else if (body.remove || !exists) worker.invalidate(owner, "evidence");
      store.save();
    }
    res.json(scopeDetail(owner));
  });
  app.get("/api/state", (_req, res) => {
    store.syncClassifications();
    res.json(store.state);
  });
  app.get("/api/sources/:id/html", (req, res) => {
    const source = store.source(req.params.id);
    if (!source) throw new HttpError(404, "Saved source not found.");
    const root = path.resolve(store.dir, "sources"),
      filename = path.resolve(root, source.filename);
    if (path.dirname(filename) !== root)
      throw new HttpError(400, "Invalid cached source filename.");
    let html: Buffer;
    try {
      html = readFileSync(filename);
    } catch (error: any) {
      if (error.code === "ENOENT")
        throw new HttpError(
          404,
          "Cached HTML file is missing. The saved text is still available.",
        );
      throw error;
    }
    res.setHeader("Cache-Control", "no-store");
    res.setHeader("Content-Security-Policy", "default-src 'none'; sandbox");
    res.type("text/plain; charset=utf-8").send(html);
  });
  app.get("/api/events", (req, res) => {
    res.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    });
    res.write(`data: ${store.state.revision}\n\n`);
    const listener = (n: number) => res.write(`data: ${n}\n\n`);
    store.on("change", listener);
    const t = setInterval(() => res.write(": alive\n\n"), 20000);
    req.on("close", () => {
      clearInterval(t);
      store.off("change", listener);
    });
  });
  app.post(
    "/api/import",
    multer({
      storage: multer.memoryStorage(),
      limits: { fileSize: 70 * 1024 * 1024, files: 1 },
    }).single("file"),
    (req, res) => {
      if (!req.file) throw new HttpError(400, "Choose an extractor ZIP.");
      const result = importZip(store, req.file.buffer, req.file.originalname);
      worker.refreshImported();
      res.json(result);
    },
  );
  app.get("/api/images", (_req, res) => {
    res.setHeader("Cache-Control", "no-store");
    store.syncClassifications();
    res.json(store.images.coverage(store.state.families));
  });
  app.get("/api/images/file/:folder/:filename", (req, res) => {
    const file = store.images.file(
      req.params.folder + "/" + req.params.filename,
    );
    if (!file) throw new HttpError(404, "Image not found.");
    res.sendFile(file, { headers: { "Cache-Control": "no-cache" } });
  });
  app.post("/api/items/:id/image", (req, res) => {
    const f = store.family(req.params.id);
    const body = z
      .object({
        image: ImagePath.nullable().optional(),
        automatic: z.boolean().optional(),
      })
      .strict()
      .parse(req.body);
    if (!body.automatic && body.image === undefined)
      throw new HttpError(400, "Choose an image or automatic matching.");
    try {
      store.images.set(f.id, body.image ?? null, body.automatic);
    } catch (error: any) {
      throw new HttpError(400, error.message);
    }
    f.revision++;
    f.updatedAt = now();
    store.save();
    res.json(store.images.match(f));
  });
  app.get("/api/items/:id/game-data", (req, res) => {
    res.setHeader("Cache-Control", "no-store");
    res.json(gameData(store, req.params.id));
  });
  app.get("/api/items/:id", (req, res) => {
    store.syncClassifications();
    const f = store.family(req.params.id);
    res.json({
      finalValidation: store.get(f.id, "finalValidation"),
      savedRebuild: (({ available, reason }) => ({ available, reason }))(
        savedSourceCache(store, f),
      ),
      image: (store.images.refresh(), store.images.match(f)),
      family: f,
      packet: store.get(f.id, "packet"),
      draft: store.get(f.id, "draft"),
      output: store.get(f.id, "output"),
      websiteOutput: websiteEntry(store, f),
      provenance: store.get(f.id, "provenance"),
      matches: store.get(f.id, "matches"),
      research: store.get(f.id, "research"),
      sources: store.sources(f.id),
      inheritedEvidence: store.inheritedEvidence(f),
      excludedSources: store.sourceExclusions(f.id),
      parts: store.get(f.id, "parts") || [],
      researchAudit: store.get(f.id, "researchAudit"),
      classification: store.classifications.data.entries[f.id] || null,
    });
  });
  app.post("/api/items/:id/action", async (req, res) => {
    const body = z
      .object({
        action: z.enum([
          "rebuild",
          "rebuild-saved",
          "rebuild-fresh",
          "discover",
          "from",
          "refresh",
          "retry",
          "exclude",
          "remove",
          "restore",
          "exclude-source",
          "restore-source",
          "resolve",
          "classification",
          "save-output",
        ]),
        url: z.string().max(4000).optional(),
        html: z.string().max(5000000).optional(),
        notes: z.string().max(10000).optional(),
        sourceId: z.string().max(200).optional(),
        gameOnly: z.boolean().optional(),
        output: z.unknown().optional(),
        weaponType: z.enum(weaponTypes).nullable().optional(),
      })
      .strict()
      .parse(req.body);
    await worker.action(req.params.id, body.action, body);
    res.json({ ok: true });
  });
  app.post("/api/groups/run", (req, res) => {
    const { scope, action } = z
      .object({
        scope: EvidenceScope,
        action: z.enum(["rebuild-saved", "rebuild-fresh", "discover"]),
      })
      .strict()
      .parse(req.body);
    if (worker.busy)
      throw new HttpError(
        409,
        "Pause the current job before starting a group batch.",
      );
    worker.start(
      undefined,
      undefined,
      action === "discover"
        ? "auto"
        : action === "rebuild-fresh"
          ? "fresh"
          : "saved",
      action === "discover" ? "discover" : "build",
      scope,
    );
    res.json(store.state.run);
  });
  app.post("/api/run", (req, res) => {
    const { action, sourceMode } = z
      .object({
        action: z.enum([
          "start",
          "pause",
          "resume",
          "discover",
          "resume-build",
        ]),
        sourceMode: z.enum(["saved", "fresh"]).optional(),
      })
      .strict()
      .refine(
        (body) => body.action === "start" || body.sourceMode === undefined,
        "Choose a source mode only when starting a batch.",
      )
      .parse(req.body);
    if (["start", "discover", "resume-build"].includes(action) && worker.busy)
      throw new HttpError(
        409,
        "Pause the current run before starting a new batch.",
      );
    if (action === "pause") worker.pause();
    else if (action === "resume") worker.resume();
    else if (action === "resume-build") worker.resumeBuild();
    else if (action === "discover")
      worker.start(undefined, undefined, "auto", "discover");
    else worker.start(undefined, undefined, sourceMode || "saved");
    res.json(store.state.run);
  });
  app.post("/api/coverage", (_req, res) => {
    if (worker.coverageBusy)
      throw new HttpError(409, "Coverage scan already running.");
    void worker.coverage();
    res.json({ ok: true });
  });
  app.post("/api/coverage/:key", (req, res) => {
    if (worker.coverageBusy || worker.busy)
      throw new HttpError(
        409,
        "Pause processing and wait for coverage to finish first.",
      );
    const body = z
      .object({
        action: z.enum(["link", "exclude"]),
        familyId: z.string().optional(),
      })
      .parse(req.body);
    const entry = store.state.coverage.entries.find(
      (e) => e.key === req.params.key,
    );
    if (!entry) throw new HttpError(404, "Coverage candidate not found.");
    const corrections =
      store.get<Record<string, { action: string; familyId?: string }>>(
        "_project",
        "coverageCorrections",
      ) || {};
    if (body.action === "link") {
      if (!body.familyId)
        throw new HttpError(400, "Choose an extracted family.");
      const f = store.family(body.familyId);
      if (!f.aliases.includes(entry.name)) f.aliases.push(entry.name);
    }
    corrections[entry.key] = body;
    store.put("_project", "coverageCorrections", corrections);
    worker.reconcileCoverage();
    store.save();
    res.json({ ok: true });
  });
  app.patch("/api/settings", (req, res) => {
    const body = z
      .object({
        agent: z.enum(["grok", "codex"]).optional(),
        model: z.string().max(100).optional(),
        writingStyle: z.string().max(4000).optional(),
        research: z.boolean().optional(),
        maxItems: z.number().int().min(1).max(10000).optional(),
      })
      .strict()
      .parse(req.body);
    if (worker.busy && Object.keys(body).some((key) => key !== "agent"))
      throw new HttpError(
        409,
        "Pause processing before changing settings other than the default agent.",
      );
    const prev = store.state.settings;
    const invalidate =
      (body.model !== undefined && body.model !== prev.model) ||
      (body.writingStyle !== undefined &&
        body.writingStyle !== prev.writingStyle) ||
      (body.research !== undefined && body.research !== prev.research);
    Object.assign(prev, body);
    if (invalidate)
      for (const f of store.state.families)
        if (f.status !== "excluded" && !f.manualOutput)
          worker.invalidate(
            f,
            body.research !== undefined ? "sources" : "draft",
          );
    store.save();
    res.json(prev);
  });
  app.get("/api/codex", async (_req, res) =>
    res.json(await worker.ai.status("codex")),
  );
  app.get("/api/agents", async (_req, res) =>
    res.json(await worker.ai.status()),
  );
  app.post("/api/agents/recheck", async (_req, res) => {
    worker.ai.resetFailures?.();
    res.json(await worker.ai.status());
  });
  app.get("/api/export", (_req, res) => {
    store.syncClassifications();
    const zip = websiteZip(store);
    res.setHeader("Content-Type", "application/zip");
    res.setHeader(
      "Content-Disposition",
      'attachment; filename="borderlens-catalogue.zip"',
    );
    res.send(zip);
  });
  app.post("/api/reset", (req, res) => {
    if (worker.busy || worker.coverageBusy)
      throw new HttpError(
        409,
        "Pause processing and wait for coverage to finish first.",
      );
    const body = z
      .object({
        scope: z.enum(["generated", "all"]),
        confirmation: z.literal("RESET"),
      })
      .strict()
      .parse(req.body);
    if (body.scope === "all") {
      store.db.exec(
        "DELETE FROM raw; DELETE FROM artifacts; DELETE FROM sources;",
      );
      store.classifications.clear();
      store.images.clear();
      store.state = initial();
      store.reloadRecords();
      for (const dir of ["captures", "sources", "ai", "exports"]) {
        rmSync(path.join(store.dir, dir), { recursive: true, force: true });
        mkdirSync(path.join(store.dir, dir), { recursive: true });
      }
      worker.research.robots.clear();
    } else {
      for (const f of store.state.families) {
        if (f.manualOutput) continue;
        store.forget(f.id, [
          "packet",
          "draft",
          "matches",
          "output",
          "validatedPacket",
          "provenance",
        ]);
        f.stage = "evidence";
        if (f.status !== "excluded") f.status = "queued";
        f.issue = null;
      }
      delete store.state.buildCheckpoint;
      store.state.run = {
        sourceMode: "saved",
        sourcePrepared: [],
        status: "idle",
        queue: [],
        index: 0,
        currentId: null,
        message: "Processing reset; research and corrections retained.",
        startedAt: null,
        deferred: [],
        pendingFrom: null,
        pauseRequested: false,
      };
    }
    store.save();
    res.json({
      ok: true,
      note:
        body.scope === "all"
          ? "Project and cached files cleared."
          : "Generated entries reset; research and corrections retained.",
    });
  });
  app.use("/api", (_req, res) =>
    res.status(404).json({ error: "Unknown API operation." }),
  );
  app.use(
    (
      error: any,
      _req: express.Request,
      res: express.Response,
      _next: express.NextFunction,
    ) => {
      const status =
        error.status === 413
          ? 413
          : error instanceof HttpError
            ? error.status
            : error instanceof z.ZodError ||
                error instanceof multer.MulterError ||
                error.type === "entity.parse.failed"
              ? 400
              : 500;
      res.status(status).json({
        error:
          error instanceof z.ZodError
            ? error.issues
                .map((i) => i.path.join(".") + ": " + i.message)
                .join("; ")
            : String(error.message || error),
      });
    },
  );
  return app;
}
import { initial } from "../shared/models.ts";
