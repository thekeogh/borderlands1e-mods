import { load } from "cheerio";
const clean = (text: string) =>
  text
    .replace(/[\t\r ]+/g, " ")
    .replace(/\n\s*\n/g, "\n")
    .trim();
export function parseSource(html: string) {
  const $ = load(html);
  const selected =
    $('meta[name="borderlens-capture"]').attr("content") === "selected";
  const boxes = Number(
    $('meta[name="borderlens-selection-count"]').attr("content"),
  );
  const warnings = Number(
    $('meta[name="borderlens-selection-warnings"]').attr("content"),
  );
  const selectedContent =
    selected &&
    Number.isInteger(boxes) &&
    boxes >= 1 &&
    boxes <= 30 &&
    Number.isInteger(warnings) &&
    warnings >= 0 &&
    warnings <= boxes
      ? { boxes, warnings }
      : undefined;
  $("script,style,nav,footer,header,iframe,noscript").remove();
  const title = $("h1").first().text().trim() || $("title").text().trim();
  const content = $(".mw-parser-output").first().length
    ? $(".mw-parser-output").first()
    : $("main").length
      ? $("main").first()
      : $("body");
  const sections: { heading: string; text: string }[] = [];
  let current: { heading: string; text: string } | undefined;
  const visit = (node: any) => {
    if (node.type === "tag" && /^h[1-4]$/i.test(node.tagName)) {
      if (sections.length >= 80) {
        current = undefined;
        return;
      }
      current = { heading: clean($(node).text()), text: "" };
      sections.push(current);
      return;
    }
    if (node.type === "text" && current) {
      const text = clean(node.data || "");
      if (text) current.text = (current.text + " " + text).slice(0, 12000);
      return;
    }
    for (const child of node.children || []) visit(child);
    if (current && /^(div|p|li|tr|br)$/i.test(node.tagName || ""))
      current.text += "\n";
  };
  for (const node of content.toArray()) visit(node);
  for (const section of sections) section.text = clean(section.text);
  const tables: { caption: string; headers: string[]; rows: string[][] }[] = [];
  content
    .find("table")
    .slice(0, 20)
    .each((_i, table) => {
      const headers = $(table)
        .find("thead th")
        .map((_i, th) => clean($(th).text()))
        .get();
      const rows: string[][] = [];
      $(table)
        .find("tr")
        .slice(0, 50)
        .each((_i, tr) => {
          const cells = $(tr)
            .children("td,th")
            .slice(0, 16)
            .map((_i, cell) => clean($(cell).text()).slice(0, 500))
            .get();
          if (cells.length) rows.push(cells);
        });
      tables.push({
        caption: clean($(table).find("caption").first().text()),
        headers,
        rows,
      });
    });
  return {
    title,
    text: clean(content.text()),
    sections,
    tables,
    ...(selectedContent ? { selectedContent } : {}),
  };
}
