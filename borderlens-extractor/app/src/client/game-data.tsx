import { useEffect, useState } from "react";
import {
  Database,
  Search,
  FileJson,
  AlertCircle,
  ChevronRight,
} from "lucide-react";
import type { GameDataView, GameDefinition } from "../shared/game-data";
const roleNames = {
  root: "Family record",
  defining: "Defining part",
  related: "Shared context",
};
const label = (value: string) =>
  value.replace(/([a-z0-9])([A-Z])/g, "$1 $2").replaceAll("_", " ");
const shortPath = (value: string) => value.split(/[.:]/).at(-1) || value;
const usefulKeys = new Set([
  "PartName",
  "ItemName",
  "TitleList",
  "PrefixList",
  "RequiredCharacter",
  "TechLevelIncrease",
  "TechAbilities",
  "CustomDamageTypeDefinition",
  "CustomFiringModeDefinition",
  "WeaponAttributeEffects",
  "ZoomWeaponAttributeEffects",
  "ExternalAttributeEffects",
  "ZoomExternalAttributeEffects",
  "ItemAttributeEffects",
  "AttributeEffects",
  "CustomPresentations",
  "MinExpLevelRequirement",
  "MaxExpLevelRequirement",
  "GameStageRequirement",
  "MinGameStage",
  "MaxGameStage",
  "AssociatedItem",
  "BodyParts",
  "LeftSideParts",
  "RightSideParts",
  "ManufacturerDefinition",
  "Manufacturer",
  "AmmoResource",
  "Rarity",
  "CashValueModifier",
  "BodyPartData",
  "LeftSidePartData",
  "RightSidePartData",
]);
function NativeValue({ value }: { value: unknown }) {
  if (value === null || value === undefined)
    return <span className="game-data-unset">Not set</span>;
  if (typeof value === "boolean") return <span>{value ? "Yes" : "No"}</span>;
  if (typeof value === "number") return <span>{value}</span>;
  if (typeof value === "string")
    return value.includes(".") ? (
      <code title={value}>{shortPath(value)}</code>
    ) : (
      <span>{value}</span>
    );
  if (Array.isArray(value) && value.every((item) => typeof item === "string"))
    return (
      <ul className="game-data-values">
        {value.map((item, index) => (
          <li key={index}>
            <NativeValue value={item} />
          </li>
        ))}
      </ul>
    );
  return (
    <details className="game-data-value">
      <summary>
        {Array.isArray(value) ? `${value.length} entries` : "View settings"}
      </summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}
function PropertyTable({
  properties,
}: {
  properties: Record<string, unknown>;
}) {
  const fields = Object.entries(properties).filter(
    ([key, value]) =>
      usefulKeys.has(key) &&
      value !== null &&
      value !== undefined &&
      value !== "None" &&
      (!Array.isArray(value) || value.length),
  );
  return fields.length ? (
    <dl className="game-data-properties">
      {fields.map(([key, value]) => (
        <div key={key}>
          <dt>{label(key)}</dt>
          <dd>
            <NativeValue value={value} />
          </dd>
        </div>
      ))}
    </dl>
  ) : (
    <p className="game-data-muted">
      Open the original record below to inspect its captured fields.
    </p>
  );
}
function DefinitionRecord({ definition }: { definition: GameDefinition }) {
  const [open, setOpen] = useState(false);
  return (
    <details
      className="game-data-record"
      onToggle={(event) => {
        if (event.target === event.currentTarget)
          setOpen(event.currentTarget.open);
      }}
    >
      <summary>
        <ChevronRight size={14} />
        <span>
          <strong>{definition.label}</strong>
          <small>{definition.className}</small>
        </span>
        <em>{roleNames[definition.role]}</em>
      </summary>
      {open && (
        <div className="game-data-record-body">
          <code className="game-data-path">{definition.path}</code>
          <PropertyTable properties={definition.properties} />
          <details className="game-data-original">
            <summary>
              <FileJson size={13} /> Original extracted record
            </summary>
            <pre>{JSON.stringify(definition.raw, null, 2)}</pre>
          </details>
        </div>
      )}
    </details>
  );
}
export function GameDataTab({ familyId }: { familyId: string }) {
  const [data, setData] = useState<GameDataView | null>(null),
    [error, setError] = useState(""),
    [query, setQuery] = useState(""),
    [role, setRole] = useState("all");
  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError("");
    setQuery("");
    setRole("all");
    fetch(`/api/items/${encodeURIComponent(familyId)}/game-data`, {
      signal: controller.signal,
    })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok)
          throw Error(body.error || "Unable to read imported game data.");
        setData(body);
      })
      .catch((error) => {
        if (!controller.signal.aborted) setError(error.message);
      });
    return () => controller.abort();
  }, [familyId]);
  if (error)
    return (
      <div className="panel-empty" role="alert">
        {error}
      </div>
    );
  if (!data)
    return (
      <div className="panel-empty" role="status">
        Reading imported game definitions…
      </div>
    );
  const primary = data.definitions.filter(
    (record) => record.role !== "related",
  );
  const matches = data.definitions.filter(
    (record) =>
      (role === "all" || role === record.role) &&
      (!query ||
        `${record.path} ${record.label} ${record.className}`
          .toLowerCase()
          .includes(query.toLowerCase())),
  );
  const facts = [
    ["Extracted category", data.family.category],
    ["Extracted type", data.family.subtype],
    ["Character", data.family.character],
    ["Manufacturers", data.facts.manufacturers.join(", ")],
    ["Rarity", data.facts.rarities.join(", ")],
    [
      "Elements",
      data.facts.elements
        .map((value) => value.charAt(0).toUpperCase() + value.slice(1))
        .join(", "),
    ],
  ];
  return (
    <section className="game-data-tab" aria-label="Imported game data">
      <div className="game-data-intro">
        <div>
          <span className="eyebrow">FROM YOUR EXTRACTION</span>
          <h2>
            <Database size={21} /> {data.family.name}
          </h2>
          <p>
            Original game definitions. This view changes only when the imported
            extraction changes.
          </p>
        </div>
        <span className="game-data-badge">ZIP only</span>
      </div>
      <div className="game-data-overview">
        <section className="game-data-panel">
          <h3>Identity</h3>
          <dl className="game-data-facts">
            {facts.map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>
                  {value || (
                    <span className="game-data-unset">
                      Not established by linked definitions
                    </span>
                  )}
                </dd>
              </div>
            ))}
          </dl>
          {data.facts.redText && (
            <blockquote className="game-data-red-text">
              {data.facts.redText}
            </blockquote>
          )}
        </section>
        <section className="game-data-panel">
          <h3>Extraction</h3>
          <div className="game-data-counts">
            <div>
              <strong>{primary.length}</strong>
              <span>family / defining records</span>
            </div>
            <div>
              <strong>{data.definitions.length - primary.length}</strong>
              <span>linked context records</span>
            </div>
          </div>
          {data.captures.map((capture) => (
            <div className="game-data-capture" key={capture.id}>
              <strong>{capture.name}</strong>
              <span>
                Extractor {capture.version} · {capture.objects.toLocaleString()}{" "}
                records
              </span>
            </div>
          ))}
          <p className="game-data-muted">
            Related definitions can contain alternatives and other item
            families. A link alone does not establish compatibility or a drop
            chance.
          </p>
        </section>
      </div>
      {data.warnings.map((warning, index) => (
        <div className="game-data-warning" key={index}>
          <AlertCircle size={15} />
          <span>{warning}</span>
        </div>
      ))}
      <section className="game-data-panel">
        <h3>Native values & defining parts</h3>
        <p className="game-data-muted">
          These are definition settings and rule inputs, rather than finished
          item stats or obtainable level ranges. Expand a record to read its
          values and original fields.
        </p>
        <div className="game-data-records">
          {primary.map((definition) => (
            <DefinitionRecord key={definition.path} definition={definition} />
          ))}
        </div>
      </section>
      <section className="game-data-panel">
        <h3>Browse linked definitions</h3>
        <div className="game-data-search">
          <label>
            <Search size={15} />
            <input
              aria-label="Search game definitions"
              placeholder="Search names, paths or definition types"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <select
            aria-label="Filter game definitions"
            value={role}
            onChange={(event) => setRole(event.target.value)}
          >
            <option value="all">All records</option>
            <option value="root">Family records</option>
            <option value="defining">Defining parts</option>
            <option value="related">Shared context</option>
          </select>
          <small>{matches.length} records</small>
        </div>
        <div className="game-data-records">
          {matches.map((definition) => (
            <DefinitionRecord key={definition.path} definition={definition} />
          ))}
        </div>
        {!matches.length && (
          <p className="panel-empty">No matching definitions.</p>
        )}
      </section>
    </section>
  );
}
