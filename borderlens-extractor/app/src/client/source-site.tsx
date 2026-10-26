/** Display the original article host; never infer it from its title or owner. */
export function SourceSite({ url }: { url: string }) {
  let domain: string;
  try {
    domain = new URL(url).hostname.toLowerCase().replace(/^www\./, "");
  } catch {
    return null;
  }
  const site =
    domain === "lootlemon.com" || domain.endsWith(".lootlemon.com")
      ? "lootlemon"
      : domain === "fandom.com" || domain.endsWith(".fandom.com")
        ? "wiki"
        : "other";
  return (
    <span
      className={`source-site source-site-${site}`}
      title={`Source site: ${domain}`}
    >
      {domain}
    </span>
  );
}
