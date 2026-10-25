import React, { useEffect, useState } from "react";
import { Image as ImageIcon, TriangleAlert, RefreshCw } from "lucide-react";
import {
  imageUrl,
  type ImageCoverage,
  type ImageMatch,
} from "../shared/images";
import { categoryFolders, itemSlug } from "../shared/website";
export function ItemImage({
  name,
  match,
  library,
  busy,
  refresh,
  choose,
}: {
  name: string;
  match?: ImageMatch;
  library: ImageCoverage | null;
  busy: boolean;
  refresh: () => Promise<void>;
  choose: (body: { image?: string | null; automatic?: boolean }) => void;
}) {
  const [failed, setFailed] = useState(false),
    [refreshing, setRefreshing] = useState(false),
    [refreshMessage, setRefreshMessage] = useState(""),
    [refreshError, setRefreshError] = useState("");
  const reloadFolder = async () => {
    if (refreshing) return;
    setRefreshing(true);
    setRefreshMessage("");
    setRefreshError("");
    try {
      await refresh();
      setRefreshMessage("Folder refreshed.");
    } catch (error: any) {
      setRefreshError(error.message || "Could not refresh the image folder.");
    } finally {
      setRefreshing(false);
    }
  };
  useEffect(() => setFailed(false), [match?.image, library?.revision]);
  const missing = !match?.image || failed;
  return (
    <section className="item-image-panel" aria-label="Item image">
      {missing ? (
        <div className="item-image-placeholder">
          <ImageIcon size={32} />
          <strong>
            {match?.method === "ambiguous"
              ? "Image needs a match"
              : failed
                ? "Image could not be loaded"
                : "Image missing"}
          </strong>
          <span>
            {match?.method === "ambiguous"
              ? "Several files match this name. Choose the correct image below."
              : "Add an image to the local library, or choose an existing file below."}
          </span>
        </div>
      ) : (
        <div className="item-image-stage">
          <img
            src={imageUrl(match!.image!, library?.revision)}
            alt={name}
            onError={() => setFailed(true)}
          />
        </div>
      )}
      <div className="item-image-caption">
        <span>
          {missing ? <TriangleAlert size={14} /> : <ImageIcon size={14} />}
          {match?.image || "No image assigned"}
        </span>
        <span>
          {match?.method === "manual"
            ? "Chosen image"
            : missing
              ? "Needs image"
              : "Automatically matched"}
        </span>
      </div>
      <details className="image-picker">
        <summary>Change image</summary>
        <div className="image-picker-heading">
          <label htmlFor="item-image-file">Image file</label>
          <button
            type="button"
            className="text-button"
            disabled={refreshing}
            onClick={() => void reloadFolder()}
            title="Reload the local image file list without interrupting the run."
          >
            <RefreshCw size={12} className={refreshing ? "spin" : ""} />
            {refreshing ? "Refreshing…" : "Refresh folder"}
          </button>
        </div>
        <select
          id="item-image-file"
          aria-label="Item image file"
          value={match?.image || ""}
          disabled={busy || refreshing || !library}
          onChange={(e) => choose({ image: e.target.value || null })}
        >
          <option value="">No image</option>
          {library?.files.map((file) => (
            <option key={file} value={file}>
              {file}
            </option>
          ))}
        </select>
        {refreshMessage && (
          <small className="image-refresh-message" role="status">
            {refreshMessage}
          </small>
        )}
        {refreshError && (
          <small className="image-refresh-error" role="alert">
            {refreshError}
          </small>
        )}
        <button
          className="text-button"
          disabled={busy || refreshing}
          onClick={() => choose({ automatic: true })}
        >
          Use automatic matching
        </button>
      </details>
    </section>
  );
}
export function ImageCoveragePanel({
  library,
  select,
  refresh,
}: {
  library: ImageCoverage | null;
  select: (id: string) => void;
  refresh: () => void;
}) {
  const [filter, setFilter] = useState("missing"),
    [query, setQuery] = useState("");
  if (!library)
    return (
      <section className="image-coverage">
        <h2>Image coverage</h2>
        <p>Loading local images…</p>
      </section>
    );
  const rows = library.items.filter(
    (item) =>
      (filter === "all" ||
        (filter === "matched" ? !!item.image : !item.image)) &&
      `${item.name} ${item.category}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  return (
    <section className="image-coverage" aria-label="Image coverage">
      <div className="image-coverage-heading">
        <div>
          <h2>Image coverage</h2>
          <p>
            {library.files.length} local images · {library.summary.matched}{" "}
            matched · {library.summary.missing} missing ·{" "}
            {library.summary.ambiguous} need a match
          </p>
        </div>
        <button className="button secondary" onClick={refresh}>
          <RefreshCw size={14} />
          Refresh images
        </button>
      </div>
      <div className="image-coverage-controls">
        <select
          aria-label="Image coverage filter"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="missing">Missing / needs a match</option>
          <option value="matched">Matched images</option>
          <option value="all">All candidates</option>
        </select>
        <input
          aria-label="Find image candidate"
          placeholder="Find an item…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <div className="table-wrap image-coverage-table">
        <table>
          <thead>
            <tr>
              <th>Item</th>
              <th>Category</th>
              <th>Image</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((item) => (
              <tr key={item.id}>
                <td>
                  <button
                    className="text-button"
                    onClick={() => select(item.id)}
                  >
                    {item.name}
                  </button>
                </td>
                <td>{item.category}</td>
                <td>
                  {item.image ? (
                    item.image
                  ) : (
                    <>
                      <strong className="image-missing-label">
                        {item.method === "ambiguous"
                          ? "Needs a match"
                          : "Missing"}
                      </strong>
                      <small>
                        {item.candidates.length
                          ? item.candidates.join(" · ")
                          : `${categoryFolders[item.category as keyof typeof categoryFolders]}/${itemSlug(item.name)}.png`}
                      </small>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <p className="empty-inline">No items in this view.</p>}
      </div>
      <p className="muted">
        Includes captured candidates awaiting review. Deliberately excluded
        items are hidden. Image matching never interrupts a build.
      </p>
    </section>
  );
}
