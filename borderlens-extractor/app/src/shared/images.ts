import { z } from "zod";
export const ImagePath = z
  .string()
  .regex(/^[a-z0-9][a-z0-9_-]*\/[a-z0-9][a-z0-9_-]*\.(png|jpe?g|webp|avif)$/i);
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
