import { z } from "zod";
/** Structured-output providers require an object at the root; nullable values belong in properties. */
export function agentOutputSchema(schema: z.ZodType) {
  const json = z.toJSONSchema(schema, { target: "draft-7" });
  if (json.type !== "object" || json.anyOf)
    throw new Error(
      "Invalid agent output schema: the root must be an object. Wrap nullable decisions in an object property.",
    );
  return json;
}
