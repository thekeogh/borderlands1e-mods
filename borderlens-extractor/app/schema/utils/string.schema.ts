import { z } from "zod";

export const line = z.string().regex(/^[^\r\n]*\S[^\r\n]*$/);