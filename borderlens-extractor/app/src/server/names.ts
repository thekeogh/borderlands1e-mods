import { existsSync, readFileSync, writeFileSync, renameSync } from "node:fs";
import {
  NameFile,
  NameOverride,
  type NameOverride as Override,
} from "../shared/names.ts";
/** Authoritative name corrections; original extraction stays unchanged. */
export class Names {
  data: { schemaVersion: 1; entries: Record<string, Override> } = {
    schemaVersion: 1,
    entries: {},
  };
  private text = "";
  constructor(public filename: string) {
    if (!this.reload()) this.persist();
  }
  reload() {
    if (!existsSync(this.filename)) {
      if (!this.text) return false;
      this.data = { schemaVersion: 1, entries: {} };
      this.text = "";
      return true;
    }
    const text = readFileSync(this.filename, "utf8");
    if (text === this.text) return false;
    this.data = NameFile.parse(JSON.parse(text));
    this.text = text;
    return true;
  }
  set(id: string, value: Override) {
    this.reload();
    const parsed = NameOverride.parse(value);
    if (
      this.data.entries[id]?.origin === "manual" &&
      parsed.origin !== "manual"
    )
      return false;
    this.data.entries[id] = parsed;
    this.persist();
    return true;
  }
  clear() {
    this.data = { schemaVersion: 1, entries: {} };
    this.persist();
  }
  private persist() {
    const text = JSON.stringify(NameFile.parse(this.data), null, 2) + "\n";
    writeFileSync(this.filename + ".tmp", text);
    renameSync(this.filename + ".tmp", this.filename);
    this.text = text;
  }
}
