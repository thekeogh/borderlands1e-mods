import { useRef, useState } from "react";
import { Download, Upload } from "lucide-react";
import { BackupUI, backupFilename } from "../shared/project-backup";
export function readRestoredBackupUI(): BackupUI | null {
  try {
    return BackupUI.parse(
      JSON.parse(localStorage.getItem("borderlens.restored-ui") || "null"),
    );
  } catch {
    return null;
  }
}
export function ProjectBackupActions({
  ui,
  disabled,
}: {
  ui: BackupUI;
  disabled: boolean;
}) {
  const input = useRef<HTMLInputElement>(null),
    [pending, setPending] = useState(""),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const exportData = async () => {
    setPending("export");
    setError("");
    setNotice("");
    try {
      // Request the native save dialog during the click gesture, before fetching.
      const handle =
        typeof (window as any).showSaveFilePicker === "function"
          ? await (window as any).showSaveFilePicker({
              suggestedName: backupFilename(),
              types: [
                {
                  description: "Borderlens project backup",
                  accept: { "application/zip": [".zip"] },
                },
              ],
            })
          : null;
      const response = await fetch("/api/project-backup/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(ui),
      });
      if (!response.ok)
        throw Error(
          (await response.json()).error || "Could not export project data.",
        );
      if (handle && response.body) {
        await response.body.pipeTo(await handle.createWritable());
      } else {
        const blob = await response.blob(),
          url = URL.createObjectURL(blob),
          link = document.createElement("a");
        link.href = url;
        link.download =
          response.headers
            .get("Content-Disposition")
            ?.match(/filename="([^"]+)"/)?.[1] || backupFilename();
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 60000);
      }
      setNotice("Project backup exported.");
    } catch (e: any) {
      if (e.name !== "AbortError") setError(e.message);
    } finally {
      setPending("");
    }
  };
  const importData = async (file: File) => {
    setPending("import");
    setError("");
    setNotice("");
    try {
      const body = new FormData();
      body.append("backup", file);
      const response = await fetch("/api/project-backup/import", {
        method: "POST",
        body,
      });
      const result = await response.json();
      if (!response.ok)
        throw Error(result.error || "Could not import project data.");
      // The project is already safely restored even if browser storage is unavailable.
      try {
        const restored = BackupUI.parse(result.ui);
        localStorage.setItem("borderlens.selection", restored.selection);
        localStorage.setItem(
          "borderlens.groups",
          JSON.stringify(restored.groups),
        );
        localStorage.setItem(
          "borderlens.restored-ui",
          JSON.stringify(restored),
        );
      } catch {
        setNotice("Project restored. Browser layout could not be restored.");
      }
      window.location.reload();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setPending("");
      if (input.current) input.current.value = "";
    }
  };
  return (
    <section className="project-backup" aria-label="Project backup">
      <h3>Project backup</h3>
      <p className="muted small">
        Export all saved project data: game captures, evidence, JSON,
        corrections, images, history and paused progress. Import replaces the
        current project; a recovery copy is kept.
      </p>
      <div className="backup-actions">
        <button
          type="button"
          className="button secondary"
          disabled={disabled || !!pending}
          onClick={() => void exportData()}
        >
          <Download size={15} />
          {pending === "export" ? "Exporting…" : "Export Data"}
        </button>
        <button
          type="button"
          className="button secondary"
          disabled={disabled || !!pending}
          onClick={() => input.current?.click()}
        >
          <Upload size={15} />
          {pending === "import" ? "Restoring…" : "Import Data"}
        </button>
      </div>
      <input
        type="file"
        accept=".zip,application/zip"
        aria-label="Import project backup"
        ref={input}
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void importData(file);
        }}
      />
      {disabled && (
        <small>
          Pause processing and wait for the current step to finish first.
        </small>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
    </section>
  );
}
