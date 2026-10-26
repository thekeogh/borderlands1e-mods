import { useState } from "react";
import type { Family } from "../shared/models";
export function ManualNameEditor({
  family,
  disabled,
  save,
}: {
  family: Family;
  disabled: boolean;
  save: (name: string) => Promise<boolean>;
}) {
  const [open, setOpen] = useState(false),
    [name, setName] = useState(family.name);
  if (!open)
    return (
      <button
        type="button"
        className="text-button manual-name-link"
        disabled={disabled}
        onClick={() => {
          setName(family.name);
          setOpen(true);
        }}
      >
        Edit item name
      </button>
    );
  return (
    <form
      className="manual-name-form"
      onSubmit={async (event) => {
        event.preventDefault();
        if (await save(name)) setOpen(false);
      }}
    >
      <label>
        Item name
        <input
          aria-label="Item name"
          type="text"
          value={name}
          maxLength={160}
          required
          autoFocus
          disabled={disabled}
          onFocus={(event) => event.currentTarget.select()}
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      <p className="muted small">
        Your name takes priority over AI and game data.
      </p>
      <div className="manual-name-actions">
        <button
          type="submit"
          className="button secondary"
          disabled={disabled || !name.trim()}
        >
          Save name
        </button>
        <button
          type="button"
          className="text-button"
          disabled={disabled}
          onClick={() => setOpen(false)}
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
