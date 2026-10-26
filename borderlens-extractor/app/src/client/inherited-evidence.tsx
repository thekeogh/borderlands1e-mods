import { BookOpen, ArrowUpRight } from "lucide-react";
import type { InheritedEvidence } from "../shared/research";
export function InheritedEvidenceList({
  items,
  manage,
}: {
  items: InheritedEvidence[];
  manage: (id: string) => void;
}) {
  if (!items.length) return null;
  return (
    <section
      className="inherited-evidence-list"
      aria-label="Inherited evidence"
    >
      <div className="inherited-evidence-heading">
        <BookOpen size={14} />
        <strong>Inherited evidence</strong>
        <span>{items.length}</span>
      </div>
      <p>
        Shared references are included automatically. Capture unsaved articles
        in their shared group.
      </p>
      {items.map((item) => (
        <div key={item.url} className="inherited-evidence-row">
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="inherited-evidence-title"
          >
            {item.title}
            <ArrowUpRight size={11} />
          </a>
          <span className="inherited-evidence-parents">
            from{" "}
            {item.parents.map((parent, index) => (
              <span key={parent.id}>
                {index > 0 && " · "}
                <button
                  className="inherited-evidence-parent"
                  title={"Manage shared evidence in " + parent.name}
                  onClick={() => manage(parent.id)}
                >
                  {parent.name}
                </button>
              </span>
            ))}
          </span>
          <span
            className={
              "inherited-evidence-capture " +
              (item.captured ? "is-saved" : "is-pending")
            }
          >
            {item.captured ? "Saved" : "Awaiting capture"}
          </span>
        </div>
      ))}
    </section>
  );
}
