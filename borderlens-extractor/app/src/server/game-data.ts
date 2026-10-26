import type { GameDataView, GameDefinition } from "../shared/game-data.ts";
import { discover, unpack } from "./importer.ts";
import { buildPacket } from "./evidence.ts";
import { HttpError, type Store } from "./store.ts";
import type { Family } from "../shared/models.ts";
const cache = new WeakMap<
  Store,
  {
    key: string;
    families: Map<string, Family>;
    views: Map<string, GameDataView>;
  }
>();
export function gameData(store: Store, id: string): GameDataView {
  // Re-discover identity from ZIP records; live Family metadata can contain source overrides.
  const key = JSON.stringify([
    store.state.captures.map((capture) => capture.id),
    store.records.size,
  ]);
  let index = cache.get(store);
  if (!index || index.key !== key) {
    index = {
      key,
      families: new Map(
        discover(store.records).map((family) => [family.id, family]),
      ),
      views: new Map(),
    };
    cache.set(store, index);
  }
  const saved = index.views.get(id);
  if (saved) return saved;
  const family = index.families.get(id);
  if (!family)
    throw new HttpError(
      404,
      "No family definition found in the imported game extraction.",
    );
  // The packet builder receives a ZIP-only facade: reading sources or artifacts is impossible.
  const packet = buildPacket(
    { records: store.records, sources: () => [], get: () => null },
    family,
  );
  const roots = new Set(family.roots.map((path) => path.toLowerCase()));
  const definitions: GameDefinition[] = packet.evidence
    .filter((evidence) => evidence.kind === "game" && evidence.path)
    .map((evidence): GameDefinition => {
      const raw = store.records.get(evidence.path!.toLowerCase())!,
        properties = unpack(raw.properties) || {};
      const label = [
        properties.PartName,
        properties.ItemName,
        properties.ManufacturerName,
        properties.DisplayName,
      ].find(
        (value) =>
          typeof value === "string" && value.trim() && value !== "None",
      );
      return {
        path: raw.path,
        label: label || raw.path.split(/[.:]/).at(-1) || raw.path,
        className: raw.class || "Unknown definition",
        role: roots.has(raw.path.toLowerCase())
          ? "root"
          : (evidence.value as any).role === "family-defining"
            ? "defining"
            : "related",
        properties,
        raw,
      };
    })
    .sort(
      (a, b) =>
        ({ root: 0, defining: 1, related: 2 })[a.role] -
          { root: 0, defining: 1, related: 2 }[b.role] ||
        a.path.localeCompare(b.path),
    );
  const view: GameDataView = {
    family: {
      id: family.id,
      name: family.name,
      category: family.category,
      subtype: family.subtype,
      character: family.character || null,
      roots: [...family.roots],
    },
    captures: store.state.captures.map(({ id, name, version, objects }) => ({
      id,
      name,
      version,
      objects,
    })),
    facts: packet.facts,
    definitions,
    warnings: packet.warnings.filter((message) => message.includes("bounded")),
  };
  if (
    definitions.some(
      (definition) =>
        definition.raw.complete === false ||
        (Array.isArray(definition.raw.issues) && definition.raw.issues.length),
    )
  )
    view.warnings.push(
      "Some captured records contain extraction issues. Their original flags are included in the record browser.",
    );
  index.views.set(id, view);
  return view;
}
