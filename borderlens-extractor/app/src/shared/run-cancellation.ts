export class RunCancelledError extends Error {
  constructor() {
    super("Run cancelled by the user.");
    this.name = "RunCancelledError";
  }
}
export const isRunCancelled = (error: unknown) =>
  error instanceof RunCancelledError ||
  (error instanceof Error && error.name === "RunCancelledError");
