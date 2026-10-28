import { z } from "zod";
/** Structured-output providers require an object at the root; nullable values belong in properties. */
export function agentOutputSchema(schema: z.ZodType) {
  const json = z.toJSONSchema(schema, { target: "draft-7" });
  if (json.type !== "object" || json.anyOf)
    throw new Error(
      "Invalid agent output schema: the root must be an object. Wrap nullable decisions in an object property.",
    );
  // Zod emits oneOf for discriminated unions. Strict providers support anyOf;
  // literal discriminators keep these branches mutually exclusive. Runtime Zod
  // parsing still validates every returned value against the original schema.
  const normalize = (node: unknown): void => {
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node)) {
      node.forEach(normalize);
      return;
    }
    const object = node as Record<string, unknown>;
    if (Array.isArray(object.oneOf)) {
      object.anyOf = object.oneOf;
      delete object.oneOf;
    }
    Object.values(object).forEach(normalize);
  };
  normalize(json);
  return json;
}
