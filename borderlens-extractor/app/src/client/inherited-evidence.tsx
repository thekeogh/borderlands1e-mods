import { useEffect, useState } from "react";
import { BookOpen, ArrowUpRight } from "lucide-react";
import type {
  InheritedEvidence,
  SourceInclusionMode,
} from "../shared/research";
export function InheritedEvidenceList({
  items,
  manage,
  setMode,
  disabled,
}: {
  items: InheritedEvidence[];
  manage: (id: string) => void;
  setMode: (url: string, mode: SourceInclusionMode) => Promise<boolean>;
  disabled?: boolean;
}) {
  if (!items.length) return null;
  return (
    <section
      className="inherited-evidence-list"
      aria-label="Inherited evidence"
    >
      <div className="inherited-evidence-heading">
        <BookOpen size={14} />
        <strong>Inherited evidence</strong>
        <span>{items.length}</span>
      </div>
      <p>
        Shared references are available to this item. Capture unsaved articles
        in their shared group. Auto selects relevant facts; Always include sends
        all indexed facts; Never include skips the source for this item.
      </p>
      {items.map((item) => (
        <div key={item.url} className="inherited-evidence-row">
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="inherited-evidence-title"
          >
            {item.title}
            <ArrowUpRight size={11} />
          </a>
          <span className="inherited-evidence-parents">
            from{" "}
            {item.parents.map((parent, index) => (
              <span key={parent.id}>
                {index > 0 && " · "}
                <button
                  className="inherited-evidence-parent"
                  title={"Manage shared evidence in " + parent.name}
                  onClick={() => manage(parent.id)}
                >
                  {parent.name}
                </button>
              </span>
            ))}
          </span>
          <InclusionMode item={item} disabled={disabled} setMode={setMode} />
          <span
            className={
              "inherited-evidence-capture " +
              (item.captured ? "is-saved" : "is-pending")
            }
          >
            {item.captured ? "Saved" : "Awaiting capture"}
          </span>
        </div>
      ))}
    </section>
  );
}

function InclusionMode({
  item,
  disabled,
  setMode,
}: {
  item: InheritedEvidence;
  disabled?: boolean;
  setMode: (url: string, mode: SourceInclusionMode) => Promise<boolean>;
}) {
  const [pending, setPending] = useState<SourceInclusionMode | null>(null);
  const saved = item.inclusionMode || (item.alwaysInclude ? "always" : "auto");
  useEffect(() => {
    if (pending === saved) setPending(null);
  }, [pending, saved]);
  const mode = pending ?? saved;
  return (
    <label
      className={"inherited-evidence-mode is-" + mode}
      title="Applies to this item only, on the next build. Auto selects relevant facts. Always include sends all indexed facts. Never include skips this source before analysis."
    >
      <select
        aria-label={"Evidence mode: " + item.title}
        value={mode}
        disabled={disabled || pending !== null}
        onChange={(event) => {
          const value = event.target.value as SourceInclusionMode;
          setPending(value);
          void setMode(item.url, value)
            .then((ok) => {
              if (!ok) setPending(null);
            })
            .catch(() => setPending(null));
        }}
      >
        <option value="auto">Auto</option>
        <option value="always">Always include</option>
        <option value="never">Never include</option>
      </select>
    </label>
  );
}
