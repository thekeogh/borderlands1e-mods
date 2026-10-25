import React from "react";
import type { Family } from "../shared/models";

/** Counts follow the currently visible group, including search/status filters. */
export function GroupStatus({ items }: { items: Pick<Family, "status">[] }) {
  const counts = { done: 0, blocked: 0, queued: 0, running: 0, excluded: 0 };
  for (const item of items) counts[item.status]++;
  const label = [
    `${counts.done} complete`,
    `${counts.blocked} need attention`,
    `${counts.queued} waiting`,
    `${counts.running} processing`,
    ...(counts.excluded ? [`${counts.excluded} removed`] : []),
    `${items.length} total`,
  ].join(" · ");
  return (
    <span
      className={`group-status${counts.blocked ? " has-attention" : ""}${counts.done === items.length && items.length ? " is-complete" : ""}`}
      role="img"
      aria-label={label}
      title={label}
    >
      <span
        className={`group-status-done${counts.done ? "" : " is-zero"}`}
        aria-hidden="true"
      >
        {counts.done}
      </span>
      <span className="group-status-divider" aria-hidden="true">
        /
      </span>
      <span
        className={`group-status-attention${counts.blocked ? "" : " is-zero"}`}
        aria-hidden="true"
      >
        {counts.blocked}
      </span>
      <span className="group-status-divider" aria-hidden="true">
        /
      </span>
      <span className="group-status-total" aria-hidden="true">
        {items.length}
      </span>
    </span>
  );
}
