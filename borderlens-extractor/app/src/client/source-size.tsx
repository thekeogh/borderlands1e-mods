import { sourceSize, storedTextBytes } from "../shared/source-size";
export function SourceSize({
  text,
  bytes,
}: {
  text?: string;
  bytes?: number | null;
}) {
  const value = text !== undefined ? storedTextBytes(text) : bytes;
  if (value === undefined || value === null)
    return (
      <span
        className="source-size is-unknown"
        title="No saved text size available. Capture this article first."
      >
        Size unavailable
      </span>
    );
  const size = sourceSize(value);
  const tooltip = `${value.toLocaleString()} bytes of stored UTF-8 text (not the HTML file). ${size.guidance} Size guide: Small <8 KB; Medium 8–32 KB; Large 32–96 KB; Very large ≥96 KB. These are document-size guides, not model limits or token counts. Actual AI input depends on selected facts, instructions and cache reuse.`;
  return (
    <span
      className={"source-size is-" + size.tier}
      title={tooltip}
      aria-label={`Stored text: ${size.formatted}, ${size.label}; ${value.toLocaleString()} bytes`}
    >
      <span>{size.formatted}</span>
      <span aria-hidden="true">·</span>
      <strong>{size.label}</strong>
    </span>
  );
}
