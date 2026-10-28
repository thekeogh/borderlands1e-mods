import type { Express } from "express";
import multer from "multer";
import { tmpdir } from "node:os";
import { rmSync } from "node:fs";
import { BackupUI } from "../shared/project-backup.ts";
import {
  exportProject,
  importProject,
  requireBackupIdle,
} from "./project-backup.ts";
import { HttpError } from "./store.ts";
import type { Worker } from "./worker.ts";
export function backupRoutes(app: Express, worker: Worker) {
  app.post("/api/project-backup/export", (req, res) => {
    const result = exportProject(worker, BackupUI.parse(req.body));
    res
      .type("application/zip")
      .setHeader(
        "Content-Disposition",
        `attachment; filename="${result.filename}"`,
      );
    res.send(result.buffer);
  });
  const upload = multer({
    dest: tmpdir(),
    limits: { fileSize: 1024 ** 3, files: 1 },
  });
  app.post(
    "/api/project-backup/import",
    (_req, _res, next) => {
      requireBackupIdle(worker);
      next();
    },
    (req, res, next) =>
      upload.single("backup")(req, res, (error) =>
        next(
          error?.code === "LIMIT_FILE_SIZE"
            ? new HttpError(413, "Backup ZIP exceeds the 1 GB upload limit.")
            : error,
        ),
      ),
    (req, res) => {
      if (!req.file)
        throw new HttpError(
          400,
          "Select a complete Borderlens project backup ZIP.",
        );
      try {
        res.json(importProject(worker, req.file.path));
      } finally {
        rmSync(req.file.path, { force: true });
      }
    },
  );
}
