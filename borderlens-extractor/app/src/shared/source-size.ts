/** Exact UTF-8 bytes of the saved text, excluding HTML, metadata and prompt instructions. */
export const storedTextBytes = (text: string) =>
  new TextEncoder().encode(text).byteLength;
export function sourceSize(bytes: number) {
  const tier =
    bytes < 8_000
      ? "small"
      : bytes < 32_000
        ? "medium"
        : bytes < 96_000
          ? "large"
          : "very-large";
  const label = {
    small: "Small",
    medium: "Medium",
    large: "Large",
    "very-large": "Very large",
  }[tier];
  const guidance = {
    small: "Compact reference.",
    medium: "Check for unrelated sections.",
    large: "Consider a targeted manual excerpt.",
    "very-large": "Strong candidate for a focused manual excerpt.",
  }[tier];
  const formatted =
    bytes < 1_000
      ? `${bytes} B`
      : bytes < 1_000_000
        ? `${(bytes / 1_000).toFixed(1)} KB`
        : `${(bytes / 1_000_000).toFixed(1)} MB`;
  return { tier, label, guidance, formatted };
}
