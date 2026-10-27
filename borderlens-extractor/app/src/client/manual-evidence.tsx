import { SourceSize } from "./source-size";
import { ManualEvidenceIcon } from "./manual-evidence-icon";
import { useState } from "react";
export function ManualEvidenceForm({
  disabled,
  add,
}: {
  disabled?: boolean;
  add: (value: { label: string; text: string }) => Promise<boolean>;
}) {
  const [label, setLabel] = useState(""),
    [text, setText] = useState(""),
    [pending, setPending] = useState(false);
  return (
    <form
      className="manual-evidence-form"
      aria-label="Add text evidence"
      onSubmit={async (event) => {
        event.preventDefault();
        setPending(true);
        try {
          if (await add({ label, text })) {
            setLabel("");
            setText("");
          }
        } finally {
          setPending(false);
        }
      }}
    >
      <h3>
        <ManualEvidenceIcon size={18} /> Add text evidence
      </h3>
      <p>
        Paste just the passage you want AI to use. Saved for this item’s next
        build; no page fetch or build starts.
      </p>
      <label>
        Source / name <span className="muted">(optional)</span>
        <input
          aria-label="Text evidence label"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          maxLength={160}
          disabled={disabled || pending}
          placeholder="e.g. Berserk — corrosive effects"
        />
      </label>
      <label>
        Evidence text
        <textarea
          aria-label="Pasted evidence text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={8}
          maxLength={100000}
          required
          disabled={disabled || pending}
          placeholder="Paste the relevant text here…"
        />
      </label>
      {!!text.trim() && <SourceSize text={text.trim()} />}
      <small>
        Plain text. Your label is for reference, not evidence of a fact. To
        replace a full page, set its source to Never include.
      </small>
      <button
        className="button secondary"
        type="submit"
        disabled={disabled || pending || !text.trim()}
      >
        {pending ? "Adding…" : "Add text evidence"}
      </button>
    </form>
  );
}
