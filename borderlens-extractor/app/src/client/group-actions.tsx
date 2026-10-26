import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MoreHorizontal } from "lucide-react";
import {
  scopeLabel,
  scopeMatches,
  type EvidenceScope,
} from "../shared/evidence-scopes";
import type { Family } from "../shared/models";
export type GroupAction = "rebuild-saved" | "rebuild-fresh" | "discover";
export function GroupActions({
  scope,
  families,
  busy,
  run,
}: {
  scope: EvidenceScope;
  families: Family[];
  busy: boolean;
  run: (scope: EvidenceScope, action: GroupAction) => void;
}) {
  const button = useRef<HTMLButtonElement>(null),
    panel = useRef<HTMLDivElement>(null),
    id = useId(),
    [position, setPosition] = useState<{ left: number; top: number } | null>(
      null,
    );
  const name = scopeLabel(scope),
    count = families.filter(
      (family) =>
        family.status !== "excluded" &&
        !family.supersededBy &&
        scopeMatches(scope, family),
    ).length;
  const close = () => {
    setPosition(null);
    button.current?.focus();
  };
  useEffect(() => {
    if (!position) return;
    panel.current
      ?.querySelector<HTMLButtonElement>("button:not(:disabled)")
      ?.focus();
    const outside = (event: PointerEvent) => {
      if (
        !panel.current?.contains(event.target as Node) &&
        !button.current?.contains(event.target as Node)
      )
        setPosition(null);
    };
    const dismiss = () => setPosition(null);
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
      } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
        const items = [
          ...panel.current!.querySelectorAll<HTMLButtonElement>(
            "button:not(:disabled)",
          ),
        ];
        if (!items.length) return;
        event.preventDefault();
        const current = items.indexOf(
          document.activeElement as HTMLButtonElement,
        );
        const next =
          event.key === "Home"
            ? 0
            : event.key === "End"
              ? items.length - 1
              : event.key === "ArrowDown"
                ? (current + 1) % items.length
                : (current - 1 + items.length) % items.length;
        items[next].focus();
      }
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", key);
    window.addEventListener("resize", dismiss);
    window.addEventListener("scroll", dismiss, true);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", key);
      window.removeEventListener("resize", dismiss);
      window.removeEventListener("scroll", dismiss, true);
    };
  }, [!!position]);
  return (
    <>
      <button
        ref={button}
        className="group-actions-button"
        aria-label={"Batch actions for " + name}
        title={"Batch actions for " + name}
        aria-haspopup="menu"
        aria-expanded={!!position}
        aria-controls={position ? id : undefined}
        onClick={() => {
          if (position) {
            close();
            return;
          }
          const bounds = button.current!.getBoundingClientRect();
          setPosition({
            left: Math.max(
              10,
              Math.min(bounds.right + 8, window.innerWidth - 340),
            ),
            top: Math.max(10, Math.min(bounds.top, window.innerHeight - 350)),
          });
        }}
      >
        <MoreHorizontal size={16} />
      </button>
      {position &&
        createPortal(
          <div
            ref={panel}
            id={id}
            role="menu"
            aria-label={"Batch actions for " + name}
            className="group-actions-panel"
            style={position}
          >
            <div className="group-actions-heading">
              <strong>{name}</strong>
              <span>
                {count} {count === 1 ? "item" : "items"}
              </span>
            </div>
            {(
              [
                {
                  action: "rebuild-saved",
                  title: "Rebuild from saved sources",
                  description:
                    "Reuse saved evidence. Fetch sources for children with none.",
                },
                {
                  action: "rebuild-fresh",
                  title: "Rebuild from fresh sources",
                  description:
                    "Refresh sources, then rebuild every item in this group.",
                },
                {
                  action: "discover",
                  title: "Fetch evidence URLs only",
                  description:
                    "Find individual links for this group; keep shared references inherited.",
                },
              ] as const
            ).map((option) => (
              <button
                role="menuitem"
                key={option.action}
                disabled={busy || !count}
                onClick={() => {
                  close();
                  run(scope, option.action);
                }}
              >
                <strong>{option.title}</strong>
                <span>{option.description}</span>
              </button>
            ))}
            <p>
              {busy
                ? "Pause the current job before starting a group batch."
                : "Applies to every active child, including completed items. Sidebar filters do not limit this batch."}
            </p>
          </div>,
          document.body,
        )}
    </>
  );
}
