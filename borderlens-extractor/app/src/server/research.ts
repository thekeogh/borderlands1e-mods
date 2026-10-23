import { parseSource } from "./source-content.ts";
import { load } from "cheerio";
import robotsParser from "robots-parser";
import { Store, hash } from "./store.ts";
import {
  now,
  type Family,
  type Source,
  type CoverageEntry,
} from "../shared/models.ts";
export const ALLOWED = new Set([
  "borderlands.fandom.com",
  "www.lootlemon.com",
  "lootlemon.com",
]);
export function sourceUrl(input: string) {
  let u: URL;
  try {
    u = new URL(input);
  } catch {
    throw new Error("Enter a complete source URL.");
  }
  if (
    u.protocol !== "https:" ||
    !ALLOWED.has(u.hostname) ||
    u.port ||
    u.username ||
    u.password
  )
    throw new Error("Sources must be HTTPS wiki or Lootlemon pages.");
  u.hash = "";
  return u;
}
export class Research {
  robots = new Map<string, string>();
  last = 0;
  constructor(
    public store: Store,
    public fetcher: typeof fetch = fetch,
    public baseOverride = process.env.BORDERLENS_RESEARCH_BASE,
  ) {}
  async request(url: URL) {
    const wait = Math.max(0, 500 - (Date.now() - this.last));
    if (wait) await new Promise((r) => setTimeout(r, wait));
    this.last = Date.now();
    let target = url.toString();
    if (this.baseOverride)
      target = this.baseOverride.replace(/\/$/, "") + url.pathname + url.search;
    const response = await this.fetcher(target, {
      redirect: "manual",
      headers: {
        "User-Agent": "BorderlensResearch/0.1 (local personal catalogue tool)",
        Accept: "text/html,application/json,text/plain",
      },
      signal: AbortSignal.timeout(25000),
    });
    if (response.status >= 300 && response.status < 400) {
      const loc = response.headers.get("location");
      if (!loc) throw new Error("Source redirected without a destination.");
      return { redirect: sourceUrl(new URL(loc, url).href), response };
    }
    return { redirect: null, response };
  }
  async fetchText(input: string, checkRobots = true) {
    let u = sourceUrl(input);
    if (checkRobots) {
      let rules = this.robots.get(u.origin);
      if (rules === undefined) {
        const r = await this.request(new URL("/robots.txt", u));
        if (r.redirect)
          throw new Error("Unable to verify redirected robots rules.");
        if (r.response.status === 404) rules = "";
        else {
          if (!r.response.ok)
            throw new Error(
              `Source access rules unavailable (${r.response.status}). Import saved HTML or use game evidence only.`,
            );
          rules = await r.response.text();
        }
        this.robots.set(u.origin, rules);
      }
      if (
        robotsParser(u.origin + "/robots.txt", rules).isAllowed(
          u.href,
          "BorderlensResearch",
        ) === false
      )
        throw new Error(
          "This source disallows automated access to this page. Import saved HTML or use game evidence only.",
        );
    }
    for (let i = 0; i < 4; i++) {
      const { response, redirect } = await this.request(u);
      if (redirect) {
        u = redirect;
        continue;
      }
      if (!response.ok)
        throw new Error(
          `Source returned HTTP ${response.status}: ${u.hostname}. Import saved HTML, correct the source, or use game evidence only.`,
        );
      const declared = Number(response.headers.get("content-length") || 0);
      if (declared > 5 * 1024 * 1024)
        throw new Error("Source page exceeds the size limit.");
      const reader = response.body?.getReader();
      if (!reader) throw new Error("Empty source response.");
      const parts: Uint8Array[] = [];
      let size = 0;
      for (;;) {
        const x = await reader.read();
        if (x.done) break;
        size += x.value.length;
        if (size > 5 * 1024 * 1024) {
          await reader.cancel();
          throw new Error("Source page exceeds the size limit.");
        }
        parts.push(x.value);
      }
      return { url: u.href, text: Buffer.concat(parts).toString("utf8") };
    }
    throw new Error("Too many source redirects.");
  }
  parse(html: string) {
    return parseSource(html);
  }

