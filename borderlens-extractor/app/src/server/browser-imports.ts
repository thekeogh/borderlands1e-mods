import { randomBytes, timingSafeEqual } from "node:crypto";
import { Store, HttpError, hash } from "./store.ts";
import type { Worker } from "./worker.ts";
import { sourceUrl } from "./research.ts";
import { providerForUrl, type ResearchReport, now } from "../shared/models.ts";
type Job = {
  id: string;
  tokenHash: string;
  familyId: string;
  name: string;
  url: string;
  expiresAt: number;
  status: "pending" | "queued" | "imported" | "failed";
  html?: string;
  capturedUrl?: string;
  message?: string;
};
export function articleKey(input: string) {
  try {
    const u = sourceUrl(input);
    if (
      u.hostname === "borderlands.fandom.com" &&
      !u.pathname.startsWith("/wiki/")
    )
      throw new Error("Open a wiki article URL.");
    return (
      u.origin +
      decodeURIComponent(u.pathname)
        .replace(/_/g, " ")
        .replace(/\/$/, "")
        .toLowerCase()
    );
  } catch (error: any) {
    throw new HttpError(400, error.message);
  }
}
export class BrowserImports {
  constructor(
    public store: Store,
    public worker: Worker,
  ) {}
  jobs(status?: string) {
    return (
      this.store.db
        .prepare(
          "SELECT value FROM artifacts WHERE family='_chrome' AND (? IS NULL OR json_extract(value,'$.status')=?)",
        )
        .all(status || null, status || null) as { value: string }[]
    ).map((row) => JSON.parse(row.value) as Job);
  }
  save(job: Job) {
    this.store.put("_chrome", job.id, job);
  }
  create(familyId: string, url: string) {
    const f = this.store.family(familyId);
    if (f.status === "excluded")
      throw new HttpError(400, "This item is excluded.");
    articleKey(url);
    if (
      this.jobs().filter(
        (j) =>
          (j.status === "pending" && j.expiresAt > Date.now()) ||
          j.status === "queued",
      ).length >= 20
    )
      throw new HttpError(
        409,
        "Too many pending captures. Finish an open import first.",
      );
    const token = randomBytes(32).toString("hex");
    const job: Job = {
      id: randomBytes(16).toString("hex"),
      tokenHash: hash(token),
      familyId,
      name: f.name,
      url: sourceUrl(url).href,
      expiresAt: Date.now() + 30 * 60 * 1000,
      status: "pending",
    };
    this.save(job);
    return {
      jobId: job.id,
      token,
      familyId,
      name: f.name,
      url: job.url,
      expiresAt: job.expiresAt,
    };
  }
  submit(input: { jobId: string; token: string; url: string; html: string }) {
    const job = this.store.get<Job>("_chrome", input.jobId);
    if (
      !job ||
      !timingSafeEqual(
        Buffer.from(job.tokenHash, "hex"),
        Buffer.from(hash(input.token), "hex"),
      )
    )
      throw new HttpError(
        403,
        "Capture ticket is invalid. Open this article from Borderlens again.",
      );
    if (job.status === "imported" || job.status === "queued")
      return this.public(job);
    if (job.expiresAt < Date.now())
      throw new HttpError(
        403,
        "Capture ticket expired. Open this article from Borderlens again.",
      );
    if (articleKey(input.url) !== articleKey(job.url))
      throw new HttpError(
        400,
        "This article is not the page requested for " +
          job.name +
          ". Reopen the requested source.",
      );
    const parsed = this.worker.research.parse(input.html);
    if (
      parsed.text.length < 60 ||
      /^(just a moment|access denied|attention required)/i.test(parsed.title)
    )
      throw new HttpError(
        400,
        "No readable article found. Wait for the article to finish loading, then send it again.",
      );
    job.status = "queued";
    job.html = input.html;
    job.capturedUrl = sourceUrl(input.url).href;
    this.save(job);
    if (!this.worker.busy) this.flush();
    this.store.save();
    return this.public(this.store.get<Job>("_chrome", job.id)!);
  }
  public(job: Job) {
    return {
      status: job.status,
      name: job.name,
      message:
        job.message ||
        (job.status === "queued"
          ? "Capture saved; applies after the current processing step."
          : "Source saved. Rebuild this item to use it."),
    };
  }
  flush() {
    for (const job of this.jobs("queued")) {
      try {
        const f = this.store.family(job.familyId);
        if (f.status === "excluded")
          throw new Error("Item was excluded before the import completed.");
        const source = this.worker.research.save(
          f,
          job.capturedUrl!,
          job.html!,
          true,
        );
        source.captureMethod = "chrome";
        this.store.db
          .prepare("UPDATE sources SET value=? WHERE id=?")
          .run(JSON.stringify(source), source.id);
        for (const old of this.store.sources(f.id))
          if (
            old.id !== source.id &&
            articleKey(old.url) === articleKey(source.url)
          )
            this.store.db.prepare("DELETE FROM sources WHERE id=?").run(old.id);
        if (!f.sourceUrls.includes(source.url))
          f.sourceUrls.unshift(source.url);
        const report = this.store.get<ResearchReport>(f.id, "research") || {
          discovered: [],
          providers: [],
        };
        const provider = providerForUrl(source.url)!;
        report.providers = report.providers.filter(
          (row) => row.provider !== provider,
        );
        report.providers.push({
          provider,
          status: "saved",
          urls: this.store
            .sources(f.id)
            .filter((s) => providerForUrl(s.url) === provider)
            .map((s) => s.url),
          message: "Captured from the article open in Chrome.",
          checkedAt: now(),
        });
        this.store.put(f.id, "research", report);
        this.worker.invalidate(f, "sources");
        const run = this.store.state.run;
        if (
          (this.worker.busy || run.status === "paused") &&
          !run.queue.slice(run.index).includes(f.id)
        )
          run.queue.push(f.id);
        this.worker.history(
          f,
          "Saved " + provider + " article from Chrome: " + source.url,
        );
        job.status = "imported";
        job.message =
          "Saved for " + f.name + ". Rebuild this item to use the new source.";
      } catch (error: any) {
        job.status = "failed";
        job.message = error.message;
      }
      delete job.html;
      this.save(job);
      this.store.save();
    }
  }
}
