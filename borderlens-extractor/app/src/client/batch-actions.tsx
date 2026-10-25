import React, { useRef } from "react";
import { Play, Pause, ChevronDown } from "lucide-react";
import type { Run } from "../shared/models";
export function BatchActions({
  run,
  busy,
  disabled,
  action,
}: {
  run: Run;
  busy: boolean;
  disabled: boolean;
  action: (
    action: "start" | "pause" | "resume",
    sourceMode?: "saved" | "fresh",
  ) => void;
}) {
  const menu = useRef<HTMLDetailsElement>(null);
  const checkpoint = run.status === "paused" || run.status === "blocked";
  const mode = run.sourceMode === "fresh" ? "fresh" : "saved";
  const start = (mode: "saved" | "fresh") => {
    if (menu.current) menu.current.open = false;
    action("start", mode);
  };
  return (
    <div
      className={`rebuild-actions batch-actions${busy ? " is-running" : ""}`}
    >
      <button
        className={`button ${busy ? "pause-button" : "primary"}`}
        disabled={disabled || run.status === "pausing"}
        onClick={() =>
          busy ? action("pause") : checkpoint ? action("resume") : start(mode)
        }
      >
        {busy ? <Pause size={16} /> : <Play size={16} fill="currentColor" />}
        {run.status === "pausing"
          ? "Pausing…"
          : busy
            ? "Pause"
            : checkpoint
              ? "Resume"
              : `Start from ${mode} sources`}
      </button>
      <details ref={menu} className="rebuild-options batch-options">
        <summary
          aria-label="Batch source options"
          aria-disabled={busy || disabled}
          onClick={(event) => {
            if (busy || disabled) event.preventDefault();
          }}
        >
          <ChevronDown size={15} />
        </summary>
        <div className="rebuild-options-panel">
          <button disabled={busy || disabled} onClick={() => start("saved")}>
            <strong>Start from saved sources</strong>
            <span>
              Build unfinished items using saved pages and facts. Fetch sources
              for items with none.
            </span>
          </button>
          <button disabled={busy || disabled} onClick={() => start("fresh")}>
            <strong>Start from fresh sources</strong>
            <span>
              Build unfinished items after refreshing their sources and reading
              their facts again.
            </span>
          </button>
          {checkpoint && (
            <p className="batch-checkpoint-note">
              Resume keeps your saved checkpoint. Starting a new batch restarts
              unfinished items.
            </p>
          )}
        </div>
      </details>
    </div>
  );
}
