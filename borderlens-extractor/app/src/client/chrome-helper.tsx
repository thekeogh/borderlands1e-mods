import { useEffect, useRef, useState } from "react";
import { Chrome, CheckCircle2, X, Copy, ArrowUpRight } from "lucide-react";
async function api(url: string, body?: unknown) {
  const response = await fetch(
    url,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const data = await response.json();
  if (!response.ok)
    throw new Error(data.error || "Local workshop request failed.");
  return data;
}
export function helperMessage(type: string, payload?: unknown): Promise<any> {
  return new Promise((resolve, reject) => {
    const requestId = crypto.randomUUID();
    const timer = setTimeout(() => {
      window.removeEventListener("message", listener);
      reject(
        new Error(
          "Chrome helper is not connected. Install it using Chrome helper setup, then refresh this tab.",
        ),
      );
    }, 2500);
    const listener = (event: MessageEvent) => {
      if (
        event.source !== window ||
        event.origin !== location.origin ||
        event.data?.source !== "borderlens-chrome-helper" ||
        event.data.requestId !== requestId
      )
        return;
      clearTimeout(timer);
      window.removeEventListener("message", listener);
      event.data.response?.ok
        ? resolve(event.data.response)
        : reject(
            new Error(
              event.data.response?.error || "Chrome helper did not respond.",
            ),
          );
    };
    window.addEventListener("message", listener);
    window.postMessage(
      { source: "borderlens-workshop", type, requestId, payload },
      location.origin,
    );
  });
}
export function useChromeHelper(callbacks: {
  saved: (message: string) => void;
  error: (message: string) => void;
}) {
  const current = useRef(callbacks);
  current.current = callbacks;
  const [connected, setConnected] = useState(false),
    [setupOpen, setSetupOpen] = useState(false),
    [metadata, setMetadata] = useState<any>(null),
    [opening, setOpening] = useState(false);
  const check = async () => {
    try {
      await helperMessage("HELLO");
      setConnected(true);
    } catch {
      setConnected(false);
    }
  };
  const showSetup = () => {
    setSetupOpen(true);
    void api("/api/chrome-helper")
      .then(setMetadata)
      .catch((error) => current.current.error(error.message));
    void check();
  };
  useEffect(() => {
    let stopped = false;
    const ping = async () => {
      try {
        await helperMessage("HELLO");
        if (!stopped) setConnected(true);
      } catch {
        if (!stopped) setConnected(false);
      }
    };
    void ping();
    const timer = setInterval(ping, 5000);
    const listener = async (event: MessageEvent) => {
      const data = event.data;
      if (
        event.source !== window ||
        event.origin !== location.origin ||
        data?.source !== "borderlens-chrome-helper" ||
        data.type !== "IMPORT_CAPTURE" ||
        typeof data.captureId !== "string"
      )
        return;
      let response;
      try {
        const result = await api("/api/chrome-helper/capture", {
          jobId: data.jobId,
          token: data.token,
          url: data.url,
          html: data.html,
        });
        if (result.status === "failed") throw new Error(result.message);
        response = { ok: true, ...result };
        current.current.saved(result.message);
      } catch (error: any) {
        response = { ok: false, error: error.message };
        current.current.error(error.message);
      }
      window.postMessage(
        {
          source: "borderlens-workshop",
          type: "CAPTURE_RESULT",
          captureId: data.captureId,
          response,
        },
        location.origin,
      );
    };
    window.addEventListener("message", listener);
    return () => {
      stopped = true;
      clearInterval(timer);
      window.removeEventListener("message", listener);
    };
  }, []);
  const openPage = async (familyId: string, url: string) => {
    if (!connected) {
      showSetup();
      return;
    }
    setOpening(true);
    try {
      const ticket = await api("/api/chrome-helper/jobs", { familyId, url });
      await helperMessage("OPEN_SOURCE", ticket);
      current.current.saved(
        "Article opened in Chrome. When it is visible, click Borderlens Page Capture → Send page to Borderlens.",
      );
    } catch (error: any) {
      current.current.error(error.message);
    } finally {
      setOpening(false);
    }
  };
  return {
    connected,
    setupOpen,
    setSetupOpen,
    metadata,
    showSetup,
    check,
    opening,
    openPage,
  };
}
export function ChromeHelperSetup({
  helper,
}: {
  helper: ReturnType<typeof useChromeHelper>;
}) {
  const [message, setMessage] = useState("");
  if (!helper.setupOpen) return null;
  const copy = async (value: string, label: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setMessage(label + " copied.");
    } catch {
      setMessage("Select and copy the text below.");
    }
  };
  return (
    <div className="modal-backdrop" onClick={() => helper.setSetupOpen(false)}>
      <section
        className="settings-modal chrome-setup"
        role="dialog"
        aria-modal="true"
        aria-label="Chrome helper setup"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          className="close-modal"
          aria-label="Close Chrome helper setup"
          onClick={() => helper.setSetupOpen(false)}
        >
          <X size={20} />
        </button>
        <div className="eyebrow">ONE-TIME CHROME SETUP</div>
        <h2>
          <Chrome size={23} /> Capture wiki articles
        </h2>
        <p className="muted">
          Open the article normally. Send its visible content straight to this
          workshop—no HTML copying.
        </p>
        <div
          className={"helper-connection " + (helper.connected ? "ready" : "")}
        >
          <CheckCircle2 size={17} />
          <strong>
            {helper.connected
              ? "Chrome helper connected"
              : "Install the local Chrome helper"}
          </strong>
          <button className="text-button" onClick={helper.check}>
            Check again
          </button>
        </div>
        <ol className="setup-steps">
          <li>
            <strong>Open Chrome’s extensions page</strong>
            <div className="setup-buttons">
              <button
                className="button secondary"
                onClick={async () => {
                  try {
                    await api("/api/chrome-helper/open-extensions", {});
                    setMessage(
                      "Enable Developer mode on the Chrome extensions page.",
                    );
                  } catch {
                    setMessage(
                      "Paste chrome://extensions/ into Chrome’s address bar.",
                    );
                  }
                }}
              >
                Open extensions <ArrowUpRight size={13} />
              </button>
              <button
                className="text-button"
                onClick={() => copy("chrome://extensions/", "Chrome setup URL")}
              >
                Copy URL
              </button>
            </div>
          </li>
          <li>
            <strong>Turn on Developer mode, then click Load unpacked</strong>
            <p>
              Select the folder below. It already contains everything you need.
            </p>
            <input
              aria-label="Chrome helper folder"
              readOnly
              value={helper.metadata?.extensionPath || "Loading helper folder…"}
              onFocus={(event) => event.target.select()}
            />
            <button
              className="text-button"
              disabled={!helper.metadata?.extensionPath}
              onClick={() =>
                copy(helper.metadata.extensionPath, "Extension folder path")
              }
            >
              <Copy size={13} /> Copy folder path
            </button>
            {helper.metadata?.platform === "darwin" && (
              <p className="small">
                In the folder picker, press ⌘⇧G, paste the path, press Return,
                then Select.
              </p>
            )}
          </li>
          <li>
            <strong>Pin Borderlens Page Capture</strong>
            <p>
              Use Chrome’s Extensions puzzle button. If the connection stays
              off, refresh this workshop tab.
            </p>
          </li>
        </ol>
        <div className="helper-how">
          <strong>After setup</strong>
          <p>
            On an item’s Sources & evidence tab, click{" "}
            <b>Open wiki in Chrome</b>. Once loaded, click the extension icon →{" "}
            <b>Send page to Borderlens</b>. Return here to rebuild the item.
          </p>
          <small>
            Keep this workshop tab open. Imports received during processing are
            applied at its next safe checkpoint.
          </small>
        </div>
        {message && (
          <p role="status" className="setup-message">
            {message}
          </p>
        )}
        <div className="setup-buttons">
          <button
            className="button primary"
            onClick={() => helper.setSetupOpen(false)}
          >
            {helper.connected ? "Done" : "Back to workshop"}
          </button>
          <a className="text-button" href="/api/chrome-helper/extension.zip">
            Download helper ZIP
          </a>
        </div>
        <p className="muted small">
          Chrome requires Load unpacked once; websites cannot install extensions
          automatically. Captures article content only. No cookies or background
          wiki fetching.
        </p>
      </section>
    </div>
  );
}
