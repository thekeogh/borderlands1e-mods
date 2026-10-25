import React, { useRef } from "react";
import { RotateCcw, ChevronDown } from "lucide-react";
export function RebuildActions({
  saved,
  disabled,
  run,
}: {
  saved?: { available: boolean; reason: string };
  disabled: boolean;
  run: (action: string) => void;
}) {
  const menu = useRef<HTMLDetailsElement>(null);
  const choose = (action: string) => {
    if (menu.current) menu.current.open = false;
    run(action);
  };
  return (
    <div className="rebuild-actions">
      <button
        className="button secondary"
        disabled={disabled}
        onClick={() =>
          choose(saved?.available ? "rebuild-saved" : "rebuild-fresh")
        }
        title={
          saved?.available
            ? saved.reason
            : "Fetch current sources, read their facts and rebuild the item."
        }
      >
        <RotateCcw size={15} />
        {saved?.available
          ? "Rebuild from saved sources"
          : "Rebuild from fresh sources"}
      </button>
      <details ref={menu} className="rebuild-options">
        <summary aria-label="Rebuild options">
          <ChevronDown size={15} />
        </summary>
        <div className="rebuild-options-panel">
          <button
            disabled={disabled || !saved?.available}
            title={saved?.reason}
            onClick={() => choose("rebuild-saved")}
          >
            <strong>Rebuild from saved sources</strong>
            <span>Reuse saved pages and facts. Write and validate again.</span>
          </button>
          <button disabled={disabled} onClick={() => choose("rebuild-fresh")}>
            <strong>Rebuild from fresh sources</strong>
            <span>Fetch sources again, read their facts, then rebuild.</span>
          </button>
        </div>
      </details>
    </div>
  );
}