  save(f: Family, url: string, html: string, imported = false) {
    sourceUrl(url);
    const parsed = this.parse(html);
    if (parsed.text.length < 60)
      throw new Error("Source has too little readable content.");
    const id = "page:" + hash(f.id + "|" + url + "|" + html).slice(0, 20);
    const s: Source = {
      id,
      familyId: f.id,
      url,
      title: parsed.title || f.name,
      fetchedAt: now(),
      hash: hash(html),
      text: parsed.text,
      contentVersion: 2,
      sections: parsed.sections,
      tables: parsed.tables,
      filename: id.replace(":", "-") + ".html",
      imported,
    };
    this.store.putSource(s, html);
    return s;
  }
  async fetchPage(f: Family, url: string, refresh = false) {
    const existing = this.store.sources(f.id).find((s) => s.url === url);
    if (existing && !refresh) return existing;
    const fetched = await this.fetchText(url);
    return this.save(f, fetched.url, fetched.text);
  }
  async inventory(onProgress: (m: string) => void) {
    const existing = this.store.get<{
      at: string;
      entries: CoverageEntry[];
      errors?: string[];
    }>("_project", "inventory");
    if (existing && Date.now() - Date.parse(existing.at) < 86400000) {
      this.store.state.coverage.errors = existing.errors || [];
      return existing.entries;
    }
    const entries: CoverageEntry[] = [];
    const errors: string[] = [];
    for (const [category, slug] of [
      ["Weapons", "weapons"],
      ["Shields", "shields"],
      ["Grenade mods", "grenade-mods"],
      ["Class mods", "class-mods"],
    ]) {
      const url = `https://www.lootlemon.com/db/borderlands-1/${slug}`;
      onProgress(`Reading Lootlemon ${category.toLowerCase()}…`);
      try {
        const page = await this.fetchText(url);
        this.store.put("_project", "inventory-html:" + slug, {
          url: page.url,
          html: page.text,
          retrievedAt: now(),
        });
        const $ = load(page.text);
        $("a[href]").each((_i, el) => {
          const href = $(el).attr("href") || "";
          if (!/^\/(weapon|shield|grenade-mod|class-mod)\//.test(href)) return;
          let name =
            $(el).find("h2,h3,h4").first().text().trim() ||
            $(el).attr("aria-label") ||
            $(el).text().trim();
          name = name.replace(/\s+/g, " ").trim();
          if (!name || name.length > 90) return;
          entries.push({
            key: hash(href),
            name,
            category,
            url: new URL(href, url).href,
            source: "Lootlemon",
            game: "BL1 listing; verify item page edition",
            status: "missing_extraction",
            familyIds: [],
            reason:
              "From BL1 equipment listing; identity match not yet verified.",
          });
        });
      } catch (e: any) {
        errors.push(`${category}: ${e.message}`);
      }
    }
    // MediaWiki discovery includes continuations and explicit subcategory traversal.
    const cats = [
      "Category:Weapons_in_Borderlands",
      "Category:Shields_in_Borderlands",
      "Category:Grenade_Mods_in_Borderlands",
      "Category:Class_Mods_in_Borderlands",
    ];
    const visited = new Set<string>();
    let pages = 0;
    while (cats.length && visited.size < 40) {
      const cat = cats.shift()!;
      if (visited.has(cat)) continue;
      visited.add(cat);
      let continuation: string | undefined;
      try {
        do {
          const u = new URL("https://borderlands.fandom.com/api.php");
          u.search = new URLSearchParams({
            action: "query",
            list: "categorymembers",
            cmtitle: cat,
            cmlimit: "500",
            format: "json",
            ...(continuation ? { cmcontinue: continuation } : {}),
          }).toString();
          onProgress(
            `Reading wiki inventory: ${cat.replace("Category:", "")}…`,
          );
          const page = await this.fetchText(u.href);
          let data: any;
          try {
            data = JSON.parse(page.text);
          } catch {
            throw new Error("Wiki API returned HTML instead of JSON.");
          }
          if (data.error)
            throw new Error(data.error.info || "Wiki query failed.");
          this.store.put("_project", "wiki:" + hash(u.href), {
            url: u.href,
            body: data,
            retrievedAt: now(),
          });
          for (const p of data.query?.categorymembers || []) {
            if (p.ns === 14) {
              if (
                /Borderlands(?:$|[^0-9])/i.test(p.title) &&
                !/(?:Borderlands_[234]|Pre.Sequel|Wonderlands)/i.test(p.title)
              )
                cats.push(p.title);
              continue;
            }
            if (p.ns !== 0) continue;
            entries.push({
              key: "wiki:" + p.pageid,
              name: p.title,
              category: "Wiki candidate",
              url:
                "https://borderlands.fandom.com/wiki/" +
                encodeURIComponent(p.title.replaceAll(" ", "_")),
              source: "Wiki",
              game: "BL1 category; verify item page",
              status: "missing_extraction",
              familyIds: [],
              reason: "Wiki category member; may be a guide, title or family.",
            });
          }
          continuation = data.continue?.cmcontinue;
          if (++pages > 80)
            throw new Error("Wiki inventory page budget reached.");
        } while (continuation);
      } catch (e: any) {
        errors.push(`${cat}: ${e.message}`);
      }
    }
    const unique = [...new Map(entries.map((e) => [e.key, e])).values()];
    this.store.state.coverage.errors = errors;
    this.store.put("_project", "inventory", {
      at: now(),
      entries: unique,
      errors,
    });
    return unique;
  }
}
export const normalName = (s: string) =>
  s
    .toLowerCase()
    .replace(
      /\s*\((?:borderlands|smg|title|revolver|rifle|shotgun|sniper rifle)\)\s*/g,
      "",
    )
    .replace(/[^a-z0-9]/g, "");
export function compareCoverage(entries: CoverageEntry[], families: Family[]) {
  return entries.map((e) => {
    const matches = families.filter((f) =>
      [f.name, ...f.aliases].some((n) => normalName(n) === normalName(e.name)),
    );
    return {
      ...e,
      status:
        matches.length === 1
          ? ("matched" as const)
          : matches.length > 1
            ? ("ambiguous" as const)
            : ("missing_extraction" as const),
      familyIds: matches.map((f) => f.id),
      reason:
        matches.length === 1
          ? "Name/alias match; verify supporting page in item research."
          : matches.length > 1
            ? "Name occurs in multiple extracted families."
            : "No extracted name/alias match; candidate needs investigation.",
    };
  });
}
