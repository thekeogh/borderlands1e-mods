import { isManualTextUrl } from "../shared/manual-evidence";
import { ManualEvidenceIcon } from "./manual-evidence-icon";
import { SourceSite } from "./source-site";
import { useState } from "react";
import { TriangleAlert } from "lucide-react";
import type { EvidenceRequestNotice } from "../shared/evidence-notice";
export function EvidenceRequestAlert({
  notice,
  dismiss,
  review,
}: {
  notice?: EvidenceRequestNotice | null;
  dismiss: (id: string) => Promise<void>;
  review: () => void;
}) {
  const [pending, setPending] = useState(false);
  if (!notice || notice.dismissedAt) return null;
  return (
    <section
      className="issue-card evidence-request-alert"
      aria-label="Requested evidence excluded"
    >
      <TriangleAlert size={20} />
      <div>
        <strong>AI requested evidence you excluded</strong>
        <p>
          Requested during a build on{" "}
          {new Date(notice.requestedAt).toLocaleString()}. These sources stayed
          excluded; processing continued.
        </p>
        <ul>
          {notice.blocked.map((match, index) => (
            <li
              key={index}
              className={
                isManualTextUrl(match.url)
                  ? "manual-evidence-surface"
                  : undefined
              }
            >
              {isManualTextUrl(match.url) && <ManualEvidenceIcon size={15} />}
              <strong>{match.topic}</strong> —{" "}
              {isManualTextUrl(match.url) ? (
                <>
                  {match.title} <SourceSite url={match.url} />
                </>
              ) : (
                <a href={match.url} target="_blank" rel="noreferrer">
                  {match.title} ↗
                </a>
              )}
              <small>{match.reason}</small>
            </li>
          ))}
        </ul>
        <p>
          To use this evidence, change its mode to Auto or Always include, then
          rebuild. Dismiss leaves your settings unchanged.
        </p>
        <div className="evidence-request-actions">
          <button className="text-button" onClick={review}>
            Review evidence
          </button>
          <button
            className="text-button"
            disabled={pending}
            onClick={() => {
              setPending(true);
              void dismiss(notice.id).finally(() => setPending(false));
            }}
          >
            {pending ? "Dismissing…" : "Dismiss notice"}
          </button>
        </div>
      </div>
    </section>
  );
}
