import { SourceSize } from "./source-size";
import { evidenceSizeTotals } from "../shared/evidence-size";
import type { InheritedEvidence } from "../shared/research";
export function EvidenceSizeSummary({
  direct,
  inherited,
  pendingUrls,
  gameOnly,
}: {
  direct: { url: string; text: string }[];
  inherited: InheritedEvidence[];
  pendingUrls?: string[];
  gameOnly?: boolean;
}) {
  if (gameOnly)
    return (
      <div className="evidence-size-summary">
        <small>Game evidence only · saved sources excluded</small>
      </div>
    );
  const totals = evidenceSizeTotals(direct, inherited, pendingUrls);
  return (
    <div
      className="evidence-size-summary"
      aria-label="Evidence text totals"
      title="Stored UTF-8 text only. Included = dedicated + Always include. Auto is separate and may be selected. Never include is excluded. Actual AI payload depends on extracted facts, cache reuse, game data and instructions; this is not a transmitted-payload measurement."
    >
      <div className="evidence-size-included">
        <span>Included evidence</span>
        <SourceSize bytes={totals.included.bytes} />
        <small>
          {totals.included.count}{" "}
          {totals.included.count === 1 ? "source" : "sources"}
          {totals.included.missing > 0 &&
            ` · +${totals.included.missing} size unknown`}
        </small>
      </div>
      <div className="evidence-size-auto">
        <span>Auto · potential extra</span>
        <SourceSize bytes={totals.auto.bytes} />
        <small>
          {totals.auto.count} {totals.auto.count === 1 ? "source" : "sources"}
          {totals.auto.missing > 0 && ` · +${totals.auto.missing} size unknown`}
        </small>
      </div>
      <small className="evidence-size-note">
        Stored text · dedicated + Always include; Auto counted separately
      </small>
    </div>
  );
}
