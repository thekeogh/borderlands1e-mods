import { ManualEvidenceIcon } from "./manual-evidence-icon";
import { SourceSite } from "./source-site";
import { isManualTextUrl } from "../shared/manual-evidence";
import { evidenceTotals, type EvidenceStats } from "../shared/evidence-stats";
export function EvidenceStatsSummary({
  stats,
  history = false,
}: {
  stats?: EvidenceStats;
  history?: boolean;
}) {
  if (!stats) return null;
  const total = evidenceTotals(stats);
  const latest = [...stats.events]
    .reverse()
    .find((e) => e.kind !== "analysis-cache" && e.phase === "write");
  const latestCall = [...stats.events]
    .reverse()
    .find((event) => event.kind !== "analysis-cache");
  return (
    <details
      className={"evidence-stats " + (history ? "is-history" : "")}
      aria-label={
        history ? "Saved evidence statistics" : "Live evidence statistics"
      }
    >
      <summary>
        <strong>AI evidence</strong> · {total.sources} unique sources submitted
        · {total.sends} source sends · {total.calls} CLI{" "}
        {total.calls === 1 ? "request" : "requests"}
        {latestCall && latestCall !== latest && (
          <span className="evidence-stats-writer">
            Latest AI input: {latestCall.sources.length} sources ·{" "}
            {latestCall.phase}
            {latestCall.kind === "response-cache"
              ? " · saved response, 0 submitted"
              : ""}
          </span>
        )}
        {latest && (
          <span className="evidence-stats-writer">
            Latest writing payload: {latest.sources.length} sources
            {latest.kind === "response-cache"
              ? " · saved response, 0 submitted"
              : ""}
          </span>
        )}
        <span className="evidence-stats-cache">
          Saved analysis: {total.cachedSources} sources reused · Cached AI
          responses: {total.cachedResponses}
        </span>
      </summary>
      <p>
        {stats.name} · Reading/indexing: {total.readSends} sends · Writing:{" "}
        {total.writeSends} sends · Other checks/repairs:{" "}
        {total.sends - total.readSends - total.writeSends} sends
      </p>
      <p>
        Saved analysis reused: {total.cachedSources} sources /{" "}
        {total.cachedChunks} chunks · Cached AI responses:{" "}
        {total.cachedResponses}
      </p>
      <p className="muted">
        Counted at CLI submission from the actual source payload. Repeated
        requests count again. Saved analysis still uses input when its selected
        facts are sent to the writer. Prompt sizes exclude schema/wrapper
        tokens; provider token usage and internal retries aren't measured. Times
        cover CLI round trips.
      </p>
      {stats.events.length === 0 && <p>No AI requests or cache reuse yet.</p>}
      {stats.events.map((event, index) => (
        <div className="evidence-stats-event" key={index}>
          <strong>{event.label}</strong>
          <small>
            {event.phase} ·{" "}
            {event.kind === "submitted"
              ? `${event.sources.length} sources submitted to ${event.agent || "agent"}`
              : event.kind === "response-cache"
                ? "Saved AI response reused; 0 submitted"
                : `${event.sources.length} sources reused from saved analysis; 0 submitted`}{" "}
            · {new Date(event.at).toLocaleTimeString()}
            {event.promptBytes != null &&
              ` · ${(event.promptBytes / 1000).toFixed(1)} KB prompt`}
            {event.promptCharacters != null &&
              ` · ${event.promptCharacters.toLocaleString()} characters`}
            {event.elapsedMs != null &&
              ` · ${(event.elapsedMs / 1000).toFixed(1)}s`}
          </small>
          {event.sources.length > 0 && (
            <ul>
              {event.sources.map((source) => (
                <li
                  key={source.url || source.id}
                  className={
                    isManualTextUrl(source.url)
                      ? "manual-evidence-surface"
                      : undefined
                  }
                >
                  {isManualTextUrl(source.url) && (
                    <ManualEvidenceIcon size={13} />
                  )}
                  {source.url && !isManualTextUrl(source.url) ? (
                    <a href={source.url} target="_blank" rel="noreferrer">
                      {source.title} ↗
                    </a>
                  ) : (
                    source.title
                  )}
                  {source.url && isManualTextUrl(source.url) && (
                    <SourceSite url={source.url} />
                  )}
                  <span className={"evidence-source-mode is-" + source.mode}>
                    {source.mode === "always"
                      ? "Always include"
                      : source.mode === "auto"
                        ? "Auto"
                        : source.mode === "never"
                          ? "Never include"
                          : "Direct"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </details>
  );
}
