import { commonFields, statChecklist } from "../src/server/source-analysis.ts";
// Used only by unrelated queue/browser fixtures, never production compilation.
export function emptySourceReading(
  category: keyof typeof statChecklist = "Weapons",
) {
  return {
    facts: [],
    fields: [...commonFields, ...statChecklist[category]].map((name) => ({
      name,
      status: "not_found",
      reason: "Synthetic source fixture; source extraction tested separately.",
    })),
    proposedFields: [],
  };
}
