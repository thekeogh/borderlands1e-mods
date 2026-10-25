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
    if (["Class mods", "Artifacts"].includes(category(r.path))) continue;
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
  return [...groups.values(), ...discoverCharacterFamilies(records)].sort(
    catalogueOrder,
  );
}
// Character equipment uses meaningful prefixes, rather than generic titles.
export function discoverCharacterFamilies(records: Map<string, Raw>): Family[] {
  const result = new Map<string, Family>();
  const characters = {
    1: "Roland",
    2: "Mordecai",
    3: "Lilith",
    4: "Brick",
  } as const;
  const rows = [...records.values()].filter(
    (r) => !/Default__|test_|delete/i.test(r.path),
  );
  const lookup = (p: string) => records.get(p.toLowerCase());
  const add = (
    cat: "Class mods" | "Artifacts",
    character: Family["character"],
    name: string,
    roots: string[],
    element?: Family["element"],
  ) => {
    const key = `${cat}|${character}|${name.toLowerCase()}`;
    const existing = result.get(key);
    if (existing) {
      existing.roots = [...new Set([...existing.roots, ...roots])];
      return;
    }
    result.set(key, {
      id: `${cat.toLowerCase().replace(/ /g, "-")}-${character!.toLowerCase()}-${name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${hash(key).slice(0, 6)}`,
      name,
      category: cat,
      subtype: cat,
      character,
      element,
      discoveryVersion: 1,
      aliases: [],
      roots: [...new Set(roots)],
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
    });
  };
  for (const item of rows.filter((r) => r.class?.endsWith(".ItemDefinition"))) {
    const p = unpack(item.properties),
      cat = category(item.path);
    const character =
      characters[p.RequiredCharacter as keyof typeof characters];
    if (!character || !["Class mods", "Artifacts"].includes(cat)) continue;
    const listPath = cat === "Class mods" ? p.BodyParts : p.RightSideParts;
    const list = typeof listPath === "string" ? lookup(listPath) : undefined;
    if (!list) continue;
    for (const rule of unpack(list.properties)?.WeightedParts || []) {
      // A disabled selection rule does not establish an obtainable family.
      const weight = rule.DefaultWeight;
      if (
        weight &&
        weight.BaseValueConstant === 0 &&
        !weight.BaseValueAttribute &&
        !weight.InitializationDefinition &&
        !(rule.Manufacturers || []).some(
          (m: any) =>
            m.DefaultWeight?.BaseValueConstant ||
            m.DefaultWeight?.InitializationDefinition ||
            m.DefaultWeight?.BaseValueAttribute,
        )
      )
        continue;
      const body = lookup(String(rule.Part));
      if (!body) continue;
      for (const prefix of unpack(body.properties)?.PrefixList || []) {
        const title = lookup(prefix),
          name = String(unpack(title?.properties)?.PartName || "")
            .replace(/<[^>]+>/g, "")
            .trim();
        if (!title || !name || name === "None") continue;
        const element =
          cat === "Artifacts"
            ? (["Incendiary", "Shock", "Corrosive", "Explosive"].find(
                (e) => name.toLowerCase() === e.toLowerCase(),
              ) as Family["element"])
            : undefined;
        if (cat === "Artifacts" && !element) continue;
        add(
          cat as "Class mods" | "Artifacts",
          character,
          cat === "Artifacts" ? `${name} Artifact` : name,
          [title.path, body.path, item.path],
          element,
        );
      }
    }
  }
  // DLC custom rewards use enabled fixed part collections, including zero-weight forced parts.
  for (const collection of rows.filter((r) =>
    r.class?.endsWith(".ItemPartListCollectionDefinition"),
  )) {
    const p = unpack(collection.properties),
      item = lookup(String(p.AssociatedItem));
    const character =
      characters[
        unpack(item?.properties)?.RequiredCharacter as keyof typeof characters
      ];
    if (
      !item ||
      !character ||
      category(item.path) !== "Class mods" ||
      !p.BodyPartData?.bEnabled
    )
      continue;
    for (const rule of p.BodyPartData.WeightedParts || []) {
      const body = lookup(String(rule.Part));
      if (!body) continue;
      for (const prefix of unpack(body.properties)?.PrefixList || []) {
        const title = lookup(prefix),
          name = String(unpack(title?.properties)?.PartName || "").trim();
        if (title && name && name !== "None")
          add("Class mods", character, name, [
            title.path,
            body.path,
            collection.path,
            item.path,
            ...rows
              .filter(
                (r) =>
                  r.class?.endsWith(".InventoryBalanceDefinition") &&
                  unpack(r.properties)?.PartListCollection === collection.path,
              )
              .map((r) => r.path),
          ]);
      }
    }
  }
  return [...result.values()];
}

// Preserve older captures and research; broad candidates must never export as items.
export function reconcileCharacterFamilies(store: Store) {
  const found = discoverCharacterFamilies(store.records);
  if (!found.length) return;
  const old = store.state.families.filter(
    (f) =>
      ["Class mods", "Artifacts"].includes(f.category) && !f.discoveryVersion,
  );
  const added = found.filter(
    (f) => !store.state.families.some((x) => x.id === f.id),
  );
  store.state.families.push(...added);
  for (const f of old) {
    f.supersededBy = found
      .filter((x) => x.category === f.category)
      .map((x) => x.id);
    f.status = "excluded";
    f.issue =
      "Replaced by character-specific families. Earlier research and output are retained privately.";
  }
  // Remove obsolete placeholders from pending work, without touching completed weapons.
  const r = store.state.run;
  const obsolete = new Set(old.map((f) => f.id));
  const previous = r.queue.slice(0, r.index).filter((id) => !obsolete.has(id));
  const pending = r.queue.slice(r.index).filter((id) => !obsolete.has(id));
  if (r.queue.length && added.length) {
    const queued = new Set([...previous, ...pending]);
    pending.push(...added.filter((f) => !queued.has(f.id)).map((f) => f.id));
    pending.sort((a, b) => catalogueOrder(store.family(a), store.family(b)));
  }
  r.queue = [...previous, ...pending];
  r.index = previous.length;
  if (r.currentId && obsolete.has(r.currentId)) {
    r.currentId = null;
    r.status = "paused";
    r.message =
      "Character families updated. Resume to build the new entries and remaining items.";
  }
  r.deferred = r.deferred.filter((id) => !obsolete.has(id));
  if (r.pendingFrom && obsolete.has(r.pendingFrom)) r.pendingFrom = null;
  store.state.families.sort(catalogueOrder);
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
    reconcileCharacterFamilies(store);
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
