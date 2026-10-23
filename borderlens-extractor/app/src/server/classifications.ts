import { readFileSync, writeFileSync, renameSync, existsSync } from "node:fs";
import {
  ClassificationFile,
  ClassificationOverride,
  type EffectiveClassification,
} from "../shared/classification.ts";

// This file is authoritative; SQLite family records only hold an effective view.
export class Classifications {
  data: ClassificationFile = { schemaVersion: 1, entries: {} };
  private text = "";
  constructor(public filename: string) {
    if (!this.reload()) this.persist();
  }
  reload() {
    if (!existsSync(this.filename)) {
      if (this.text) {
        this.data = { schemaVersion: 1, entries: {} };
        this.text = "";
        return true;
      }
      return false;
    }
    const text = readFileSync(this.filename, "utf8");
    if (text === this.text) return false;
    const data = ClassificationFile.parse(JSON.parse(text));
    this.data = data;
    this.text = text;
    return true;
  }
  effective(id: string): EffectiveClassification | undefined {
    const row = this.data.entries[id];
    if (row?.manual) return { ...row.manual, origin: "manual" };
    if (row?.research) return { ...row.research, origin: "research" };
  }
  set(
    id: string,
    origin: "manual" | "research",
    value: ClassificationOverride | null,
  ) {
    this.reload();
    if (value) {
      const entry = (this.data.entries[id] ||= {});
      entry[origin] = ClassificationOverride.parse(value);
    } else if (this.data.entries[id]) {
      delete this.data.entries[id][origin];
      if (!Object.keys(this.data.entries[id]).length)
        delete this.data.entries[id];
    }
    this.persist();
  }
  clear() {
    this.data = { schemaVersion: 1, entries: {} };
    this.persist();
  }
  private persist() {
    const value = ClassificationFile.parse(this.data);
    const text = JSON.stringify(value, null, 2) + "\n";
    writeFileSync(this.filename + ".tmp", text);
    renameSync(this.filename + ".tmp", this.filename);
    this.text = text;
  }
}
