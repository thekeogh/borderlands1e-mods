import { contentPacks } from "../shared/content.ts";
import { readFileSync } from "node:fs";
import path from "node:path";
import { load } from "cheerio";
import { parseSource } from "./source-content.ts";
import { hash } from "./store.ts";
import type { Store } from "./store.ts";
import type { Family, Source } from "../shared/models.ts";
import type { SourceReading } from "./source-analysis.ts";
export const PARSER_POLICY = "2";
const normal = (value: string) =>
  value.toLowerCase().replace(/[^a-z0-9]+/g, "");
const numeric = (value: string) =>
  /^[-+]?\d+(?:\.\d+)?$/.test(value.trim()) ? Number(value) : null;
export function interpretationContent(
  store: Pick<Store, "dir">,
  f: Family,
  source: Source,
) {
  let residual = {
    text: source.text,
    sections: source.sections || [],
    tables: source.tables || [],
  };
  const facts: SourceReading["facts"] = [];
  // An explicit item-owned binding and exact title are needed. Shared/generic tables stay with the reader.
  if (
    source.familyId === f.id &&
    !source.inheritedFrom &&
    !source.manualText &&
    !source.selectedContent?.warnings &&
    !/Borderlands\s*(?:2|3|4)|The Pre-Sequel|Wonderlands/i.test(
      source.title + " " + source.url + " " + source.text,
    ) &&
    normal(source.title) === normal(f.name) &&
    !/\b(?:example|sample|illustrative|maximum[ -]roll|max[ -]roll)\b/i.test(
      source.text,
    )
  ) {
    try {
      const root = path.resolve(store.dir, "sources"),
        filename = path.resolve(root, source.filename);
      if (path.dirname(filename) !== root) throw Error("Invalid source path");
      const $ = load(readFileSync(filename, "utf8"));
      let removed = 0;
      $("table")
        .slice(0, 20)
        .each((_index, table) => {
          const t = $(table);
          if (t.find("[rowspan],[colspan],table").length) return;
          const rows = t.find("tr").toArray();
          if (rows.length < 2 || rows.length > 50) return;
          const headers = $(rows[0])
            .children("th,td")
            .toArray()
            .map((c) => $(c).text().trim());
          const keys = headers.map(normal);
          if (new Set(keys).size !== keys.length) return;
          const parsed: SourceReading["facts"] = [];
          for (const row of rows.slice(1)) {
            const cells = $(row)
              .children("th,td")
              .toArray()
              .map((c) => $(c).text().trim());
            if (cells.length !== keys.length) return;
            const get = (key: string) => cells[keys.indexOf(key)] || "";
            const quote = $(row).text().trim();
            const base = {
              catalogueRole: "item_property" as const,
              extractionMethod: "parser" as const,
              manufacturerNames: [] as string[],
              origin: null,
              stat: null,
              structured: null,
            };
            if (keys.join("|") === "property|value") {
              const label = normal(get("property")),
                value = get("value");
              if (!value) return;
              if (
                label === "manufacturer" &&
                !/^(none|unknown|n\/a|unspecified|not applicable)$/i.test(
                  value,
                ) &&
                !/[,/;]|\b(?:and|or)\b|\s&\s/i.test(value)
              )
                parsed.push({
                  ...base,
                  field: "manufacturers",
                  detail: quote,
                  quote,
                  manufacturerNames: [value],
                  structured: {
                    kind: "list",
                    coverage: "partial",
                    field: "manufacturers",
                    values: [value],
                  },
                });
              else if (
                label === "rarity" &&
                /^(Common|Uncommon|Rare|Epic|Legendary|Pearlescent)$/i.test(
                  value,
                )
              )
                parsed.push({
                  ...base,
                  field: "rarities",
                  detail: quote,
                  quote,
                  structured: {
                    kind: "list",
                    coverage: "partial",
                    field: "rarities",
                    values: [
                      value[0].toUpperCase() + value.slice(1).toLowerCase(),
                    ],
                  },
                });
              else if (
                label === "element" &&
                /^(Non-elemental|Incendiary|Shock|Corrosive|Explosive)$/i.test(
                  value,
                )
              )
                parsed.push({
                  ...base,
                  field: "elements",
                  detail: quote,
                  quote,
                  structured: {
                    kind: "list",
                    coverage: "partial",
                    field: "elements",
                    values: [
                      value[0].toUpperCase() + value.slice(1).toLowerCase(),
                    ],
                  },
                });
              else if (
                ["dlc", "origin", "contentpack"].includes(label) &&
                contentPacks.some(
                  (pack) => pack.toLowerCase() === value.toLowerCase(),
                )
              )
                parsed.push({
                  ...base,
                  field: "dlc",
                  detail: quote,
                  quote,
                  origin: contentPacks.find(
                    (pack) => pack.toLowerCase() === value.toLowerCase(),
                  )!,
                });
              else if (label === "redtext")
                parsed.push({
                  ...base,
                  field: "redText",
                  detail: quote,
                  quote,
                  structured: { kind: "redText", text: value },
                });
              else return;
            } else if (
              keys.includes("stat") &&
              keys.includes("minimum") &&
              keys.includes("maximum") &&
              keys.includes("unit") &&
              keys.every((k) =>
                [
                  "stat",
                  "minimum",
                  "maximum",
                  "unit",
                  "level",
                  "context",
                ].includes(k),
              )
            ) {
              const minimum = numeric(get("minimum")),
                maximum = numeric(get("maximum")),
                level = get("level") ? numeric(get("level")) : null;
              if (
                minimum === null ||
                maximum === null ||
                minimum > maximum ||
                !get("stat") ||
                get("context").length > 120 ||
                (get("level") && (!level || !Number.isInteger(level)))
              )
                return;
              parsed.push({
                ...base,
                field: "stats",
                detail: quote,
                quote,
                stat: {
                  name: get("stat"),
                  context: get("context") || null,
                  minimum,
                  maximum,
                  unit: get("unit"),
                  level,
                  notes: get("context"),
                },
              });
            } else return;
          }
          if (parsed.length) {
            facts.push(...parsed);
            t.remove();
            removed++;
          }
        });
      if (removed) {
        const parsed = parseSource($.html());
        residual = {
          text: normal(parsed.text) === normal(parsed.title) ? "" : parsed.text,
          sections: parsed.sections,
          tables: parsed.tables,
        };
      }
    } catch {
      /* Missing/unknown HTML is interpreted from the intact saved source. */
    }
  }
  const content = interpretationText(source, residual);
  return {
    content,
    facts,
    hash: hash(
      JSON.stringify({
        policy: PARSER_POLICY,
        source: source.hash,
        content,
        facts,
      }),
    ),
    policy: PARSER_POLICY,
  };
}

/** Retain every original word, without repeating complete prose again as section bodies. */
export function interpretationText(
  source: Pick<Source, "text" | "sections" | "tables" | "selectedContent">,
  residual = {
    text: source.text,
    sections: source.sections || [],
    tables: source.tables || [],
  },
) {
  if (!residual.text) return "";
  const canonical = (text: string) => text.replace(/\s+/g, "").toLowerCase();
  const body = canonical(residual.text);
  const sections = residual.sections.map((section) => ({
    heading: section.heading,
    ...(body.includes(canonical(section.text))
      ? { startsWith: section.text.slice(0, 120) }
      : { text: section.text }),
  }));
  return (
    (source.selectedContent
      ? "USER-SELECTED PAGE EXCERPT: Only selected areas were captured. Missing content is not proof of absence. Partial tables/text may require caution.\n"
      : "") +
    residual.text +
    "\n\nSTORED SECTIONS AND TABLES (section starts are layout anchors, not additional facts)\n" +
    JSON.stringify({ sections, tables: residual.tables })
  );
}
