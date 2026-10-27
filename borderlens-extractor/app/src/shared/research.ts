export const researchProviders = ["Wiki", "Lootlemon"] as const;
export type ResearchProvider = (typeof researchProviders)[number];
export const providerForUrl = (url: string): ResearchProvider | null => {
  try {
    const host = new URL(url).hostname;
    if (host === "borderlands.fandom.com") return "Wiki";
    if (host === "lootlemon.com" || host === "www.lootlemon.com")
      return "Lootlemon";
  } catch {}
  return null;
};
export type ResearchReport = {
  discovered: ResearchProvider[];
  providers: {
    provider: ResearchProvider;
    status: "saved" | "unavailable" | "not_found" | "urls_ready" | "inherited";
    urls: string[];
    message: string;
    checkedAt: string;
  }[];
};

export type ExcludedSource = {
  sourceId: string;
  url: string;
  title: string;
  excludedAt: string;
};
/** Article identity, ignoring tracking/revision queries and encoded Wiki spacing. */
export function sourceKey(input: string): string {
  try {
    const u = new URL(input);
    return (
      u.protocol +
      "//" +
      u.hostname.replace(/^www\./, "") +
      decodeURIComponent(u.pathname)
        .replace(/_/g, " ")
        .replace(/\/$/, "")
        .toLowerCase()
    );
  } catch {
    return input.trim();
  }
}

/** Effective shared references, including URLs not yet captured. */
export type InheritedEvidence = {
  selectedContent?: { boxes: number; warnings: number };
  textBytes?: number | null;
  url: string;
  title: string;
  parents: { id: string; name: string }[];
  captured: boolean;
  alwaysInclude?: boolean;
  inclusionMode?: SourceInclusionMode;
};

export const sourceInclusionModes = ["auto", "always", "never"] as const;
export type SourceInclusionMode = (typeof sourceInclusionModes)[number];
