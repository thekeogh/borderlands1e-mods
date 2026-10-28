import { ProjectBackupActions, readRestoredBackupUI } from "./project-backup";
import { SourceRecapture } from "./source-recapture";
import { EvidenceSizeSummary } from "./evidence-size-summary";
import { ManualEvidenceEdit } from "./manual-evidence-edit";
import { SourceSize } from "./source-size";
import { ManualEvidenceIcon } from "./manual-evidence-icon";
import { ManualEvidenceForm } from "./manual-evidence";
import { isManualTextUrl } from "../shared/manual-evidence";
import type { EvidenceStats } from "../shared/evidence-stats";
import { EvidenceStatsSummary } from "./evidence-stats";
import type { EvidenceRequestNotice } from "../shared/evidence-notice";
import { EvidenceRequestAlert } from "./evidence-request-alert";
import { ManualNameEditor } from "./manual-name";
import { ManualTypePicker } from "./manual-type";
import { DuplicateFinder } from "./duplicate-finder";
import { EvidenceFollowupSummary } from "./evidence-followup";
import { SharedResearchSummary } from "./shared-research-summary";
import { SourcePromote } from "./source-promote";
import { SourceSite } from "./source-site";
import { GroupActions, type GroupAction } from "./group-actions";
import { scopeLabel } from "../shared/evidence-scopes";
import { GameDataTab } from "./game-data";
import { InheritedEvidenceList } from "./inherited-evidence";
import { sourceKey, type InheritedEvidence } from "../shared/research";
import { SharedSources } from "./shared-sources";
import type { EvidenceScope } from "../shared/evidence-scopes";
import { familyTreePath, revealTreePath, stepTree } from "./tree-navigation";
import { GroupStatus } from "./group-status";
import { BatchActions } from "./batch-actions";
import { RebuildActions } from "./rebuild-actions";
import { ItemImage, ImageCoveragePanel } from "./item-images";
import type { ImageCoverage, ImageMatch } from "../shared/images";
import { acquisitionSources } from "../shared/acquisition";
import { agentNames } from "../shared/agents";
import { SourceViewer } from "./source-viewer";
import { useChromeHelper, ChromeHelperSetup } from "./chrome-helper";
import { CATALOGUE_SCHEMA_VERSION } from "../shared/versions";
import { catalogueGroup, classificationNote } from "../shared/taxonomy";
import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Search,
  Upload,
  Play,
  Pause,
  ArrowUpRight,
  ChevronDown,
  ChevronRight,
  ChevronsDownUp,
  ChevronsUpDown,
  Check,
  FileJson,
  BookOpen,
  Database,
  Settings2,
  Download,
  RefreshCw,
  RotateCcw,
  Trash2,
  Undo2,
  ArrowRight,
  Target,
  TriangleAlert,
  Layers,
  Chrome,
  Plus,
  CheckCircle2,
  Clock,
  Activity,
  X,
  Link2,
} from "lucide-react";
import {
  researchProviders,
  providerForUrl,
  type ResearchReport,
  type ExcludedSource,
} from "../shared/research";
import type {
  Project,
  Family,
  Packet,
  Source,
  PublicEntry,
  Draft,
} from "../shared/models";
import "./style.css";
type Detail = {
  extractedDlc: import("../shared/content").ItemDLC;
  finalValidation: {
    checkedAt: string;
    compilerVersion: string;
    warnings?: string[];
  } | null;
  image: ImageMatch;
  savedRebuild: { available: boolean; reason: string };
  websiteOutput: import("../shared/website").WebsiteEntry | null;
  parts: import("../shared/models").PartDefinition[];
  researchAudit: any;
  evidenceStatsHistory?: EvidenceStats[];
  evidenceRequestNotice?: EvidenceRequestNotice | null;
  evidenceFollowup?: import("../server/saved-evidence").EvidenceFollowup;
  sharedSourceSelection?: import("../server/shared-source-index").SharedSelection;
  research: ResearchReport | null;
  family: Family;
  packet: Packet | null;
  sources: Source[];
  inheritedEvidence?: InheritedEvidence[];
  excludedSources?: ExcludedSource[];
  output: PublicEntry | null;
  draft: Draft | null;
  provenance: any;
  matches: any;
};
async function request<T = any>(
  url: string,
  body?: unknown,
  method = "POST",
  options: RequestInit = {},
): Promise<T> {
  const r = await fetch(url, {
    ...options,
    ...(body === undefined
      ? {}
      : {
          method,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }),
  });
  const value = await r.json();
  if (!r.ok) throw new Error(value.error || "Request failed");
  return value;
}
const stepLabels = {
  evidence: "Read game data",
  sources: "Research sources",
  draft: "Write the entry",
  validate: "Validate final JSON",
  complete: "Ready to export",
};
const statusLabel = {
  queued: "Queued",
  running: "Processing",
  blocked: "Needs attention",
  done: "Ready",
  excluded: "Removed",
};
function App() {
  const [restoredUI] = useState(readRestoredBackupUI);
  useEffect(() => {
    localStorage.removeItem("borderlens.restored-ui");
  }, []);
  const [state, setState] = useState<Project | null>(null),
    [images, setImages] = useState<ImageCoverage | null>(null),
    [selected, setSelected] = useState(
      restoredUI?.selection ||
        localStorage.getItem("borderlens.selection") ||
        "",
    ),
    [detail, setDetail] = useState<Detail | null>(null),
    [tab, setTab] = useState(restoredUI?.tab || "preview"),
    [view, setView] = useState(restoredUI?.view || "catalogue"),
    [query, setQuery] = useState(restoredUI?.query || ""),
    [filter, setFilter] = useState(restoredUI?.filter || "all"),
    [collapsed, setCollapsed] = useState<Record<string, boolean>>(() => {
      try {
        return (
          restoredUI?.groups ||
          JSON.parse(localStorage.getItem("borderlens.groups") || "{}")
        );
      } catch {
        return {};
      }
    }),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [working, setWorking] = useState(false),
    [connected, setConnected] = useState(true),
    [settingsOpen, setSettingsOpen] = useState(false),
    [sharedScope, setSharedScope] = useState<EvidenceScope | null>(null),
    [returnSourceId, setReturnSourceId] = useState(0),
    [viewedSource, setViewedSource] = useState<Source | null>(null),
    [agents, setAgents] = useState<any>(null),
    [correction, setCorrection] = useState(""),
    [source, setSource] = useState(""),
    [html, setHtml] = useState(""),
    [gameOnly, setGameOnly] = useState(false),
    [edit, setEdit] = useState(""),
    [resetScope, setResetScope] = useState(""),
    [resetConfirm, setResetConfirm] = useState("");
  const previousGroup = useRef({ id: "", path: "" });
  const pendingReveal = useRef("");
  useEffect(() => {
    const family = state?.families.find((f) => f.id === selected);
    if (!family) return;
    const path = familyTreePath(family),
      key = path.join("|");
    if (
      previousGroup.current.id !== selected ||
      previousGroup.current.path !== key
    ) {
      setCollapsed((current) => revealTreePath(current, path));
    }
    previousGroup.current = { id: selected, path: key };
  }, [selected, state?.revision]);
  useEffect(() => {
    if (!pendingReveal.current) return;
    const row = document.querySelector<HTMLElement>(
      `[data-family-id="${CSS.escape(pendingReveal.current)}"]`,
    );
    if (row) {
      row.scrollIntoView({ block: "nearest" });
      pendingReveal.current = "";
    }
  }, [selected, collapsed, filter, query, state?.revision]);
  const editDirty = useRef(false);
  const formId = useRef("");
  const editRevision = useRef("");
  const input = useRef<HTMLInputElement>(null);
  const refresh = async () => {
    try {
      const [project, imageLibrary] = await Promise.all([
        request("/api/state"),
        request("/api/images"),
      ]);
      setState(project);
      setImages(imageLibrary);
      setConnected(true);
    } catch {
      setConnected(false);
    }
  };
  const refreshImageFolder = async () => {
    const library = await request<ImageCoverage>(
      "/api/images",
      undefined,
      "GET",
      { cache: "no-store" },
    );
    setImages(library);
  };
  const chromeHelper = useChromeHelper({
    focusSource: async ({ familyId, url }) => {
      const target = await request<Detail>(
        `/api/items/${encodeURIComponent(familyId)}`,
      );
      setView("catalogue");
      setTab("sources");
      setViewedSource(null);
      setSettingsOpen(false);
      setReturnSourceId((id) => id + 1);
      if (target.family.evidenceScope)
        setSharedScope(target.family.evidenceScope);
      else {
        setSharedScope(null);
        setQuery("");
        setFilter(target.family.status === "excluded" ? "excluded" : "all");
        select(target.family.id);
        setDetail(target);
        setTab("sources");
      }
      await refresh();
      // Wait for the item or shared dialog to render, then scroll/focus the exact URL.
      for (let attempt = 0; attempt < 50; attempt++) {
        await new Promise((resolve) => setTimeout(resolve, 80));
        const root = target.family.evidenceScope
          ? document.querySelector(".shared-source-modal")
          : document.querySelector(".sources-layout, .sources-grid");
        if (!root) continue;
        const candidates = [
          ...root.querySelectorAll<HTMLElement>("[data-source-url]"),
        ];
        const matches = candidates.filter(
          (row) => sourceKey(row.dataset.sourceUrl || "") === sourceKey(url),
        );
        const element =
          matches.find((row) =>
            row.matches(".source-card, .inherited-evidence-row"),
          ) || matches[0];
        if (!element) continue;
        element.scrollIntoView({ block: "center", behavior: "auto" });
        element.tabIndex = -1;
        element.focus({ preventScroll: true });
        element.classList.add("source-return-highlight");
        setTimeout(
          () => element.classList.remove("source-return-highlight"),
          6500,
        );
        return;
      }
      // A queued import may not have produced its evidence card yet.
      document
        .querySelector(".research-status, .shared-source-modal")
        ?.scrollIntoView({ block: "start", behavior: "auto" });
    },
    saved: (message) => {
      setNotice(message);
      void refresh();
    },
    error: (message) => setError(message),
  });
  useEffect(() => {
    if (settingsOpen) void request("/api/agents").then(setAgents);
  }, [settingsOpen]);
  useEffect(() => {
    void refresh();
    let timer: ReturnType<typeof setTimeout>;
    const es = new EventSource("/api/events");
    es.onmessage = () => {
      clearTimeout(timer);
      timer = setTimeout(refresh, 80);
    };
    es.onerror = () => setConnected(false);
    const t = setInterval(refresh, 10000);
    void request("/api/agents").then(setAgents);
    return () => {
      es.close();
      clearInterval(t);
      clearTimeout(timer);
    };
  }, []);
  useEffect(() => {
    if (!state) return;
    const visible = state.families.filter(
      (f) =>
        !f.supersededBy &&
        (filter === "excluded"
          ? f.status === "excluded"
          : f.status !== "excluded"),
    );
    if (!visible.some((f) => f.id === selected))
      setSelected(
        visible.find((f) => /hellfire/i.test(f.name))?.id ||
          visible[0]?.id ||
          "",
      );
  }, [state, selected, filter]);
  useEffect(() => {
    localStorage.setItem("borderlens.selection", selected);
    if (!selected) {
      setDetail(null);
      return;
    }
    const c = new AbortController();
    fetch("/api/items/" + encodeURIComponent(selected), { signal: c.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d) setDetail(d);
      })
      .catch(() => {});
    return () => c.abort();
  }, [selected, state?.revision, images?.revision]);
  useEffect(() => {
    if (detail && detail.family.id === selected) {
      const changed = formId.current !== selected;
      if (changed) {
        formId.current = selected;
        editDirty.current = false;
        setCorrection(detail.family.notes);
        setGameOnly(detail.family.gameOnly);
        setSource(detail.family.sourceUrls[0] || "");
      }
      const signature = `${detail.family.revision}:${detail.websiteOutput?.image}:${images?.revision}`;
      if (
        changed ||
        (!editDirty.current && editRevision.current !== signature)
      ) {
        editRevision.current = signature;
        setEdit(
          JSON.stringify(
            detail.websiteOutput || detail.output || detail.draft?.entry || {},
            null,
            2,
          ),
        );
      }
    }
  }, [
    selected,
    detail?.family.id,
    detail?.family.revision,
    detail?.websiteOutput?.image,
    images?.revision,
  ]);
  useEffect(() => {
    localStorage.setItem("borderlens.groups", JSON.stringify(collapsed));
  }, [collapsed]);
  const act = async (fn: () => Promise<unknown>, message?: string) => {
    setError("");
    setNotice("");
    setWorking(true);
    try {
      await fn();
      if (message) setNotice(message);
      await refresh();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setWorking(false);
    }
  };
  const itemAction = (action: string, body: Record<string, unknown> = {}) =>
    act(() =>
      request("/api/items/" + selected + "/action", { action, ...body }),
    );
  const sourceAction = (
    action: "exclude-source" | "restore-source",
    sourceId: string,
  ) =>
    act(
      () => request("/api/items/" + selected + "/action", { action, sourceId }),
      action === "exclude-source"
        ? "Source removed from future builds and fetching. Rebuild the item to update its JSON."
        : "Source restored. Rebuild the item to include it.",
    );
  const select = (id: string) => {
    const family = state?.families.find((f) => f.id === id);
    if (family)
      setCollapsed((current) =>
        revealTreePath(current, familyTreePath(family)),
      );
    pendingReveal.current = id;
    setSelected(id);
    setView("catalogue");
    setHtml("");
    setNotice("");
  };
  const upload = async (file: File) => {
    await act(async () => {
      const body = new FormData();
      body.append("file", file);
      const r = await fetch("/api/import", { method: "POST", body });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error);
    }, "Capture imported. Family candidates are ready to inspect.");
  };
  if (!state)
    return (
      <div className="loading">
        <div className="brand-mark">
          b<span>.</span>
        </div>
        <h2>Opening your workshop</h2>
        <p>
          {connected
            ? "Reading saved progress…"
            : "Waiting for the local service. Run pnpm dev in the app folder."}
        </p>
      </div>
    );
  const run = state.run,
    busy =
      ["running", "pausing"].includes(run.status) ||
      Boolean(state.identitySync),
    current = state.families.find(
      (f) => f.id === (state.identitySync?.familyId || run.currentId),
    ),
    done = state.families.filter((f) => f.status === "done").length,
    blocked = state.families.filter(
      (f) =>
        f.status !== "excluded" &&
        (f.status === "blocked" || f.urlDiscovery?.status === "failed"),
    ).length,
    removed = state.families.filter(
      (f) => f.status === "excluded" && !f.supersededBy,
    ).length,
    percent = run.queue.length
      ? Math.round((run.index / run.queue.length) * 100)
      : 0;
  const groups: Record<string, Family[]> = {};
  for (const f of state.families) {
    if (f.supersededBy || (filter !== "excluded" && f.status === "excluded"))
      continue;
    if (
      query &&
      !`${f.name} ${f.aliases.join(" ")} ${f.rawName || ""} ${f.subtype} ${f.character || ""}`
        .toLowerCase()
        .includes(query.toLowerCase())
    )
      continue;
    if (
      filter !== "all" &&
      !(filter === "blocked"
        ? f.status === "blocked" || f.urlDiscovery?.status === "failed"
        : f.status === filter)
    )
      continue;
    (groups[catalogueGroup(f)] ||= []).push(f);
  }
  const treePaths = Object.values(groups).flat().map(familyTreePath);
  const activePath = busy && current ? familyTreePath(current) : [];
  const f = detail?.family.id === selected ? detail.family : null,
    output = f ? detail?.output : null;
  const manualTypeChange = (
    type: import("../shared/manual-type").ManualType,
  ) => {
    if (!f) return;
    void act(async () => {
      const result = await request(`/api/items/${f.id}/type`, { type });
      setNotice(f.name + ": " + result.message);
    });
  };
  const manualNameChange = async (name: string) => {
    if (!f) return false;
    let saved = false;
    await act(async () => {
      const result = await request(`/api/items/${f.id}/name`, { name });
      saved = true;
      setNotice(result.message);
    });
    return saved;
  };
  const inheritedKeys = new Set(
    (detail?.inheritedEvidence || []).map((source) => sourceKey(source.url)),
  );
  const itemSources = (detail?.sources || []).filter(
    (source) =>
      !source.inheritedFrom && !inheritedKeys.has(sourceKey(source.url)),
  );
  const runGroup = (scope: EvidenceScope, action: GroupAction) =>
    void act(() => request("/api/groups/run", { scope, action }));
  const setSetting = (patch: Record<string, unknown>) =>
    act(() => request("/api/settings", patch, "PATCH"), "Settings saved.");
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            b<span>.</span>
          </span>
          <div>
            <strong>borderlens</strong>
            <small>CATALOGUE WORKSHOP</small>
          </div>
          <span className="local-badge">LOCAL</span>
        </div>
        <div className="project-label">
          <span className="project-dot" /> BORDERLANDS · GOTY ENHANCED
        </div>
        <nav className="main-nav">
          <button
            className={view === "catalogue" ? "active" : ""}
            onClick={() => setView("catalogue")}
          >
            <Layers size={17} /> Catalogue <span>{state.families.length}</span>
          </button>
          <button
            className={view === "coverage" ? "active" : ""}
            onClick={() => setView("coverage")}
          >
            <Target size={17} /> Coverage{" "}
            <span>{state.coverage.entries.length || "—"}</span>
          </button>
          <button
            className={view === "activity" ? "active" : ""}
            onClick={() => setView("activity")}
          >
            <Activity size={17} /> Activity
          </button>
        </nav>
        <div className="sidebar-heading">
          <span>ITEM FAMILIES</span>
          <div className="sidebar-tree-actions">
            <button
              aria-label="Collapse all"
              title="Collapse all — one level per click, deepest first"
              disabled={!treePaths.length}
              onClick={() =>
                setCollapsed((current) =>
                  stepTree(current, treePaths, "collapse"),
                )
              }
            >
              <ChevronsDownUp size={15} />
            </button>
            <button
              aria-label="Expand all"
              title="Expand all — one level per click, parents first"
              disabled={!treePaths.length}
              onClick={() =>
                setCollapsed((current) =>
                  stepTree(current, treePaths, "expand"),
                )
              }
            >
              <ChevronsUpDown size={15} />
            </button>
            <button
              title="Import extractor ZIP"
              onClick={() => input.current?.click()}
            >
              <Plus size={17} />
            </button>
          </div>
        </div>
        <div className="search">
          <Search size={15} />
          <input
            aria-label="Find an item"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Find an item…"
          />
          <kbd>⌕</kbd>
        </div>
        <div className="filter-row">
          <button
            className={filter === "all" ? "selected" : ""}
            onClick={() => setFilter("all")}
          >
            All
          </button>
          <button
            className={filter === "done" ? "selected" : ""}
            onClick={() => setFilter("done")}
          >
            Ready
          </button>
          <button
            className={filter === "blocked" ? "selected" : ""}
            onClick={() => setFilter("blocked")}
          >
            Needs attention{blocked > 0 && ` ${blocked}`}
          </button>
        </div>
        <button
          className={`removed-items-link ${filter === "excluded" ? "selected" : ""}`}
          onClick={() => setFilter(filter === "excluded" ? "all" : "excluded")}
        >
          <Trash2 size={13} /> Removed items{removed > 0 && ` (${removed})`}
        </button>
        <button
          className="shared-evidence-link"
          onClick={() => setSharedScope({ category: "Everything" })}
        >
          <BookOpen size={14} /> Shared evidence
        </button>
        <div className="item-tree">
          {Object.entries(groups).map(([group, items]) => (
            <div key={group} className="tree-group">
              <button
                className={`group-toggle${activePath[0] === group ? " is-active" : ""}`}
                aria-expanded={!collapsed[group]}
                onClick={() =>
                  setCollapsed({ ...collapsed, [group]: !collapsed[group] })
                }
              >
                {collapsed[group] ? (
                  <ChevronRight size={13} />
                ) : (
                  <ChevronDown size={13} />
                )}
                <span>{group}</span>
                {activePath[0] === group && (
                  <span
                    className="tiny-spinner group-spinner"
                    role="status"
                    aria-label={`Processing in ${group}`}
                    title={`Processing: ${current?.name}`}
                  />
                )}
                <GroupStatus items={items} />
              </button>
              <button
                className="group-evidence-button"
                aria-label={"Shared evidence for " + group}
                title={"Shared evidence for " + group}
                onClick={() =>
                  setSharedScope(
                    items[0].category === "Weapons"
                      ? { category: "Weapons", group: group as any }
                      : { category: items[0].category },
                  )
                }
              >
                <BookOpen size={13} />
              </button>
              <GroupActions
                scope={
                  items[0].category === "Weapons"
                    ? { category: "Weapons", group: group as any }
                    : { category: items[0].category }
                }
                families={state.families}
                busy={busy || working}
                run={runGroup}
              />
              {!collapsed[group] &&
                (() => {
                  const renderItem = (item: Family) => (
                    <button
                      key={item.id}
                      data-family-id={item.id}
                      className={`item-row ${selected === item.id ? "selected" : ""}`}
                      onClick={() => select(item.id)}
                      title={`${item.name} · ${statusLabel[item.status]}`}
                    >
                      <span className={`status-dot ${item.status}`} />
                      <span>{item.name}</span>
                      {busy && run.currentId === item.id ? (
                        <span className="tiny-spinner" />
                      ) : item.status === "blocked" ||
                        item.urlDiscovery?.status === "failed" ? (
                        <X
                          size={14}
                          className="failed-item-icon"
                          aria-label="Failed — needs attention"
                        />
                      ) : item.status === "done" ? (
                        <Check size={13} />
                      ) : null}
                    </button>
                  );
                  if (!["Class mods", "Artifacts"].includes(group))
                    return items.map(renderItem);
                  const characters = [
                    ...new Set(
                      items.map((item) => item.character || "Needs review"),
                    ),
                  ];
                  return characters.map((character) => {
                    const key = `${group}:${character}`,
                      children = items.filter(
                        (item) =>
                          (item.character || "Needs review") === character,
                      );
                    return (
                      <div key={key} className="character-group">
                        <button
                          className={`group-toggle${activePath[1] === key ? " is-active" : ""}`}
                          aria-expanded={!collapsed[key]}
                          onClick={() =>
                            setCollapsed({
                              ...collapsed,
                              [key]: !collapsed[key],
                            })
                          }
                        >
                          {collapsed[key] ? (
                            <ChevronRight size={13} />
                          ) : (
                            <ChevronDown size={13} />
                          )}
                          <span>{character}</span>
                          {activePath[1] === key && (
                            <span
                              className="tiny-spinner group-spinner"
                              role="status"
                              aria-label={`Processing in ${character}`}
                              title={`Processing: ${current?.name}`}
                            />
                          )}
                          <GroupStatus items={children} />
                        </button>
                        {character !== "Needs review" && (
                          <button
                            className="group-evidence-button"
                            aria-label={
                              "Shared evidence for " + group + " " + character
                            }
                            title="Shared character evidence"
                            onClick={() =>
                              setSharedScope({
                                category: items[0].category,
                                character: character as any,
                              })
                            }
                          >
                            <BookOpen size={13} />
                          </button>
                        )}
                        {character !== "Needs review" && (
                          <GroupActions
                            scope={{
                              category: items[0].category,
                              character: character as any,
                            }}
                            families={state.families}
                            busy={busy || working}
                            run={runGroup}
                          />
                        )}
                        {!collapsed[key] && children.map(renderItem)}
                      </div>
                    );
                  });
                })()}
            </div>
          ))}
          {!Object.keys(groups).length && (
            <p className="sidebar-empty">
              {state.families.length
                ? "No matching items."
                : "Your item families will appear here after import."}
            </p>
          )}
        </div>
        <div className="sidebar-bottom">
          <span
            className={connected ? "connection-dot" : "connection-dot offline"}
          />
          <span>{connected ? "Saved locally" : "Reconnecting…"}</span>
          <button title="Settings" onClick={() => setSettingsOpen(true)}>
            <Settings2 size={17} />
          </button>
        </div>
      </aside>
      <section className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            Workshop <ChevronRight size={13} />{" "}
            <strong>
              {view === "catalogue"
                ? "Catalogue"
                : view === "coverage"
                  ? "Coverage"
                  : "Activity"}
            </strong>
          </div>
          <div className="toolbar">
            <select
              className="agent-select"
              aria-label="Default agent"
              title="Default agent; changes apply to the next AI call. Automatic fallback is enabled."
              value={state.settings.agent || "grok"}
              onChange={(event) =>
                void setSetting({ agent: event.target.value })
              }
            >
              <option value="grok">Grok 4.6</option>
              <option value="codex">Codex</option>
            </select>
            <button
              className="button quiet chrome-helper-button"
              title={
                chromeHelper.connected
                  ? "Chrome helper connected"
                  : "Set up Chrome helper"
              }
              onClick={chromeHelper.showSetup}
            >
              <span
                className={
                  chromeHelper.connected
                    ? "connection-dot"
                    : "connection-dot offline"
                }
              />
              <Chrome size={15} /> Chrome helper
            </button>
            <button
              className="button quiet"
              disabled={working || busy}
              onClick={() => input.current?.click()}
            >
              <Upload size={15} /> Import ZIP
            </button>
            <a className="button quiet" href="/api/export">
              <Download size={15} /> Export ({done})
            </a>
            <span className="toolbar-divider" />
            <button
              className="icon-button"
              title="Settings"
              onClick={() => setSettingsOpen(true)}
            >
              <Settings2 size={17} />
            </button>
          </div>
        </header>
        <div className={`runbar ${busy ? "is-running" : ""}`}>
          <div className="run-icon">
            {busy ? (
              <span className="spinner" />
            ) : run.status === "blocked" ? (
              <TriangleAlert size={21} />
            ) : run.status === "complete" ? (
              <CheckCircle2 size={21} />
            ) : (
              <Play size={20} />
            )}
          </div>
          <div className="run-content">
            <div className="run-title">
              <strong>
                {state.identitySync
                  ? "Checking item " + state.identitySync.target
                  : run.cancelRequested
                    ? "Cancelling run"
                    : busy
                      ? run.mode === "discover"
                        ? "Finding evidence URLs"
                        : "Building your catalogue"
                      : run.status === "blocked"
                        ? "A little input needed"
                        : run.status === "complete"
                          ? "This run is complete"
                          : run.status === "paused"
                            ? "Ready when you are"
                            : "Your catalogue, one item at a time"}
              </strong>
              {run.scope && (
                <span className="run-scope" aria-label="Batch group">
                  {scopeLabel(run.scope)}
                </span>
              )}
              <span>
                {run.queue.length
                  ? `${Math.min(run.index + (busy ? 1 : 0), run.queue.length)} / ${run.queue.length}`
                  : `${done} / ${state.families.length} ready`}
              </span>
            </div>
            <p>{state.identitySync?.message || run.message}</p>
            <EvidenceStatsSummary stats={state.evidenceStats} />
            {!state.identitySync && (
              <div className="progress-track">
                <div style={{ width: `${percent}%` }} />
              </div>
            )}
          </div>
          {current && (
            <button
              className="jump"
              onClick={() => {
                setQuery("");
                setFilter(current.status === "excluded" ? "excluded" : "all");
                select(current.id);
              }}
              title="Jump to current item"
            >
              <Target size={15} />
              <span>Current item</span>
            </button>
          )}
          {!state.identitySync && (
            <BatchActions
              run={run}
              busy={busy}
              disabled={working || !state.families.length}
              savedBuild={!!state.buildCheckpoint}
              action={(action, sourceMode) =>
                void act(() => request("/api/run", { action, sourceMode }))
              }
            />
          )}
        </div>
        {(error || notice) && (
          <div
            role={error ? "alert" : "status"}
            className={`banner ${error ? "error" : "success"}`}
          >
            <span>{error || notice}</span>
            <button
              onClick={() => {
                setError("");
                setNotice("");
              }}
            >
              <X size={15} />
            </button>
          </div>
        )}
        <main>
          {f?.urlDiscovery?.status === "failed" && (
            <div className="banner error" role="alert">
              URL discovery needs attention: {f.urlDiscovery.issue}
            </div>
          )}

          {!state.families.length ? (
            <div className="empty-workshop">
              <div className="eyebrow">FROM GAME DATA TO PLAYER KNOWLEDGE</div>
              <h1>
                Build a clearer
                <br />
                picture of every item<span>.</span>
              </h1>
              <p>
                Bring in your extractor ZIP. Borderlens connects the evidence,
                <br className="desktop" /> researches the details and builds
                your catalogue, one family at a time.
              </p>
              <button
                className="button primary large"
                onClick={() => input.current?.click()}
              >
                <Upload size={17} /> Import your first capture{" "}
                <ArrowRight size={17} />
              </button>
              <div className="empty-steps">
                <div>
                  <span>01</span>
                  <strong>Import</strong>
                  <p>
                    Verified game data,
                    <br />
                    kept exactly as captured.
                  </p>
                </div>
                <div>
                  <span>02</span>
                  <strong>Research</strong>
                  <p>
                    Sources and corrections,
                    <br />
                    remembered for next time.
                  </p>
                </div>
                <div>
                  <span>03</span>
                  <strong>Build</strong>
                  <p>
                    Readable, evidenced entries.
                    <br />
                    Ready for your website.
                  </p>
                </div>
              </div>
              <div className="local-note">
                <Database size={14} /> Your captures and progress stay on this
                machine.
              </div>
            </div>
          ) : view === "coverage" ? (
            <>
              <div className="page-title">
                <div>
                  <div className="eyebrow">LEAVE NO FAMILY BEHIND</div>
                  <h1>Catalogue coverage</h1>
                  <p>
                    Compare known listings with your game data. A match is a
                    lead, not proof of completeness.
                  </p>
                </div>
                <button
                  className="button secondary"
                  disabled={working || state.coverage.status === "running"}
                  onClick={() => act(() => request("/api/coverage", {}))}
                >
                  <RefreshCw
                    size={15}
                    className={
                      state.coverage.status === "running" ? "spin" : ""
                    }
                  />{" "}
                  Compare catalogues
                </button>
              </div>
              <ImageCoveragePanel
                library={images}
                select={select}
                refresh={() => void refresh()}
              />
              <div className="metric-grid">
                {[
                  ["Extracted candidates", state.families.length],
                  ["External candidates", state.coverage.entries.length],
                  [
                    "Name matches",
                    state.coverage.entries.filter((e) => e.status === "matched")
                      .length,
                  ],
                  [
                    "Need investigation",
                    state.coverage.entries.filter(
                      (e) => e.status !== "matched" && e.status !== "excluded",
                    ).length,
                  ],
                ].map(([label, value]) => (
                  <div className="metric" key={label}>
                    <span>{label}</span>
                    <strong>{value}</strong>
                  </div>
                ))}
              </div>
              <p className="muted">{state.coverage.message}</p>
              {state.coverage.errors.map((m, i) => (
                <div className="coverage-error" key={i}>
                  {m}
                </div>
              ))}
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Candidate</th>
                      <th>Source</th>
                      <th>Comparison</th>
                      <th>Evidence / correction</th>
                    </tr>
                  </thead>
                  <tbody>
                    {state.coverage.entries.map((e) => (
                      <tr key={e.key}>
                        <td>{e.name}</td>
                        <td>{e.source}</td>
                        <td>
                          <span className="tag">
                            {e.status.replaceAll("_", " ")}
                          </span>
                        </td>
                        <td>
                          <a href={e.url} target="_blank" rel="noreferrer">
                            Open page <ArrowUpRight size={12} />
                          </a>
                          {e.familyIds[0] && (
                            <button
                              className="text-button"
                              onClick={() => select(e.familyIds[0])}
                            >
                              {" "}
                              View item
                            </button>
                          )}
                          <div className="coverage-actions">
                            <select
                              aria-label={"Link " + e.name + " to a family"}
                              disabled={
                                busy || state.coverage.status === "running"
                              }
                              value=""
                              onChange={(event) => {
                                if (event.target.value)
                                  void act(() =>
                                    request(
                                      "/api/coverage/" +
                                        encodeURIComponent(e.key),
                                      {
                                        action: "link",
                                        familyId: event.target.value,
                                      },
                                    ),
                                  );
                              }}
                            >
                              <option value="">
                                Link to extracted family…
                              </option>
                              {state.families.map((f) => (
                                <option key={f.id} value={f.id}>
                                  {f.name} · {f.subtype}
                                </option>
                              ))}
                            </select>
                            <button
                              className="text-button"
                              disabled={
                                busy || state.coverage.status === "running"
                              }
                              onClick={() =>
                                act(() =>
                                  request(
                                    "/api/coverage/" +
                                      encodeURIComponent(e.key),
                                    { action: "exclude" },
                                  ),
                                )
                              }
                            >
                              Exclude
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!state.coverage.entries.length && (
                  <div className="panel-empty">
                    Run a comparison to discover missing pages and possible
                    families.
                  </div>
                )}
              </div>
            </>
          ) : view === "activity" ? (
            <>
              <div className="page-title">
                <div>
                  <div className="eyebrow">EVERY STEP, REMEMBERED</div>
                  <h1>Workshop activity</h1>
                  <p>
                    Capture imports and project events. Individual processing
                    history lives on each item.
                  </p>
                </div>
              </div>
              <div className="history-list">
                {[...state.activity].reverse().map((h, i) => (
                  <div key={i}>
                    <span className="history-dot" />
                    <div>
                      <strong>{h.message}</strong>
                      <p>
                        {new Date(h.at).toLocaleString()} · {h.stage}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : f ? (
            <>
              <div className="item-heading">
                <div>
                  <div className="eyebrow">
                    {f.category.toUpperCase()} <span>/</span>{" "}
                    {catalogueGroup(f).toUpperCase()}
                  </div>
                  <h1>
                    {f.name}
                    <span className={`pill ${f.status}`}>
                      {statusLabel[f.status]}
                    </span>
                  </h1>
                  <p>
                    {output?.summary ||
                      "A family from your game capture. Its player-facing entry is waiting to be built."}
                  </p>
                </div>
                <div className="item-actions">
                  <div className="item-rebuild-summary">
                    <EvidenceSizeSummary
                      direct={itemSources}
                      inherited={detail?.inheritedEvidence || []}
                      gameOnly={f.gameOnly}
                      pendingUrls={f.sourceUrls.filter(
                        (url) =>
                          !(detail?.excludedSources || []).some(
                            (excluded) =>
                              sourceKey(excluded.url) === sourceKey(url),
                          ),
                      )}
                    />
                    <RebuildActions
                      saved={detail?.savedRebuild}
                      discoveryDisabled={busy}
                      disabled={working || f.status === "excluded"}
                      run={(action) => void itemAction(action)}
                    />
                  </div>
                  <button
                    className="button quiet"
                    disabled={working || f.status === "excluded"}
                    onClick={() => itemAction("from")}
                  >
                    Start from here <ArrowRight size={14} />
                  </button>
                </div>
              </div>
              {classificationNote(f) && (
                <div className="classification-note">
                  <TriangleAlert size={17} />
                  <p>{classificationNote(f)}</p>
                </div>
              )}
              <div className="stage-strip">
                {Object.entries(stepLabels).map(([key, label], i) => (
                  <div
                    key={key}
                    className={`${f.stage === key ? "current" : ""} ${Object.keys(stepLabels).indexOf(f.stage) > i ? "finished" : ""}`}
                  >
                    <span>
                      {Object.keys(stepLabels).indexOf(f.stage) > i ? (
                        <Check size={12} />
                      ) : (
                        i + 1
                      )}
                    </span>
                    {label}
                  </div>
                ))}
              </div>
              <div className="tabs">
                {[
                  ["preview", "Preview", BookOpen],
                  ["game-data", "Game data", Layers],
                  ["sources", "Sources & evidence", Database],
                  ["history", "History", Clock],
                  ["json", "Final JSON", FileJson],
                ].map(([key, label, Icon]: any) => (
                  <button
                    key={key}
                    className={tab === key ? "active" : ""}
                    onClick={() => setTab(key)}
                  >
                    <Icon size={15} />
                    {label}
                    {key === "sources" && (
                      <small>{detail?.sources.length || 0}</small>
                    )}
                  </button>
                ))}
              </div>
              <EvidenceRequestAlert
                notice={detail?.evidenceRequestNotice}
                review={() => setTab("sources")}
                dismiss={async (id) => {
                  await act(
                    () =>
                      request(
                        `/api/items/${f.id}/evidence-request-notice/dismiss`,
                        { id },
                      ),
                    "Evidence notice dismissed. Source settings unchanged.",
                  );
                }}
              />
              {f.issue && (
                <div className="issue-card">
                  <TriangleAlert size={20} />
                  <div>
                    <strong>This item needs attention</strong>
                    <p>{f.issue}</p>
                    <button
                      className="text-button"
                      onClick={() => setTab("sources")}
                    >
                      Review sources & corrections <ArrowRight size={13} />
                    </button>
                  </div>
                </div>
              )}
              {tab === "game-data" ? (
                <GameDataTab familyId={f.id} />
              ) : tab === "preview" ? (
                <div className="preview-grid">
                  <section className="item-preview">
                    <div className="section-label">
                      PLAYER PREVIEW{" "}
                      <span>
                        {output ? "LAST VALIDATED REVISION" : "NOT BUILT YET"}
                      </span>
                    </div>
                    <ItemImage
                      name={f.name}
                      match={
                        images?.items.find((item) => item.id === f.id) ||
                        detail?.image
                      }
                      library={images}
                      refresh={refreshImageFolder}
                      busy={working}
                      choose={(body) =>
                        void act(
                          () => request("/api/items/" + f.id + "/image", body),
                          "Image saved.",
                        )
                      }
                    />
                    {detail?.finalValidation &&
                      output &&
                      detail.finalValidation.compilerVersion ===
                        output.compilerVersion && (
                        <p className="muted">
                          <CheckCircle2 size={14} /> Final JSON checked
                        </p>
                      )}
                    {output && !!detail?.finalValidation?.warnings?.length && (
                      <details className="notice">
                        <summary>
                          Built with {detail.finalValidation.warnings.length}{" "}
                          notes
                        </summary>
                        <p className="muted">
                          Saved successfully. These uncertainties do not block
                          this item.
                        </p>
                        <ul>
                          {detail.finalValidation.warnings.map(
                            (warning, index) => (
                              <li key={index}>{warning}</li>
                            ),
                          )}
                        </ul>
                      </details>
                    )}
                    {output ? (
                      <>
                        <div className="preview-tags">
                          {[
                            ...output.manufacturers,
                            ...output.rarities,
                            ...output.elements,
                          ].map((t) => (
                            <span key={t} className="tag">
                              {t}
                            </span>
                          ))}
                        </div>
                        {output.redText && (
                          <blockquote>“{output.redText}”</blockquote>
                        )}
                        {output.description?.map((paragraph, i) => (
                          <p className="description-paragraph" key={i}>
                            {paragraph}
                          </p>
                        ))}
                        {output.details?.map((section, i) => (
                          <section key={i}>
                            <h2>{section.heading}</h2>
                            {section.paragraphs.map((paragraph, j) => (
                              <p key={j}>{paragraph}</p>
                            ))}
                          </section>
                        ))}
                        <h2>What makes it different</h2>
                        {output.specialEffects.length ? (
                          <ul className="effect-list">
                            {output.specialEffects.map((e, i) => (
                              <li key={i}>{e}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="muted">
                            No special effect has been established for this
                            family.
                          </p>
                        )}
                        <h2>Stats & variations</h2>
                        {output.stats.length ? (
                          <div className="stats-list">
                            {output.stats.map((s, i) => (
                              <div key={i}>
                                <strong>
                                  {s.name}
                                  {s.context ? ` (${s.context})` : ""}
                                </strong>
                                <span>
                                  {s.minimum ?? "—"}
                                  {s.maximum !== s.minimum && s.maximum !== null
                                    ? `–${s.maximum}`
                                    : ""}{" "}
                                  {s.unit}
                                </span>
                                {s.notes && <p>{s.notes}</p>}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="muted">No stat ranges available yet.</p>
                        )}
                        {output.variants?.length > 0 && (
                          <>
                            <h2>Meaningful variants</h2>
                            {output.variants.map((v, i) => (
                              <div key={i}>
                                <h3>{v.name}</h3>
                                <p>{v.description}</p>
                                <ul>
                                  {v.differences.map((d, j) => (
                                    <li key={j}>{d}</li>
                                  ))}
                                </ul>
                              </div>
                            ))}
                          </>
                        )}
                        {output.parts?.length > 0 && (
                          <>
                            <h2>Weapon parts</h2>
                            {output.parts.map((ref) => {
                              const part = detail?.parts?.find(
                                (part) => part.id === ref.partId,
                              );
                              return (
                                <div className="part-preview" key={ref.partId}>
                                  <strong>{part?.name || ref.partId}</strong>
                                  <small>
                                    {" "}
                                    · {part?.slot} · {ref.relationship}
                                  </small>
                                  <p>{ref.notes}</p>
                                  {part?.effects.map((effect, i) => (
                                    <p key={i}>{effect}</p>
                                  ))}
                                </div>
                              );
                            })}
                          </>
                        )}
                        <h2>Where to find it</h2>
                        {output.sources.length ? (
                          acquisitionSources(output.sources).map((s, i) => (
                            <p key={i}>
                              <strong>{s.label}</strong>
                              <br />
                              {s.notes}
                              {(s.location || s.dlc) && (
                                <small className="source-context">
                                  {[s.location, s.dlc]
                                    .filter(Boolean)
                                    .join(" · ")}
                                </small>
                              )}
                              {s.conditions?.map((condition, j) => (
                                <small className="source-context" key={j}>
                                  {condition}
                                </small>
                              ))}
                              {s.dropChances.map((rate, j) => (
                                <small className="source-context" key={j}>
                                  {rate.percent}%
                                  {rate.players
                                    ? ` · ${rate.players} player${rate.players === 1 ? "" : "s"}`
                                    : ""}
                                  {rate.conditions.length
                                    ? ` · ${rate.conditions.join("; ")}`
                                    : ""}
                                </small>
                              ))}
                              {s.url && (
                                <a
                                  target="_blank"
                                  rel="noreferrer"
                                  href={s.url}
                                >
                                  {" "}
                                  Source <ArrowUpRight size={12} />
                                </a>
                              )}
                            </p>
                          ))
                        ) : (
                          <p className="muted">
                            No verified source established yet.
                          </p>
                        )}
                        {output.notes.length > 0 && (
                          <>
                            <h2>Good to know</h2>
                            {output.notes.map((n, i) => (
                              <p key={i}>{n}</p>
                            ))}
                          </>
                        )}
                      </>
                    ) : (
                      <div className="preview-placeholder">
                        <BookOpen size={28} />
                        <h2>A good entry starts with evidence.</h2>
                        <p>
                          Rebuild this item on its own, or start the queue.
                          <br />
                          You can keep browsing while Borderlens works.
                        </p>
                        <button
                          className="button secondary"
                          onClick={() =>
                            itemAction(
                              detail?.savedRebuild.available
                                ? "rebuild-saved"
                                : "rebuild-fresh",
                            )
                          }
                          disabled={working}
                        >
                          <Play size={14} /> Build {f.name}
                        </button>
                      </div>
                    )}
                  </section>
                  <aside className="inspector">
                    <div className="section-label">AT A GLANCE</div>
                    <ManualTypePicker
                      family={f}
                      disabled={
                        working ||
                        busy ||
                        f.status === "excluded" ||
                        Boolean(f.supersededBy)
                      }
                      change={manualTypeChange}
                    />
                    <dl>
                      <dt>Item family</dt>
                      <dd>
                        {f.name}
                        <ManualNameEditor
                          key={f.id}
                          family={f}
                          disabled={
                            working ||
                            busy ||
                            f.status === "excluded" ||
                            Boolean(f.supersededBy)
                          }
                          save={manualNameChange}
                        />
                      </dd>
                      {f.nameOverride && (
                        <>
                          <dt>Extracted name</dt>
                          <dd>{f.rawName}</dd>
                          <dt>Name source</dt>
                          <dd title={f.nameOverride.reason}>
                            {f.nameOverride.origin === "manual"
                              ? "Your manual override (locked)"
                              : "Verified saved evidence"}
                          </dd>
                        </>
                      )}
                      <dt>Category</dt>
                      <dd>{catalogueGroup(f)}</dd>
                      {f.character && (
                        <>
                          <dt>Character</dt>
                          <dd>{f.character}</dd>
                        </>
                      )}
                      <dt>Game</dt>
                      <dd>Borderlands</dd>
                      <dt>DLC</dt>
                      <dd>
                        {detail?.extractedDlc ||
                          output?.dlc ||
                          "Unknown"}
                      </dd>
                      <dt>Game evidence</dt>
                      <dd>
                        {detail?.packet?.evidence.filter(
                          (e) => e.kind === "game",
                        ).length || f.roots.length}{" "}
                        linked records
                      </dd>
                      <dt>Research</dt>
                      <dd>
                        {f.gameOnly
                          ? "Game evidence only"
                          : `${detail?.sources.length || 0} saved pages`}
                      </dd>
                      <dt>Saved revision</dt>
                      <dd>{f.revision || "Not built yet"}</dd>
                    </dl>
                    <section
                      className="identity-sync-controls"
                      aria-label="Sync item identity"
                    >
                      <div className="section-label">SYNC FROM SAVED DATA</div>
                      <div className="identity-sync-buttons">
                        {(["type", "name"] as const).map((target) => (
                          <button
                            key={target}
                            className="button secondary"
                            disabled={
                              working ||
                              busy ||
                              f.status === "excluded" ||
                              Boolean(f.supersededBy)
                            }
                            title={
                              busy
                                ? "Wait for the current job to finish or pause it first."
                                : "Check saved evidence and game data without rebuilding."
                            }
                            onClick={() =>
                              void act(async () => {
                                const result = await request(
                                  `/api/items/${f.id}/sync`,
                                  { target },
                                );
                                setNotice(f.name + ": " + result.message);
                              })
                            }
                          >
                            {state.identitySync?.familyId === f.id &&
                            state.identitySync.target === target ? (
                              <span className="tiny-spinner" />
                            ) : (
                              <RefreshCw size={14} />
                            )}
                            Sync {target}
                          </button>
                        ))}
                      </div>
                      <p className="muted small">
                        Checks saved evidence, game data and existing JSON.
                        Updates verified identity only; no rebuild.
                      </p>
                      {state.identitySync?.familyId === f.id && (
                        <p className="muted small" role="status">
                          {state.identitySync.message}
                        </p>
                      )}
                    </section>
                    {catalogueGroup(f) === "Needs review" &&
                      f.status !== "excluded" &&
                      !f.supersededBy && (
                        <DuplicateFinder
                          key={f.id}
                          family={f}
                          busy={working || (busy && run.currentId === f.id)}
                          remove={() =>
                            act(
                              () =>
                                request(
                                  `/api/items/${f.id}/duplicates/remove`,
                                  {},
                                ),
                              "Needs review entry removed. Possible matches were left unchanged; restore it from Removed items if needed.",
                            )
                          }
                        />
                      )}
                    <div className="catalogue-removal">
                      {f.status === "excluded" ? (
                        <>
                          <p>
                            Removed from batches and exports. Saved data is
                            kept.
                          </p>
                          <button
                            className="button secondary"
                            disabled={working}
                            onClick={() => itemAction("restore")}
                          >
                            <Undo2 size={14} /> Restore to catalogue
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            className="button remove-item-button"
                            disabled={
                              working || (busy && run.currentId === f.id)
                            }
                            onClick={() => itemAction("remove")}
                          >
                            <Trash2 size={14} /> Remove from catalogue
                          </button>
                          <p>You can restore it from Removed items.</p>
                        </>
                      )}
                    </div>
                    <div className="inspector-note">
                      <Database size={16} />
                      <p>
                        Every completed step is saved locally. Browsing never
                        interrupts the queue.
                      </p>
                    </div>
                    {detail?.draft?.uncertainties?.length ? (
                      <div className="unknowns">
                        <strong>Still to establish</strong>
                        {detail.draft.uncertainties.map((u, i) => (
                          <p key={i}>{u}</p>
                        ))}
                      </div>
                    ) : null}
                  </aside>
                </div>
              ) : tab === "sources" ? (
                <div className="sources-grid">
                  <section>
                    <div className="section-label">
                      SAVED RESEARCH{" "}
                      <button
                        className="text-button"
                        disabled={working || busy}
                        onClick={() => itemAction("refresh")}
                      >
                        <RefreshCw size={13} /> Refresh sources
                      </button>
                    </div>
                    <InheritedEvidenceList
                      items={detail?.inheritedEvidence || []}
                      view={async (item) => {
                        const key = sourceKey(item.url);
                        let saved = detail?.sources.find(
                          (source) => sourceKey(source.url) === key,
                        );
                        let owner =
                          item.parents.find(
                            (parent) => parent.id === saved?.inheritedFrom?.id,
                          ) || item.parents[0];
                        if (!saved) {
                          for (const parent of item.parents) {
                            const shared = await request<Detail>(
                              `/api/items/${encodeURIComponent(parent.id)}`,
                            );
                            saved = shared.sources.find(
                              (source) => sourceKey(source.url) === key,
                            );
                            if (saved) {
                              owner = parent;
                              break;
                            }
                          }
                        }
                        if (!saved)
                          throw new Error(
                            "Saved source is no longer available. Refresh the evidence list.",
                          );
                        setViewedSource({ ...saved, inheritedFrom: owner });
                      }}
                      recapture={(ownerId, url) =>
                        chromeHelper.openPage(ownerId, url)
                      }
                      disabled={working || (busy && run.currentId === f.id)}
                      key={f.id}
                      setAllModes={(mode) => {
                        let saved = false;
                        return act(
                          async () => {
                            await request(
                              `/api/items/${f.id}/shared-source-modes`,
                              { mode },
                            );
                            saved = true;
                          },
                          "All inherited sources set to " +
                            (mode === "always"
                              ? "Always include"
                              : mode === "never"
                                ? "Never include"
                                : "Auto") +
                            ". No build started.",
                        ).then(() => saved);
                      }}
                      setMode={(url, mode) => {
                        let saved = false;
                        return act(
                          async () => {
                            await request(
                              `/api/items/${f.id}/shared-source-mode`,
                              { url, mode },
                            );
                            saved = true;
                          },
                          mode === "never"
                            ? "Source set to Never include for this item’s next build."
                            : mode === "always"
                              ? "Source set to Always include for this item’s next build."
                              : "Source set to Auto. The app will select relevant facts on the next build.",
                        ).then(() => saved);
                      }}
                      manage={(id) => {
                        const scope = state.sharedScopes?.find(
                          (scope) => scope.id === id,
                        )?.evidenceScope;
                        if (scope) setSharedScope(scope);
                      }}
                    />
                    <EvidenceFollowupSummary
                      report={detail?.evidenceFollowup}
                    />
                    <SharedResearchSummary
                      selection={detail?.sharedSourceSelection}
                    />
                    <div className="research-status">
                      {researchProviders.map((provider) => {
                        const count = itemSources.filter(
                          (s) => providerForUrl(s.url) === provider,
                        ).length;
                        const row = detail?.research?.providers.find(
                          (row) => row.provider === provider,
                        );
                        const targets = [
                          ...new Set([
                            ...(row?.urls || []),
                            ...f.sourceUrls.filter(
                              (url) => providerForUrl(url) === provider,
                            ),
                          ]),
                        ].filter(
                          (url) =>
                            !detail?.inheritedEvidence?.some(
                              (source) =>
                                sourceKey(source.url) === sourceKey(url),
                            ),
                        );
                        if (
                          !count &&
                          !targets.length &&
                          (detail?.inheritedEvidence?.some(
                            (source) => providerForUrl(source.url) === provider,
                          ) ||
                            detail?.excludedSources?.some(
                              (source) =>
                                providerForUrl(source.url) === provider,
                            ))
                        )
                          return null;
                        return (
                          <div
                            key={provider}
                            className={count ? "saved" : "missing"}
                          >
                            <strong>
                              {provider} ·{" "}
                              {count
                                ? `${count} saved`
                                : row?.status === "unavailable"
                                  ? "Unavailable"
                                  : row?.status === "inherited"
                                    ? "Inherited"
                                    : "Not saved"}
                            </strong>
                            <p>
                              {count
                                ? "Cached evidence ready for the writer."
                                : row?.message ||
                                  "Rebuild this item to seek this source. If blocked, import saved page HTML with its original URL."}
                            </p>
                            <div className="browser-import-buttons">
                              {targets.map((url, index) => (
                                <span
                                  className="evidence-url-actions"
                                  data-source-url={url}
                                  key={url}
                                >
                                  <button
                                    className="button secondary"
                                    disabled={chromeHelper.opening}
                                    onClick={() =>
                                      chromeHelper.openPage(f.id, url)
                                    }
                                  >
                                    <Chrome size={13} />
                                    {index === 0
                                      ? `Open ${provider === "Wiki" ? "wiki" : "Lootlemon"} in Chrome`
                                      : "Open additional article"}
                                  </button>
                                  {!itemSources.some(
                                    (source) =>
                                      sourceKey(source.url) === sourceKey(url),
                                  ) && (
                                    <button
                                      className="pending-source-remove"
                                      aria-label={"Remove evidence URL: " + url}
                                      title="Remove this URL and exclude it from future discovery"
                                      disabled={
                                        working ||
                                        (busy && run.currentId === f.id)
                                      }
                                      onClick={() =>
                                        void act(
                                          () =>
                                            request(
                                              "/api/items/" + f.id + "/action",
                                              { action: "exclude-source", url },
                                            ),
                                          "Evidence URL removed. Restore it from Removed sources if needed.",
                                        )
                                      }
                                    >
                                      <X size={15} />
                                    </button>
                                  )}
                                </span>
                              ))}
                              {!targets.length && (
                                <button
                                  className="text-button"
                                  onClick={() => chromeHelper.showSetup()}
                                >
                                  Set up browser capture
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    {itemSources.length ? (
                      itemSources.map((s) => (
                        <article
                          data-source-url={s.url}
                          className={
                            "source-card" +
                            (s.manualText
                              ? " is-manual-text manual-evidence-surface"
                              : "")
                          }
                          key={s.id}
                        >
                          <div>
                            {s.manualText ? (
                              <ManualEvidenceIcon size={19} />
                            ) : (
                              <BookOpen size={18} />
                            )}
                            <strong>{s.title}</strong>
                            <SourceSite url={s.url} />
                            {s?.selectedContent && (
                              <span
                                className="selected-content-badge"
                                title="Only user-selected areas were captured; this is not the complete article."
                              >
                                Selected page content ·{" "}
                                {s.selectedContent.boxes} boxes
                                {s.selectedContent.warnings > 0
                                  ? " · partial"
                                  : ""}
                              </span>
                            )}
                            <SourceSize text={s.text} />
                            {!s.manualText && (
                              <SourceRecapture
                                url={s.url}
                                title={s.title}
                                disabled={
                                  working ||
                                  chromeHelper.opening ||
                                  f.status === "excluded"
                                }
                                run={() => chromeHelper.openPage(f.id, s.url)}
                              />
                            )}
                            {s.manualText && (
                              <ManualEvidenceEdit
                                source={s}
                                ownerId={f.id}
                                disabled={
                                  working ||
                                  !!state.identitySync ||
                                  (busy && run.currentId === f.id)
                                }
                                onSaved={() => void refresh()}
                              />
                            )}
                            <SourcePromote
                              owner={f}
                              disabled={
                                working || (busy && run.currentId === f.id)
                              }
                              onMove={() =>
                                void act(
                                  () =>
                                    request("/api/evidence/promote", {
                                      ownerId: f.id,
                                      url: s.url,
                                    }),
                                  "Evidence moved to its parent. It will be used on the next requested build.",
                                )
                              }
                            />
                            {!s.manualText && (
                              <a target="_blank" rel="noreferrer" href={s.url}>
                                <ArrowUpRight size={15} />
                              </a>
                            )}
                            <button
                              className="source-remove-button"
                              aria-label={"Remove source: " + s.title}
                              title={
                                busy && run.currentId === f.id
                                  ? "Pause processing before removing this source"
                                  : "Remove this source from this item"
                              }
                              disabled={
                                working ||
                                f.status === "excluded" ||
                                (busy && run.currentId === f.id)
                              }
                              onClick={() =>
                                sourceAction("exclude-source", s.id)
                              }
                            >
                              <X size={15} />
                            </button>
                          </div>
                          {s.reusedFrom && (
                            <small className="source-reused">
                              Reused saved article · saved for{" "}
                              {s.reusedFrom.name}
                            </small>
                          )}
                          <small>
                            {new Date(s.fetchedAt).toLocaleString()} ·{" "}
                            {s.manualText
                              ? "Manually added text"
                              : s.captureMethod === "chrome"
                                ? "Captured in Chrome"
                                : s.imported
                                  ? "Imported HTML"
                                  : "Fetched & cached"}
                          </small>
                          <p
                            className={
                              s.manualText ? "manual-evidence-text" : undefined
                            }
                          >
                            {s.text.slice(0, 550)}
                            {s.text.length > 550 ? "…" : ""}
                          </p>
                          <button
                            className="text-button source-show-more"
                            aria-label={"Show more: " + s.title}
                            onClick={() => setViewedSource(s)}
                          >
                            Show more <ArrowUpRight size={12} />
                          </button>
                        </article>
                      ))
                    ) : (
                      <div className="panel-empty">
                        No item-specific pages saved yet.
                        {!!detail?.inheritedEvidence?.length &&
                          " Shared evidence above is still available to the build."}
                      </div>
                    )}
                    {!!detail?.excludedSources?.length && (
                      <details className="removed-sources">
                        <summary>
                          Removed sources ({detail.excludedSources.length})
                        </summary>
                        <p>
                          These pages are excluded from builds and automatic
                          fetching for this item.
                        </p>
                        {detail.excludedSources.map((source) => (
                          <div
                            className={
                              "removed-source" +
                              (isManualTextUrl(source.url)
                                ? " manual-evidence-surface"
                                : "")
                            }
                            key={source.sourceId}
                          >
                            <div>
                              {isManualTextUrl(source.url) ? (
                                <>
                                  <ManualEvidenceIcon size={15} />
                                  <strong>{source.title}</strong>
                                  <SourceSite url={source.url} />
                                </>
                              ) : (
                                <>
                                  <a
                                    href={source.url}
                                    target="_blank"
                                    rel="noreferrer"
                                  >
                                    {source.title}
                                  </a>
                                  <small>{source.url}</small>
                                </>
                              )}
                            </div>
                            <button
                              className="text-button"
                              disabled={
                                working ||
                                f.status === "excluded" ||
                                (busy && run.currentId === f.id)
                              }
                              onClick={() =>
                                sourceAction("restore-source", source.sourceId)
                              }
                              aria-label={"Restore source: " + source.title}
                            >
                              <Undo2 size={13} /> Restore
                            </button>
                          </div>
                        ))}
                      </details>
                    )}
                    {detail?.researchAudit?.ledger && (
                      <details className="evidence-details">
                        <summary>
                          Compilation coverage (
                          {detail.researchAudit.ledger.length} sources)
                        </summary>
                        <p>
                          Every source is read in full. Each extracted fact is
                          used, merged as a duplicate, or given an explicit
                          reason for exclusion. This audit stays out of website
                          exports.
                        </p>
                        <pre>
                          {JSON.stringify(detail.researchAudit, null, 2)}
                        </pre>
                      </details>
                    )}
                    <details className="evidence-details">
                      <summary>
                        Captured game evidence (
                        {detail?.packet?.evidence.filter(
                          (e) => e.kind === "game",
                        ).length || 0}
                        )
                      </summary>
                      <pre>
                        {JSON.stringify(
                          detail?.packet || { roots: f.roots },
                          null,
                          2,
                        )}
                      </pre>
                    </details>
                  </section>
                  <aside className="correction-card">
                    <ManualEvidenceForm
                      key={f.id}
                      disabled={
                        working ||
                        f.status === "excluded" ||
                        !!state.identitySync ||
                        (busy && run.currentId === f.id)
                      }
                      add={(value) => {
                        let saved = false;
                        return act(async () => {
                          await request(
                            `/api/items/${f.id}/text-evidence`,
                            value,
                          );
                          saved = true;
                        }, "Text evidence saved. Used on the next build; no build started.").then(
                          () => saved,
                        );
                      }}
                    />
                    <h2>Help it move forward</h2>
                    <p>
                      A correction is remembered for future runs. Add a source
                      or explain what needs changing.
                    </p>
                    <ManualTypePicker
                      family={f}
                      disabled={
                        working ||
                        busy ||
                        f.status === "excluded" ||
                        Boolean(f.supersededBy)
                      }
                      change={manualTypeChange}
                    />
                    <label>
                      Source page URL
                      <input
                        value={source}
                        onChange={(e) => setSource(e.target.value)}
                        placeholder="https://…"
                      />
                    </label>
                    <button
                      className="text-button source-url-capture"
                      disabled={
                        !source.trim() ||
                        chromeHelper.opening ||
                        f.status === "excluded"
                      }
                      title={
                        source.trim()
                          ? "Open this source with the Chrome capture extension."
                          : "Paste a Wiki or Lootlemon URL above first."
                      }
                      onClick={() => chromeHelper.openPage(f.id, source.trim())}
                    >
                      <Chrome size={13} />{" "}
                      {chromeHelper.opening
                        ? "Opening in Chrome…"
                        : "Open URL in Chrome for capture"}
                    </button>
                    <label>
                      Your correction
                      <textarea
                        value={correction}
                        onChange={(e) => setCorrection(e.target.value)}
                        placeholder="Use this page, keep this detail…"
                        rows={4}
                      />
                    </label>
                    <details>
                      <summary>Import saved HTML</summary>
                      <textarea
                        value={html}
                        onChange={(e) => setHtml(e.target.value)}
                        placeholder="Paste the original page HTML"
                        rows={5}
                      />
                      <small>
                        Include its original wiki/Lootlemon URL above.
                      </small>
                    </details>
                    <label className="check-label">
                      <input
                        type="checkbox"
                        checked={gameOnly}
                        onChange={(e) => setGameOnly(e.target.checked)}
                      />{" "}
                      Use game evidence only for this item
                    </label>
                    <button
                      className="button primary"
                      disabled={working || busy}
                      onClick={() =>
                        itemAction("resolve", {
                          url: source || undefined,
                          html: html || undefined,
                          notes: correction,
                          gameOnly,
                        })
                      }
                    >
                      Save correction <Check size={15} />
                    </button>
                    {f.issue && (
                      <button
                        className="button secondary"
                        disabled={working || busy}
                        onClick={() => itemAction("retry")}
                      >
                        Retry this step
                      </button>
                    )}
                    <button
                      className="text-button danger"
                      disabled={working || busy}
                      onClick={() =>
                        itemAction("remove", {
                          notes:
                            correction ||
                            "Deliberately excluded from this catalogue.",
                        })
                      }
                    >
                      Exclude this candidate
                    </button>
                  </aside>
                </div>
              ) : tab === "history" ? (
                <div className="history-list">
                  {[...(detail?.evidenceStatsHistory || [])]
                    .reverse()
                    .map((stats) => (
                      <div key={stats.id}>
                        <span className="history-dot" />
                        <div>
                          <strong>
                            AI evidence statistics ·{" "}
                            {stats.outcome === "cancelled"
                              ? "Cancelled"
                              : stats.outcome === "failed"
                                ? "Stopped with an error"
                                : "Completed"}
                          </strong>
                          <p>
                            {new Date(
                              stats.finishedAt || stats.startedAt,
                            ).toLocaleString()}
                          </p>
                          <EvidenceStatsSummary stats={stats} history />
                        </div>
                      </div>
                    ))}
                  {[...f.history].reverse().map((h, i) => (
                    <div key={i}>
                      <span className="history-dot" />
                      <div>
                        <strong>{h.message}</strong>
                        <p>
                          {new Date(h.at).toLocaleString()} ·{" "}
                          {stepLabels[h.stage as keyof typeof stepLabels] ||
                            h.stage}
                        </p>
                      </div>
                    </div>
                  ))}
                  {!f.history.length &&
                    !detail?.evidenceStatsHistory?.length && (
                      <div className="panel-empty">
                        This item has not entered processing yet.
                      </div>
                    )}
                </div>
              ) : (
                <div className="json-panel">
                  <div className="section-label">
                    WEBSITE-READY JSON{" "}
                    <span>
                      {output ? `REVISION ${f.revision}` : "DRAFT / NOT BUILT"}
                    </span>
                  </div>
                  {output &&
                    output.schemaVersion !== CATALOGUE_SCHEMA_VERSION && (
                      <div className="classification-note">
                        Previous-schema output is retained below. Rebuild this
                        item for the new description, variants, sources and
                        parts fields.
                      </div>
                    )}
                  <p className="muted">
                    You can edit a completed entry here. Saved manual edits
                    survive rebuilds.
                  </p>
                  <textarea
                    spellCheck={false}
                    aria-label="Edit final item JSON"
                    value={edit}
                    onChange={(e) => {
                      editDirty.current = true;
                      setEdit(e.target.value);
                    }}
                  />
                  <button
                    className="button secondary"
                    disabled={working || busy}
                    onClick={() =>
                      act(async () => {
                        let parsed;
                        try {
                          parsed = JSON.parse(edit);
                        } catch {
                          throw new Error("The edited JSON is not valid.");
                        }
                        await request("/api/items/" + selected + "/action", {
                          action: "save-output",
                          output: parsed,
                        });
                      }, "Manual entry validated and saved.")
                    }
                  >
                    <Check size={15} /> Validate & save manual entry
                  </button>
                </div>
              )}
            </>
          ) : (
            <div className="panel-empty">Select an item to inspect it.</div>
          )}
        </main>
        <footer>
          <span>ONE FAMILY. EVERY DETAIL.</span>
          <span>Borderlens workshop · 0.52.3</span>
        </footer>
      </section>
      <input
        ref={input}
        type="file"
        accept=".zip"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void upload(file);
          e.target.value = "";
        }}
      />
      {viewedSource && (
        <SourceViewer
          key={viewedSource.id}
          source={viewedSource}
          recapture={() => {
            const url = viewedSource.url;
            setViewedSource(null);
            const ownerId = viewedSource.inheritedFrom?.id || f?.id;
            if (ownerId) return chromeHelper.openPage(ownerId, url);
          }}
          onClose={() => setViewedSource(null)}
        />
      )}
      {sharedScope && (
        <SharedSources
          key={scopeLabel(sharedScope) + ":" + returnSourceId}
          initial={sharedScope}
          onClose={() => setSharedScope(null)}
          onChange={() => void refresh()}
          openPage={(id, url) => chromeHelper.openPage(id, url)}
        />
      )}
      <ChromeHelperSetup helper={chromeHelper} />
      {settingsOpen && (
        <div className="modal-backdrop" onClick={() => setSettingsOpen(false)}>
          <section
            className="settings-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Workshop settings"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="close-modal"
              onClick={() => setSettingsOpen(false)}
            >
              <X size={20} />
            </button>
            <div className="eyebrow">YOUR WORKSHOP</div>
            <h2>Settings</h2>
            {(["grok", "codex"] as const).map((name) => {
              const status = agents?.providers?.[name] || agents;
              return (
                <div className="codex-status" key={name}>
                  <span
                    className={
                      status?.ready || status?.chatgpt
                        ? "connection-dot"
                        : "connection-dot offline"
                    }
                  />
                  <div>
                    <strong>{agentNames[name]}</strong>
                    <small>{status?.message || "Checking connection…"}</small>
                    {status?.lastError && (
                      <small className="agent-error">
                        Last call: {status.lastError}
                      </small>
                    )}
                  </div>
                </div>
              );
            })}
            <button
              className="button quiet"
              onClick={() =>
                void request("/api/agents/recheck", {}).then(setAgents)
              }
            >
              Recheck agents
            </button>
            <p className="muted small">
              Uses your signed-in Grok/Codex subscriptions. Grok stays on 4.6.
              Writing uses low effort; extraction/research uses medium. Failed
              calls or calls over five minutes switch to the other agent. No
              API-key fallback.
            </p>
            <label>
              Codex model
              <input
                defaultValue={state.settings.model}
                key={state.settings.model}
                placeholder="Codex default"
                onBlur={(e) => {
                  if (e.target.value !== state.settings.model)
                    void setSetting({ model: e.target.value });
                }}
                disabled={busy}
              />
            </label>
            <label>
              Writing preference
              <textarea
                defaultValue={state.settings.writingStyle}
                key={state.settings.writingStyle}
                rows={3}
                disabled={busy}
                onBlur={(e) => {
                  if (e.target.value !== state.settings.writingStyle)
                    void setSetting({ writingStyle: e.target.value });
                }}
              />
            </label>
            <label className="check-label">
              <input
                type="checkbox"
                checked={state.settings.research}
                disabled={busy}
                onChange={(e) => setSetting({ research: e.target.checked })}
              />{" "}
              Research wiki/Lootlemon pages automatically
            </label>
            <label>
              Maximum items per run
              <input
                type="number"
                min={1}
                max={10000}
                defaultValue={state.settings.maxItems}
                disabled={busy}
                onBlur={(e) => {
                  const n = Number(e.target.value);
                  if (n !== state.settings.maxItems)
                    void setSetting({ maxItems: n });
                }}
              />
            </label>
            <div className="settings-divider" />
            <ProjectBackupActions
              ui={{
                selection: selected,
                groups: collapsed,
                tab: tab as any,
                view: view as any,
                query,
                filter,
              }}
              disabled={
                busy ||
                state.coverage.status === "running" ||
                !!state.identitySync ||
                working ||
                state.run.status === "pausing"
              }
            />
            <div className="settings-divider" />
            <h3>Reset project</h3>
            <p className="muted small">
              Restart generated work while retaining research/corrections, or
              clear all project data, restored images, caches and automatic
              recovery copies. Downloaded backups and built-in assets stay
              intact.
            </p>
            <select
              value={resetScope}
              onChange={(e) => setResetScope(e.target.value)}
            >
              <option value="">Choose reset scope…</option>
              <option value="generated">
                Restart generated work · keep research & corrections
              </option>
              <option value="all">Clear the entire project</option>
            </select>
            {resetScope && (
              <>
                <label>
                  Type RESET to confirm
                  <input
                    value={resetConfirm}
                    onChange={(e) => setResetConfirm(e.target.value)}
                  />
                </label>
                <button
                  className="button danger-button"
                  disabled={
                    busy ||
                    working ||
                    state.coverage.status === "running" ||
                    !!state.identitySync ||
                    resetConfirm !== "RESET"
                  }
                  onClick={() =>
                    act(async () => {
                      await request("/api/reset", {
                        scope: resetScope,
                        confirmation: resetConfirm,
                      });
                      if (resetScope === "all") {
                        for (const key of Object.keys(localStorage))
                          if (key.startsWith("borderlens."))
                            localStorage.removeItem(key);
                        window.location.reload();
                        return;
                      }
                      setResetScope("");
                      setResetConfirm("");
                      setDetail(null);
                    }, "Project reset completed.")
                  }
                >
                  Reset selected scope
                </button>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
