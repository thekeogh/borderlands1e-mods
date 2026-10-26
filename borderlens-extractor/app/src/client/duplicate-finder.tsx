import { useEffect, useRef, useState } from "react";
import { Copy, Search, Trash2, X } from "lucide-react";
import type { Family } from "../shared/models";
import type { DuplicateMatch, DuplicateResults } from "../shared/duplicates";
import { GameDataTab } from "./game-data";
async function get(url: string) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok)
    throw new Error(data.error || "Could not find possible matches.");
  return data;
}
export function DuplicateFinder({
  family,
  busy,
  remove,
}: {
  family: Family;
  busy: boolean;
  remove: () => Promise<unknown>;
}) {
  const [result, setResult] = useState<DuplicateResults | null>(null),
    [error, setError] = useState(""),
    [searching, setSearching] = useState(false),
    [inspect, setInspect] = useState<DuplicateMatch | null>(null);
  useEffect(() => {
    setResult(null);
    setError("");
    setInspect(null);
  }, [family.id]);
  return (
    <section
      className="duplicate-finder"
      aria-label="Possible duplicate lookup"
    >
      <button
        className="button secondary"
        disabled={searching}
        onClick={async () => {
          setSearching(true);
          setError("");
          try {
            setResult(await get(`/api/items/${family.id}/duplicates`));
          } catch (error: any) {
            setError(error.message);
          } finally {
            setSearching(false);
          }
        }}
      >
        <Search size={14} />
        {searching ? "Finding matches…" : "Find duplicates"}
      </button>
      <p>
        Possible matches only. Inspect their game definitions before deciding.
      </p>
      {error && <p role="alert">{error}</p>}
      {result && (
        <>
          <strong>
            {result.total
              ? `${result.total} possible ${result.total === 1 ? "match" : "matches"}`
              : "No possible matches found."}
          </strong>
          {result.total > result.matches.length && (
            <p>Showing the {result.matches.length} closest matches.</p>
          )}
          {result.matches.map((match) => (
            <div className="duplicate-match" key={match.id}>
              <strong>
                <Copy size={12} /> {match.name}
              </strong>
              <small>
                {[match.category, match.character].filter(Boolean).join(" · ")}
              </small>
              <ul>
                {match.reasons.map((reason, index) => (
                  <li key={index}>{reason}</li>
                ))}
              </ul>
              <button className="text-button" onClick={() => setInspect(match)}>
                Inspect {match.name}
              </button>
            </div>
          ))}
          {result.matches.length > 0 && (
            <>
              <button
                className="button remove-item-button"
                disabled={busy}
                onClick={() => void remove()}
              >
                <Trash2 size={14} />
                Remove this Needs review item
              </button>
              <p>
                Removes {family.name} only. Restore it later from Removed items.
              </p>
            </>
          )}
        </>
      )}
      {inspect && (
        <DuplicateInspector match={inspect} onClose={() => setInspect(null)} />
      )}
    </section>
  );
}
function DuplicateInspector({
  match,
  onClose,
}: {
  match: DuplicateMatch;
  onClose: () => void;
}) {
  const ref = useRef<HTMLElement>(null),
    [detail, setDetail] = useState<any>(null),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    void get(`/api/items/${match.id}`)
      .then((value) => {
        if (active) setDetail(value);
      })
      .catch((error) => {
        if (active) setError(error.message);
      });
    return () => {
      active = false;
    };
  }, [match.id]);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    ref.current?.querySelector<HTMLButtonElement>("button")?.focus();
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
      if (event.key === "Tab") {
        const controls = [
          ...ref.current!.querySelectorAll<HTMLElement>(
            'button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),[tabindex="0"]',
          ),
        ].filter((el) => el.getClientRects().length);
        if (event.shiftKey && document.activeElement === controls[0]) {
          event.preventDefault();
          controls.at(-1)?.focus();
        } else if (
          !event.shiftKey &&
          document.activeElement === controls.at(-1)
        ) {
          event.preventDefault();
          controls[0]?.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("keydown", key);
      if (previous?.isConnected) previous.focus();
    };
  }, []);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section
        ref={ref}
        className="duplicate-inspector"
        role="dialog"
        aria-modal="true"
        aria-labelledby="duplicate-inspector-title"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          className="close-modal"
          aria-label="Close duplicate inspection"
          onClick={onClose}
        >
          <X size={20} />
        </button>
        <h2 id="duplicate-inspector-title">Possible match: {match.name}</h2>
        <p>
          {[match.category, match.character].filter(Boolean).join(" · ")} ·
          Read-only inspection
        </p>
        {error && <p role="alert">{error}</p>}
        {detail && (
          <>
            <p>
              {detail.websiteOutput?.summary ||
                detail.output?.summary ||
                "This item has not been built yet."}
            </p>
            <p>
              {detail.sources.length} saved articles ·{" "}
              {detail.family.roots.length} extracted family records
            </p>
          </>
        )}
        <GameDataTab familyId={match.id} />
      </section>
    </div>
  );
}
