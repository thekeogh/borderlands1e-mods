import { NotebookPen } from "lucide-react";
export function ManualEvidenceIcon({ size = 16 }: { size?: number }) {
  return (
    <NotebookPen
      size={size}
      className="manual-evidence-icon"
      aria-hidden="true"
    />
  );
}
