import type { Family, Packet, Raw } from "./models.ts";
export type GameDefinition = {
  path: string;
  label: string;
  className: string;
  role: "root" | "defining" | "related";
  properties: Record<string, unknown>;
  raw: Raw;
};
/** ZIP-only view. Never contains a compiled entry, saved article or user correction. */
export type GameDataView = {
  family: {
    id: string;
    name: string;
    category: Family["category"];
    subtype: string;
    character: Family["character"] | null;
    roots: string[];
  };
  captures: { id: string; name: string; version: string; objects: number }[];
  facts: Packet["facts"];
  definitions: GameDefinition[];
  warnings: string[];
};
