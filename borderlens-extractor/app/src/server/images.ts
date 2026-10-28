import {
  existsSync,
  readFileSync,
  readdirSync,
  realpathSync,
  statSync,
  writeFileSync,
  renameSync,
  mkdirSync,
} from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { z } from "zod";
import type { Family } from "../shared/models.ts";
import { categoryFolders, itemSlug } from "../shared/website.ts";
import {
  ImagePath,
  type ImageMatch,
  type ImageCoverage,
} from "../shared/images.ts";
const Overrides = z
  .object({
    schemaVersion: z.literal(1),
    entries: z.record(z.string(), ImagePath.nullable()),
  })
  .strict();
const normalized = (name: string) => itemSlug(name).replace(/-/g, "");
export const defaultImageRoot = fileURLToPath(
  new URL("../../img/borderlands/", import.meta.url),
);
/** Images are filesystem-owned, never selected/invented by the writing model. */
export class Images {
  files: string[] = [];
  private entries: Record<string, string | null> = {};
  private stamp = "";
  private paths = new Map<string, string>();
  get roots() {
    return [...new Set([this.root, this.localRoot])];
  }
  constructor(
    public root: string,
    public overridesFile: string,
    public localRoot = root,
  ) {
    this.refresh();
  }
  refresh() {
    const files: string[] = [],
      stamps: unknown[] = [];
    this.paths.clear();
    for (const library of this.roots) {
      if (!existsSync(library)) continue;
      const root = realpathSync(library);
      const scan = (dir: string, prefix = "") => {
        for (const entry of readdirSync(dir, { withFileTypes: true })) {
          if (entry.name.startsWith(".")) continue;
          const relative = prefix + entry.name;
          const full = path.join(dir, entry.name);
          // Do not follow symlinks, including directory links outside the library.
          if (entry.isDirectory()) scan(full, relative + "/");
          else if (entry.isFile() && ImagePath.safeParse(relative).success) {
            const resolved = realpathSync(full);
            if (
              !resolved.startsWith(root + path.sep) ||
              this.paths.has(relative)
            )
              continue;
            const stat = statSync(resolved);
            this.paths.set(relative, resolved);
            files.push(relative);
            stamps.push([relative, resolved, stat.size, stat.mtimeMs]);
          }
        }
      };
      scan(root);
    }
    this.files = files.sort();
    this.entries = existsSync(this.overridesFile)
      ? Overrides.parse(JSON.parse(readFileSync(this.overridesFile, "utf8")))
          .entries
      : {};
    this.stamp = JSON.stringify([stamps.sort(), this.entries]);
  }
  match(
    f: Pick<Family, "id" | "name" | "category" | "aliases" | "character"> &
      Partial<Pick<Family, "nameOverride" | "rawName">>,
  ): ImageMatch {
    if (f.nameOverride?.origin === "manual")
      f = {
        ...f,
        name: f.nameOverride.identityName || f.nameOverride.originalName,
        aliases: f.nameOverride.identityAliases || [
          f.nameOverride.originalName,
        ],
      };
    if (Object.hasOwn(this.entries, f.id)) {
      const image = this.entries[f.id];
      return {
        image: image && this.files.includes(image) ? image : null,
        method:
          image === null || !this.files.includes(image) ? "missing" : "manual",
        candidates: image ? [image] : [],
      };
    }
    const folder = categoryFolders[f.category],
      local = this.files.filter(
        (file) =>
          file.startsWith(folder + "/") ||
          (f.category === "Artifacts" && file.startsWith("artifact/")),
      );
    const stem = (file: string) => path.basename(file, path.extname(file));
    const shortName =
      f.category === "Artifacts" ? f.name.replace(/\s+artifact$/i, "") : f.name;
    const choose = (
      matches: string[],
      method: ImageMatch["method"],
    ): ImageMatch | undefined =>
      matches.length
        ? {
            image: matches.length === 1 ? matches[0] : null,
            method: matches.length === 1 ? method : "ambiguous",
            candidates: matches,
          }
        : undefined;
    if (f.character) {
      for (const name of new Set([f.name, shortName])) {
        const specific = choose(
          local.filter((file) =>
            [f.character + " " + name, name + " " + f.character].some(
              (candidate) => normalized(candidate) === normalized(stem(file)),
            ),
          ),
          "normalized",
        );
        if (specific) return specific;
      }
    }
    const exact = choose(
      local.filter((file) => stem(file) === itemSlug(f.name)),
      "exact",
    );
    if (exact) return exact;
    const byName = choose(
      local.filter((file) => normalized(stem(file)) === normalized(f.name)),
      "normalized",
    );
    if (byName) return byName;
    const byAlias = choose(
      local.filter((file) =>
        f.aliases.some((alias) => normalized(alias) === normalized(stem(file))),
      ),
      "alias",
    );
    if (byAlias) return byAlias;
    if (shortName !== f.name) {
      const shortened = choose(
        local.filter(
          (file) => normalized(stem(file)) === normalized(shortName),
        ),
        "normalized",
      );
      if (shortened) return shortened;
    }
    // Unclassified equipment can have a uniquely named image in a known folder.
    if (f.category === "Other equipment") {
      const matches = this.files.filter((file) =>
        [f.name, ...f.aliases].some(
          (name) => normalized(name) === normalized(stem(file)),
        ),
      );
      const fallback = choose(matches, "normalized");
      if (fallback) return fallback;
    }
    return { image: null, method: "missing", candidates: [] };
  }
  coverage(families: Family[]): ImageCoverage {
    this.refresh();
    const items = families
      .filter((f) => f.status !== "excluded")
      .map((f) => ({
        id: f.id,
        name: f.name,
        category: f.category,
        ...this.match(f),
      }));
    return {
      files: this.files,
      items,
      revision: createHash("sha256")
        .update(this.stamp + JSON.stringify(items))
        .digest("hex")
        .slice(0, 16),
      summary: {
        total: items.length,
        matched: items.filter((i) => i.image).length,
        missing: items.filter((i) => i.method === "missing").length,
        ambiguous: items.filter((i) => i.method === "ambiguous").length,
      },
    };
  }
  set(id: string, image: string | null, automatic = false) {
    this.refresh();
    if (
      !automatic &&
      image !== null &&
      (!ImagePath.safeParse(image).success || !this.files.includes(image))
    )
      throw new Error("Choose an existing image from the image library.");
    if (automatic) delete this.entries[id];
    else this.entries[id] = image;
    mkdirSync(path.dirname(this.overridesFile), { recursive: true });
    writeFileSync(
      this.overridesFile + ".tmp",
      JSON.stringify({ schemaVersion: 1, entries: this.entries }, null, 2) +
        "\n",
    );
    renameSync(this.overridesFile + ".tmp", this.overridesFile);
    this.refresh();
  }
  clear() {
    mkdirSync(path.dirname(this.overridesFile), { recursive: true });
    writeFileSync(
      this.overridesFile + ".tmp",
      JSON.stringify({ schemaVersion: 1, entries: {} }) + "\n",
    );
    renameSync(this.overridesFile + ".tmp", this.overridesFile);
    this.refresh();
  }
  file(relative: string): string | null {
    if (!ImagePath.safeParse(relative).success) return null;
    this.refresh();
    if (!this.files.includes(relative)) return null;
    return this.paths.get(relative) || null;
  }
}
