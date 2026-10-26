import type { SharedSelection } from "../server/shared-source-index";
export function SharedResearchSummary({
  selection,
}: {
  selection?: SharedSelection | null;
}) {
  if (
    !selection ||
    !(
      selection.indexedChunks +
      selection.cachedChunks +
      selection.fallbackChunks
    )
  )
    return null;
  return (
    <details className="shared-research-summary">
      <summary>
        Last shared-source analysis: {selection.included} facts kept ·{" "}
        {selection.excluded} skipped
      </summary>
      <p>
        {selection.cachedChunks} saved analysis chunks reused ·{" "}
        {selection.indexedChunks} newly analysed. General and uncertain facts
        stay included. Original articles remain saved in full.
      </p>
      {selection.fallbackChunks > 0 && (
        <p>
          {selection.fallbackChunks} chunks used full item-specific reading
          because shared indexing was unavailable.
        </p>
      )}
      {selection.decisions.map((decision, at) => (
        <div className="shared-fact-decision" key={at}>
          <strong>{decision.included ? "Kept" : "Skipped"}</strong>{" "}
          {decision.detail}
          <small>{decision.reason}</small>
        </div>
      ))}
    </details>
  );
}
