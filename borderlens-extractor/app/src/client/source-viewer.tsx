import { useEffect, useRef, useState } from "react";
import { X, Copy, ArrowUpRight, BookOpen } from "lucide-react";
import type { Source } from "../shared/models";
type Tab = "text" | "structured" | "record" | "html";
export function SourceViewer({
  source,
  onClose,
}: {
  source: Source;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<Tab>("text"),
    [html, setHtml] = useState<string | null>(null),
    [error, setError] = useState(""),
    [copied, setCopied] = useState(false);
  const dialog = useRef<HTMLElement>(null),
    close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.querySelector<HTMLButtonElement>("button")?.focus();
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close.current();
      }
      if (event.key === "Tab") {
        const elements = [
          ...dialog.current!.querySelectorAll<HTMLElement>(
            'button:not(:disabled),a[href],[tabindex="0"]',
          ),
        ].filter((el) => el.getClientRects().length);
        const first = elements[0],
          last = elements.at(-1);
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
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/sources/" + encodeURIComponent(source.id) + "/html", {
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.error || "Unable to read cached HTML.");
        }
        return response.text();
      })
      .then(setHtml)
      .catch((error) => {
        if (!controller.signal.aborted) setError(error.message);
      });
    return () => controller.abort();
  }, [source.id]);
  const record = JSON.stringify(source, null, 2);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(
        tab === "html"
          ? html || ""
          : tab === "text"
            ? source.text
            : tab === "record"
              ? record
              : JSON.stringify(
                  {
                    sections: source.sections || [],
                    tables: source.tables || [],
                  },
                  null,
                  2,
                ),
      );
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };
  return (
    <div
      className="modal-backdrop source-viewer-backdrop"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        ref={dialog}
        className="source-viewer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="source-viewer-title"
      >
        <header>
          <button
            className="source-viewer-close"
            aria-label="Close source viewer"
            onClick={onClose}
          >
            <X size={20} />
          </button>
          <div className="eyebrow">
            <BookOpen size={13} /> SAVED SOURCE SNAPSHOT
          </div>
          <h2 id="source-viewer-title">{source.title}</h2>
          <a href={source.url} target="_blank" rel="noreferrer">
            {source.url} <ArrowUpRight size={12} />
          </a>
          <p>
            Exact stored content. Display formatting only; no AI rewriting or
            live website fetch.
          </p>
          <div className="source-viewer-meta">
            <span>{new Date(source.fetchedAt).toLocaleString()}</span>
            <span>
              {source.captureMethod === "chrome"
                ? "Captured in Chrome"
                : source.imported
                  ? "Imported HTML"
                  : "Fetched & cached"}
            </span>
            <span>{source.text.length.toLocaleString()} characters</span>
          </div>
          <details>
            <summary>Source identity & checksum</summary>
            <dl>
              <dt>Source ID</dt>
              <dd>{source.id}</dd>
              <dt>SHA-256</dt>
              <dd>{source.hash}</dd>
              <dt>Cached file</dt>
              <dd>{source.filename}</dd>
            </dl>
          </details>
        </header>
        <div
          className="source-viewer-tabs"
          role="tablist"
          aria-label="Stored source views"
        >
          {(
            [
              ["text", "Full text"],
              ["structured", "Sections & tables"],
              ["record", "Source record"],
              ["html", "Stored HTML"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              id={"source-tab-" + id}
              role="tab"
              aria-selected={tab === id}
              aria-controls="source-viewer-content"
              onClick={() => {
                setTab(id);
                setCopied(false);
              }}
            >
              {label}
            </button>
          ))}
          <button
            className="source-copy"
            disabled={tab === "html" && html === null}
            onClick={copy}
          >
            <Copy size={13} />
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <div
          id="source-viewer-content"
          className="source-viewer-content"
          role="tabpanel"
          aria-labelledby={"source-tab-" + tab}
          tabIndex={0}
        >
          {tab === "text" ? (
            <pre className="stored-source-text">{source.text}</pre>
          ) : tab === "record" ? (
            <pre className="stored-source-record">{record}</pre>
          ) : tab === "html" ? (
            error ? (
              <p role="alert" className="source-read-error">
                {error}
              </p>
            ) : html === null ? (
              <p>Reading cached HTML…</p>
            ) : (
              <pre className="stored-source-html">{html}</pre>
            )
          ) : (
            <div className="source-structured">
              <p className="muted small">
                These are the saved section and table fields. Full text contains
                the complete stored text.
              </p>
              {source.sections?.map((section, index) => (
                <section key={index}>
                  <h3>{section.heading}</h3>
                  <pre>{section.text}</pre>
                </section>
              ))}
              {source.tables?.map((table, index) => (
                <section key={"table-" + index}>
                  <h3>{table.caption || `Table ${index + 1}`}</h3>
                  <div className="source-table-scroll">
                    <table>
                      {!!table.headers.length && (
                        <thead>
                          <tr>
                            {table.headers.map((header, i) => (
                              <th key={i}>{header}</th>
                            ))}
                          </tr>
                        </thead>
                      )}
                      <tbody>
                        {table.rows
                          .filter(
                            (row, i) =>
                              i !== 0 ||
                              JSON.stringify(row) !==
                                JSON.stringify(table.headers),
                          )
                          .map((row, i) => (
                            <tr key={i}>
                              {row.map((cell, j) => (
                                <td key={j}>{cell}</td>
                              ))}
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              ))}
              {!source.sections?.length && !source.tables?.length && (
                <p>
                  No structured sections or tables were stored. Use Full text to
                  read the source.
                </p>
              )}
            </div>
          )}
        </div>
        <footer>
          <span>Read-only snapshot · stored data remains unchanged</span>
          <button className="button secondary" onClick={onClose}>
            Close
          </button>
        </footer>
      </section>
    </div>
  );
}
