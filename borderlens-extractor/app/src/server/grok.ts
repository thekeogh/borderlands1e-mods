import { CliRunner } from "./cli-runner.ts";
export class GrokRunner extends CliRunner {
  constructor(
    dir: string,
    binary = process.env.BORDERLENS_GROK || "grok",
    timing: { timeoutMs?: number; heartbeatMs?: number } = {},
  ) {
    super(dir, binary, timing, "grok");
  }
}
