import type { EvidenceFollowup } from "../server/saved-evidence";
import { SourceSite } from "./source-site";
export function EvidenceFollowupSummary({
  report,
}: {
  report?: EvidenceFollowup | null;
}) {
  if (!report?.requests.length) return null;
  return (
    <details className="shared-research-summary evidence-followup-summary">
      <summary>
        Additional saved evidence: {report.requests.length}{" "}
        {report.requests.length === 1 ? "request" : "requests"} ·{" "}
        {report.status === "supplied"
          ? report.matches.length +
            (report.matches.length === 1
              ? " match supplied"
              : " matches supplied")
          : "original draft retained"}
      </summary>
      <p>
        One optional request round. Only saved, permitted articles were
        searched; Never include sources stay excluded.
      </p>
      {report.requests.map((request, index) => (
        <div className="shared-fact-decision" key={index}>
          <strong>{request.topic}</strong>
          <small>{request.reason}</small>
        </div>
      ))}
      {report.missing.length > 0 && (
        <p>
          No saved match for: {report.missing.join("; ")}. Work continues with
          existing evidence.
        </p>
      )}
      {report.matches.map((match, index) => (
        <div className="shared-fact-decision" key={index}>
          <a href={match.url} target="_blank" rel="noreferrer">
            {match.title} ↗
          </a>{" "}
          <SourceSite url={match.url} />
          <small>
            {match.topic} ·{" "}
            {match.origin === "index"
              ? "Indexed fact"
              : "Original saved excerpt"}
            {report.status !== "supplied" ? " · not applied" : ""}
          </small>
          <blockquote>{match.fact.quote}</blockquote>
        </div>
      ))}
      {report.status === "writer_failed" && (
        <p>
          The additional writing pass was unavailable. The original draft was
          kept.
        </p>
      )}
      {report.status === "search_failed" && (
        <p>
          Extra context lookup was unavailable. The original draft was kept.
        </p>
      )}
      {!!report.ignoredRequests && (
        <p>
          Further requests were ignored because this item's request round was
          already used.
        </p>
      )}
    </details>
  );
}
