import { CliRunner } from "./cli-runner.ts";
export class CodexRunner extends CliRunner {
  constructor(
    dir: string,
    binary = process.env.BORDERLENS_CODEX || "codex",
    timing: { timeoutMs?: number; heartbeatMs?: number } = {},
  ) {
    super(dir, binary, timing, "codex");
  }
}
