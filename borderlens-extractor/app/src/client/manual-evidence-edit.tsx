import { useState } from "react";
import { Pencil } from "lucide-react";
import type { Source } from "../shared/models";
import { SourceSize } from "./source-size";
export function ManualEvidenceEdit({
  source,
  ownerId,
  disabled,
  onSaved,
}: {
  source: Source;
  ownerId: string;
  disabled?: boolean;
  onSaved: () => void;
}) {
  const [editing, setEditing] = useState(false),
    [label, setLabel] = useState(source.title),
    [text, setText] = useState(source.text),
    [pending, setPending] = useState(false),
    [error, setError] = useState("");
  return (
    <div className="manual-evidence-editor">
      <button
        type="button"
        className="text-button manual-evidence-edit-button"
        aria-label={"Edit manual evidence: " + source.title}
        title="Edit manual evidence"
        disabled={disabled || pending}
        onClick={() => {
          setLabel(source.title);
          setText(source.text);
          setError("");
          setEditing(!editing);
        }}
      >
        <Pencil size={16} />
      </button>
      {editing && (
        <form
          aria-label={"Edit manual evidence: " + source.title}
          className="manual-evidence-edit-form"
          onSubmit={async (e) => {
            e.preventDefault();
            setPending(true);
            setError("");
            try {
              const response = await fetch(
                `/api/items/${encodeURIComponent(ownerId)}/text-evidence/${encodeURIComponent(source.id)}`,
                {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ label, text }),
                },
              );
              const result = await response.json();
              if (!response.ok)
                throw Error(result.error || "Could not save evidence.");
              setEditing(false);
              onSaved();
            } catch (e: any) {
              setError(e.message);
            } finally {
              setPending(false);
            }
          }}
        >
          <label>
            Source / name
            <input
              aria-label="Edit evidence label"
              value={label}
              maxLength={160}
              disabled={pending || disabled}
              onChange={(e) => setLabel(e.target.value)}
              autoFocus
            />
          </label>
          <label>
            Evidence text
            <textarea
              aria-label="Edit evidence text"
              rows={10}
              value={text}
              maxLength={100000}
              required
              disabled={pending || disabled}
              onChange={(e) => setText(e.target.value)}
            />
          </label>
          <SourceSize text={text.trim()} />
          <small>
            Saved for the next build. Shared entries update for all inheriting
            items; no build starts.
          </small>
          {error && <p role="alert">{error}</p>}
          <div>
            <button
              type="submit"
              className="button secondary"
              disabled={pending || disabled || !text.trim()}
            >
              {pending ? "Saving…" : "Save changes"}
            </button>
            <button
              type="button"
              className="button quiet"
              disabled={pending}
              onClick={() => setEditing(false)}
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
