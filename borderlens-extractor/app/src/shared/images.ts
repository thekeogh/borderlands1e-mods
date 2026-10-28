import { z } from "zod";
export const ImagePath = z
  .string()
  .refine(
    (value) =>
      /\.(png|jpe?g|webp|avif|gif)$/i.test(value) &&
      value
        .split("/")
        .every(
          (segment) =>
            segment.length > 0 &&
            !segment.startsWith(".") &&
            !/[\\:\u0000-\u001f\u007f]/.test(segment),
        ),
    "Choose a relative image path inside the local library.",
  );
export const ImageMatch = z
  .object({
    image: ImagePath.nullable(),
    method: z.enum([
      "exact",
      "normalized",
      "alias",
      "manual",
      "missing",
      "ambiguous",
    ]),
    candidates: z.array(ImagePath),
  })
  .strict();
export type ImageMatch = z.infer<typeof ImageMatch>;
export type ImageCoverage = {
  revision: string;
  files: string[];
  items: (ImageMatch & { id: string; name: string; category: string })[];
  summary: {
    total: number;
    matched: number;
    missing: number;
    ambiguous: number;
  };
};
export function imageUrl(image: string, revision = "") {
  return (
    "/api/images/file/" +
    image.split("/").map(encodeURIComponent).join("/") +
    (revision ? "?v=" + encodeURIComponent(revision) : "")
  );
}
