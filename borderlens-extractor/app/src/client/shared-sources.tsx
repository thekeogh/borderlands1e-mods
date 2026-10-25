import React, { useEffect, useRef, useState } from "react";
import { X, BookOpen, Plus, Trash2, ArrowUpRight } from "lucide-react";
import {
  scopeOptions,
  scopeLabel,
  type EvidenceScope,
} from "../shared/evidence-scopes";
import type { Family, Source } from "../shared/models";
import { sourceKey } from "../shared/research";
type Detail = { family: Family; sources: Source[]; children: number };
async function call(url: string, body?: unknown) {
  const response = await fetch(
    url,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const data = await response.json();
  if (!response.ok)
    throw new Error(data.error || "Could not save shared evidence.");
  return data;
}
export function SharedSources({
  initial,
  onClose,
  onChange,
  openPage,
}: {
  initial: EvidenceScope;
  onClose: () => void;
  onChange: () => void;
  openPage: (id: string, url: string) => unknown;
}) {
  const options = scopeOptions(),
    [scope, setScope] = useState(initial),
    [rows, setRows] = useState<Detail[]>([]),
    [url, setUrl] = useState(""),
    [error, setError] = useState(""),
    [working, setWorking] = useState(false);
  const dialog = useRef<HTMLElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.querySelector<HTMLButtonElement>("button")?.focus();
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
      if (event.key === "Tab") {
        const controls = [
          ...dialog.current!.querySelectorAll<HTMLElement>(
            "button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled)",
          ),
        ].filter((el) => el.getClientRects().length && el.offsetWidth > 1);
        const first = controls[0],
          last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("keydown", key);
      if (previous?.isConnected) previous.focus();
    };
  }, []);
  const refresh = async () => setRows(await call("/api/shared-sources"));
  useEffect(() => {
    void refresh().catch((e) => setError(e.message));
    const events = new EventSource("/api/events");
    events.onmessage = () => void refresh().catch(() => {});
    return () => events.close();
  }, []);
  const detail = rows.find(
    (row) => scopeLabel(row.family.evidenceScope!) === scopeLabel(scope),
  );
  const update = async (body: unknown) => {
    setWorking(true);
    setError("");
    try {
      const result = await call("/api/shared-sources", body);
      await refresh();
      onChange();
      return result as Detail;
    } catch (e: any) {
      setError(e.message);
      return null;
    } finally {
      setWorking(false);
    }
  };
  const capture = async (target: string) => {
    const owner = detail || (await update({ scope }));
    if (owner) openPage(owner.family.id, target);
  };
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section
        ref={dialog}
        className="shared-source-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shared-sources-title"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          className="close-modal"
          aria-label="Close shared evidence"
          onClick={onClose}
        >
          <X size={20} />
        </button>
        <h2 id="shared-sources-title">
          <BookOpen size={20} /> Shared evidence
        </h2>
        <p>
          {scope.category === "Everything"
            ? "Articles here are shared with every item in the catalogue. Capture once; reuse throughout."
            : "Articles here apply to every item in this group, alongside evidence from Everything and its parent groups."}
        </p>
        <label>
          Applies to
          <select
            aria-label="Evidence group"
            value={scopeLabel(scope)}
            onChange={(event) => {
              setScope(
                options.find(
                  (option) => scopeLabel(option) === event.target.value,
                )!,
              );
              setError("");
            }}
          >
            {options.map((option) => (
              <option key={scopeLabel(option)} value={scopeLabel(option)}>
                {scopeLabel(option)}
              </option>
            ))}
          </select>
        </label>
        <p className="muted">
          {detail
            ? `${detail.children} items inherit this group’s evidence.`
            : "Add a source to share evidence with this group."}{" "}
          Item-specific exclusions still take priority.
        </p>
        {error && (
          <div role="alert" className="banner error">
            {error}
          </div>
        )}
        <form
          className="shared-source-add"
          onSubmit={(event) => {
            event.preventDefault();
            void update({ scope, url }).then((result) => {
              if (result) setUrl("");
            });
          }}
        >
          <input
            aria-label="Shared evidence URL"
            type="url"
            placeholder="Wiki or Lootlemon article URL"
            required
            value={url}
            onChange={(event) => setUrl(event.target.value)}
          />
          <button className="button primary" disabled={working}>
            <Plus size={15} />
            Add source
          </button>
        </form>
        <div className="shared-source-list">
          {detail?.family.sourceUrls.map((target) => {
            const source = detail.sources.find(
              (source) => sourceKey(source.url) === sourceKey(target),
            );
            return (
              <article className="source-card" key={target}>
                <div>
                  <strong>{source?.title || target}</strong>
                  <a
                    href={target}
                    target="_blank"
                    rel="noreferrer"
                    aria-label="Open article"
                  >
                    <ArrowUpRight size={15} />
                  </a>
                  <button
                    className="source-remove-button"
                    aria-label={"Remove shared source: " + target}
                    disabled={working}
                    onClick={() =>
                      void update({ scope, url: target, remove: true })
                    }
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
                <small>
                  {source
                    ? `${source.captureMethod === "chrome" ? "Captured in Chrome" : source.imported ? "Imported HTML" : "Fetched & cached"} · ${new Date(source.fetchedAt).toLocaleString()} · ${source.text.length.toLocaleString()} characters saved`
                    : "Not captured yet · URL only. Open in Chrome to capture the article."}
                </small>
                {source && (
                  <p className="shared-captured-text">
                    {source.text.slice(0, 550)}
                    {source.text.length > 550 ? "…" : ""}
                  </p>
                )}
                <div className="browser-import-buttons">
                  <button
                    className="button"
                    disabled={working}
                    onClick={() => void capture(target)}
                  >
                    Open in Chrome
                  </button>
                  <label className="button shared-html-import">
                    Import saved HTML
                    <input
                      aria-label={"Import shared HTML: " + target}
                      type="file"
                      accept=".html,.htm"
                      disabled={working}
                      onChange={async (event) => {
                        const file = event.target.files?.[0];
                        if (file)
                          await update({
                            scope,
                            url: target,
                            html: await file.text(),
                          });
                        event.target.value = "";
                      }}
                    />
                  </label>
                </div>
              </article>
            );
          })}
          {!detail?.family.sourceUrls.length && (
            <p className="panel-empty">No shared sources in this group yet.</p>
          )}
        </div>
        <p className="muted">
          Adding or changing evidence queues affected items for rebuilding. It
          does not start a build.
        </p>
      </section>
    </div>
  );
}
