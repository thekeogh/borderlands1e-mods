import { SourceRecapture } from "./source-recapture";
import { SourceSize } from "./source-size";
import { ManualEvidenceIcon } from "./manual-evidence-icon";
import { isManualTextUrl } from "../shared/manual-evidence";
import { SourceSite } from "./source-site";
import { useEffect, useState } from "react";
import { BookOpen, ArrowUpRight } from "lucide-react";
import type {
  InheritedEvidence,
  SourceInclusionMode,
} from "../shared/research";
export function InheritedEvidenceList({
  items,
  manage,
  recapture,
  setMode,
  setAllModes,
  disabled,
}: {
  items: InheritedEvidence[];
  manage: (id: string) => void;
  recapture?: (ownerId: string, url: string) => unknown | Promise<unknown>;
  setMode: (url: string, mode: SourceInclusionMode) => Promise<boolean>;
  setAllModes: (mode: SourceInclusionMode) => Promise<boolean>;
  disabled?: boolean;
}) {
  const [bulkPending, setBulkPending] = useState(false);
  if (!items.length) return null;
  const priority = { always: 0, auto: 1, never: 2 };
  const mode = (item: InheritedEvidence) =>
    item.inclusionMode || (item.alwaysInclude ? "always" : "auto");
  const alphabetical = new Intl.Collator(undefined, {
    sensitivity: "base",
    numeric: true,
  });
  const sorted = [...items].sort(
    (a, b) =>
      priority[mode(a)] - priority[mode(b)] ||
      alphabetical.compare(a.title, b.title) ||
      a.url.localeCompare(b.url),
  );
  return (
    <section
      className="inherited-evidence-list"
      aria-label="Inherited evidence"
    >
      <div className="inherited-evidence-heading">
        <BookOpen size={14} />
        <strong>Inherited evidence</strong>
        <span>{items.length}</span>
        <label className="inherited-evidence-bulk">
          Set all
          <select
            aria-label="Set all inherited evidence"
            value=""
            disabled={disabled || bulkPending}
            onChange={(event) => {
              const mode = event.target.value as SourceInclusionMode;
              if (!mode) return;
              setBulkPending(true);
              void setAllModes(mode).finally(() => setBulkPending(false));
            }}
          >
            <option value="" disabled>
              {bulkPending ? "Saving…" : "Choose mode…"}
            </option>
            <option value="auto">Auto</option>
            <option value="always">Always include</option>
            <option value="never">Never include</option>
          </select>
        </label>
      </div>
      <p>
        Shared references are available to this item. Capture unsaved articles
        in their shared group. Auto selects relevant facts; Always include sends
        all indexed facts; Never include skips the source for this item. Sizes
        measure saved text; labels are guides, not AI limits.
      </p>
      {(["always", "auto", "never"] as const).map((group) => {
        const rows = sorted.filter((item) => mode(item) === group);
        if (!rows.length) return null;
        const title = {
          always: "Always include",
          auto: "Auto",
          never: "Never include",
        }[group];
        return (
          <section
            key={group}
            className={"inherited-evidence-group is-" + group}
            aria-label={title + " evidence"}
          >
            <h3 className="inherited-evidence-group-title">
              {title}
              <span>{rows.length}</span>
            </h3>
            <div className="inherited-evidence-group-rows">
              {rows.map((item) => (
                <div
                  key={item.url}
                  data-source-url={item.url}
                  className={
                    "inherited-evidence-row" +
                    (isManualTextUrl(item.url)
                      ? " is-manual-text manual-evidence-surface"
                      : "")
                  }
                >
                  {isManualTextUrl(item.url) ? (
                    <button
                      className="inherited-evidence-title"
                      title="View shared manual text"
                      onClick={() => manage(item.parents[0].id)}
                    >
                      <ManualEvidenceIcon size={16} />
                      {item.title} <SourceSite url={item.url} />
                    </button>
                  ) : (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inherited-evidence-title"
                    >
                      {item.title}
                      <ArrowUpRight size={11} />
                    </a>
                  )}
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
                  {item.selectedContent && (
                    <span
                      className="selected-content-badge"
                      title="Only selected areas of this page are saved."
                    >
                      Selected excerpt
                    </span>
                  )}
                  <SourceSize bytes={item.textBytes} />
                  {recapture &&
                    item.captured &&
                    !isManualTextUrl(item.url) &&
                    item.parents[0] && (
                      <SourceRecapture
                        url={item.url}
                        title={item.title}
                        disabled={disabled}
                        run={() => recapture(item.parents[0].id, item.url)}
                      />
                    )}
                  <InclusionMode
                    item={item}
                    disabled={disabled || bulkPending}
                    setMode={setMode}
                  />
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
            </div>
          </section>
        );
      })}
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
