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
    status: "saved" | "unavailable" | "not_found";
    urls: string[];
    message: string;
    checkedAt: string;
  }[];
};
