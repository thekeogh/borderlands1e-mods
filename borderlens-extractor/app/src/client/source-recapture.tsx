import { useState } from "react";
import { RotateCcw } from "lucide-react";
import { isManualTextUrl } from "../shared/manual-evidence";
export function SourceRecapture({
  url,
  title,
  disabled,
  run,
}: {
  url: string;
  title: string;
  disabled?: boolean;
  run: () => unknown | Promise<unknown>;
}) {
  const [pending, setPending] = useState(false);
  if (isManualTextUrl(url)) return null;
  return (
    <button
      type="button"
      className="button source-recapture"
      aria-label={"Recapture: " + title}
      title="Open this exact source in Chrome. Send new selections to replace its saved content; no build starts."
      disabled={disabled || pending}
      onClick={async () => {
        setPending(true);
        try {
          await run();
        } finally {
          setPending(false);
        }
      }}
    >
      <RotateCcw size={13} />
      {pending ? "Opening…" : "Recapture"}
    </button>
  );
}
