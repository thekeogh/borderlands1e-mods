import { catalogueOrder } from "../shared/taxonomy.ts";
import AdmZip from "adm-zip";
import path from "node:path";
import { Store, hash, atomic, HttpError } from "./store.ts";
import { now, type Raw, type Family, type Category } from "../shared/models.ts";
export function unpack(v: unknown): any {
  if (Array.isArray(v)) return v.map(unpack);
  if (v && typeof v === "object") {
    const x = v as any;
    if (x.$ref) return x.$ref;
    if (x.$type === "array") return x.items.map(unpack);
    if (x.$type === "struct")
      return Object.fromEntries(
        Object.entries(x.fields).map(([k, v]) => [k, unpack(v)]),
      );
    return Object.fromEntries(
      Object.entries(x).map(([k, v]) => [k, unpack(v)]),
    );
  }
  return v;
}
export function subtype(p: string) {
  const n = p.toLowerCase();
  for (const [key, name] of [
    ["patrol_smg", "SMGs"],
    ["repeater_pistol", "Repeater pistols"],
    ["machine_pistol", "Machine pistols"],
    ["revolver", "Revolvers"],
    ["sniper", "Sniper rifles"],
    ["shotgun", "Shotguns"],
    ["combat_rifle", "Combat rifles"],
    ["support_machinegun", "Machine guns"],
    ["rocket", "Rocket launchers"],
    ["grenade_launcher", "Grenade launchers"],
    ["alien", "Eridian weapons"],
  ] as const)
    if (n.includes(key)) return name;
  return "Other weapons";
}
export function category(p: string): Category {
  const n = p.toLowerCase();
  if (
    n.includes("commanddeck") ||
    n.includes("loyaltydeck") ||
    n.includes("classmod")
  )
    return "Class mods";
  if (n.includes("shield")) return "Shields";
  if (n.includes("tunercuff") || n.includes("grenademod"))
    return "Grenade mods";
  if (n.includes("elementalupgrade") || n.includes("artifact"))
    return "Artifacts";
  if (n.includes("weap_") || n.includes("weapon")) return "Weapons";
  return "Other equipment";
}
export function discover(records: Map<string, Raw>): Family[] {
  const groups = new Map<string, Family>();
  for (const r of records.values()) {
    if (
      !r.class?.match(/(?:Weapon|Item)NamePartDefinition$/) ||
      r.path.includes("Default__")
    )
      continue;
    if (
      !/(?:^|\.)(?:title[^.]*|titles)\./i.test(r.path) ||
      /prefix|delete|test_|editor/i.test(r.path)
    )
      continue;
    const p = unpack(r.properties);
    const name = String(p?.PartName || "")
      .replace(/<[^>]+>/g, "")
      .trim();
    if (!name || name === "None") continue;
    const cat = category(r.path),
      sub = cat === "Weapons" ? subtype(r.path) : cat,
      key = `${cat}|${sub}|${name.toLowerCase()}`;
    let f = groups.get(key);
    if (!f) {
      const id = `${sub.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "")}-${hash(key).slice(0, 6)}`;
      f = {
        id,
        name,
        category: cat,
        subtype: sub,
        aliases: [],
        roots: [],
        status: "queued",
        stage: "evidence",
        inputHash: "",
        issue: null,
        notes: "",
        gameOnly: false,
        sourceUrls: [],
        history: [],
        updatedAt: now(),
        manualOutput: false,
        revision: 0,
      };
      groups.set(key, f);
    }
    f.roots.push(r.path);
  }
  return [...groups.values()].sort(catalogueOrder);
}
export function importZip(store: Store, buffer: Buffer, filename: string) {
  if (["running", "pausing"].includes(store.state.run.status))
    throw new HttpError(
      409,
      "Pause processing before importing another capture.",
    );
  const id = hash(buffer);
  if (store.state.captures.some((c) => c.id === id))
    return { duplicate: true, families: store.state.families.length };
  let zip: AdmZip;
  try {
    zip = new AdmZip(buffer);
  } catch {
    throw new HttpError(400, "That file is not a readable ZIP archive.");
  }
  const entries = zip.getEntries();
  let total = 0;
  const names = new Set<string>();
  for (const e of entries) {
    const n = e.entryName;
    if (
      n.startsWith("/") ||
      n.includes("\\") ||
      n.split("/").includes("..") ||
      /^[A-Za-z]:/.test(n) ||
      names.has(n)
    )
      throw new HttpError(400, "Unsafe or duplicate ZIP entry.");
    names.add(n);
    total += e.header.size;
    if (total > 350 * 1024 * 1024 || entries.length > 10000)
      throw new HttpError(400, "Capture exceeds import limits.");
  }
  const manifests = entries.filter((e) =>
    /(?:^|\/)manifest\.json$/.test(e.entryName),
  );
  if (manifests.length !== 1)
    throw new HttpError(400, "Expected exactly one capture manifest.");
  let manifest: any;
  try {
    manifest = JSON.parse(manifests[0].getData().toString("utf8"));
  } catch {
    throw new HttpError(400, "Invalid manifest JSON.");
  }
  if (manifest.format_version !== 1 || !Array.isArray(manifest.chunks))
    throw new HttpError(400, "Unsupported capture format.");
  const prefix = manifests[0].entryName.slice(0, -"manifest.json".length),
    rows: Raw[] = [],
    ids = new Set<string>(),
    chunkNames = new Set<string>();
  for (const chunk of manifest.chunks) {
    if (
      typeof chunk.file !== "string" ||
      !/^data\/[A-Za-z0-9_-]+\.json$/.test(chunk.file) ||
      chunkNames.has(chunk.file)
    )
      throw new HttpError(400, "Unsafe or duplicate manifest chunk path.");
    chunkNames.add(chunk.file);
    const e = zip.getEntry(prefix + chunk.file);
    if (!e) throw new HttpError(400, `Missing chunk: ${chunk.file}`);
    let raw: Buffer;
    try {
      raw = e.getData();
    } catch {
      throw new HttpError(400, `Invalid ZIP checksum: ${chunk.file}`);
    }
    if (hash(raw) !== chunk.sha256)
      throw new HttpError(400, `Checksum mismatch: ${chunk.file}`);
    let data: any;
    try {
      data = JSON.parse(raw.toString("utf8"));
    } catch {
      throw new HttpError(400, `Invalid JSON: ${chunk.file}`);
    }
    if (!Array.isArray(data) || data.length !== chunk.records)
      throw new HttpError(400, "Chunk record count mismatch.");
    for (const r of data) {
      if (
        r?.record_type === "object" &&
        (typeof r.class !== "string" ||
          !r.properties ||
          Array.isArray(r.properties) ||
          typeof r.properties !== "object")
      )
        throw new HttpError(400, "Invalid object definition.");
      if (
        !r ||
        typeof r.id !== "string" ||
        typeof r.path !== "string" ||
        typeof r.record_type !== "string" ||
        ids.has(r.id)
      )
        throw new HttpError(400, "Invalid or duplicate record identity.");
      ids.add(r.id);
      rows.push(r);
    }
  }
  const before = new Map(store.state.families.map((f) => [f.id, f]));
  atomic(path.join(store.dir, "captures", id + ".zip"), buffer);
  const previousState = structuredClone(store.state);
  store.db.exec("BEGIN IMMEDIATE");
  try {
    const insert = store.db.prepare(
      "INSERT OR REPLACE INTO raw VALUES(?,?,?,?,?)",
    );
    for (const r of rows)
      insert.run(id, r.id, r.path, r.class || "", JSON.stringify(r));
    store.state.captures.push({
      id,
      name: path.basename(filename),
      version: String(manifest.extractor_version),
      importedAt: now(),
      objects: rows.filter((r) => r.record_type === "object").length,
      manifest,
    });
    store.reloadRecords();
    const found = discover(store.records);
    for (const candidate of found) {
      const old = before.get(candidate.id);
      if (old) Object.assign(candidate, { ...old, roots: candidate.roots });
    }
    for (const old of store.state.families)
      if (!found.some((f) => f.id === old.id)) found.push(old);
    store.state.families = found.sort(catalogueOrder);
    if (store.state.run.status === "idle")
      store.state.run.message =
        "Capture imported. Start the catalogue or build one item first.";
    store.save();
    store.db.exec("COMMIT");
  } catch (error) {
    store.db.exec("ROLLBACK");
    store.state = previousState;
    store.reloadRecords();
    throw error;
  }
  store.activity(
    `Imported ${filename}: ${rows.filter((r) => r.record_type === "object").length.toLocaleString()} data objects; ${store.state.families.length} family candidates.`,
    "import",
  );
  return {
    duplicate: false,
    objects: rows.length,
    families: store.state.families.length,
  };
}
