import type { Express } from "express";
import { z } from "zod";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { readFileSync } from "node:fs";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import AdmZip from "adm-zip";
import type { Worker } from "./worker.ts";
const folder = fileURLToPath(
  new URL("../../chrome-extension/", import.meta.url),
);
export function chromeRoutes(app: Express, worker: Worker) {
  app.get("/api/chrome-helper", (_req, res) =>
    res.json({
      version: "1.0.0",
      extensionPath: folder,
      chromeUrl: "chrome://extensions/",
      platform: process.platform,
    }),
  );
  app.post("/api/chrome-helper/open-extensions", async (_req, res) => {
    const command =
      process.platform === "darwin"
        ? (["open", ["-a", "Google Chrome", "chrome://extensions/"]] as const)
        : process.platform === "win32"
          ? ([
              "cmd",
              ["/c", "start", "", "chrome", "chrome://extensions/"],
            ] as const)
          : (["google-chrome", ["chrome://extensions/"]] as const);
    await promisify(execFile)(command[0], [...command[1]], { timeout: 10000 });
    res.json({ ok: true });
  });
  app.get("/api/chrome-helper/extension.zip", (_req, res) => {
    const zip = new AdmZip();
    for (const file of [
      "manifest.json",
      "bridge.js",
      "background.js",
      "popup.html",
      "popup.js",
      "popup.css",
      "README.md",
    ])
      zip.addFile(
        "borderlens-chrome-helper/" + file,
        readFileSync(path.join(folder, file)),
      );
    res
      .type("application/zip")
      .setHeader(
        "Content-Disposition",
        'attachment; filename="borderlens-chrome-helper.zip"',
      );
    res.send(zip.toBuffer());
  });
  app.post("/api/chrome-helper/jobs", (req, res) => {
    const body = z
      .object({ familyId: z.string().max(300), url: z.string().max(4000) })
      .strict()
      .parse(req.body);
    res.json(worker.browserImports.create(body.familyId, body.url));
  });
  app.post("/api/chrome-helper/capture", (req, res) => {
    const body = z
      .object({
        jobId: z.string().regex(/^[a-f0-9]{32}$/),
        token: z.string().regex(/^[a-f0-9]{64}$/),
        url: z.string().max(4000),
        html: z.string().min(60).max(5000000),
      })
      .strict()
      .parse(req.body);
    res.json(worker.browserImports.submit(body));
  });
}
