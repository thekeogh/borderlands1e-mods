import { ArrowUpToLine } from "lucide-react";
import { evidenceParent, scopeLabel } from "../shared/evidence-scopes";
import type { Family } from "../shared/models";
export function SourcePromote({
  owner,
  disabled,
  onMove,
}: {
  owner: Family;
  disabled?: boolean;
  onMove: () => void;
}) {
  const parent = evidenceParent(owner);
  if (!parent) return null;
  const label = `Move evidence to ${scopeLabel(parent)}`;
  return (
    <button
      type="button"
      className="source-promote-button"
      title={`${label}. Shared with its descendants on the next build.`}
      aria-label={label}
      disabled={disabled}
      onClick={onMove}
    >
      <ArrowUpToLine size={16} />
    </button>
  );
}
