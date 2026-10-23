const localOrigin = (input) => {
  const u = new URL(input);
  if (
    u.protocol !== "http:" ||
    !["127.0.0.1", "localhost"].includes(u.hostname)
  )
    throw new Error("Open your local Borderlens workshop first.");
  return u.origin;
};
const sourceKey = (input) => {
  const u = new URL(input);
  if (
    u.protocol !== "https:" ||
    !["borderlands.fandom.com", "www.lootlemon.com", "lootlemon.com"].includes(
      u.hostname,
    ) ||
    u.username ||
    u.password ||
    u.port
  )
    throw new Error("Only wiki and Lootlemon articles can be captured.");
  return (
    u.origin +
    decodeURIComponent(u.pathname)
      .replace(/_/g, " ")
      .replace(/\/$/, "")
      .toLowerCase()
  );
};
async function handle(message, sender) {
  if (message.type === "HELLO" || message.type === "OPEN_SOURCE") {
    if (!sender.tab?.id)
      throw new Error("This request must come from the workshop.");
    const origin = localOrigin(sender.url);
    await chrome.storage.session.set({ lastAppUrl: origin });
    if (message.type === "HELLO")
      return { ok: true, version: chrome.runtime.getManifest().version };
    const job = message.payload;
    sourceKey(job.url);
    if (
      !/^[a-f0-9]{32}$/.test(job.jobId) ||
      !/^[a-f0-9]{64}$/.test(job.token) ||
      job.expiresAt < Date.now()
    )
      throw new Error(
        "Import ticket expired; open the article from Borderlens again.",
      );
    const tab = await chrome.tabs.create({ url: job.url });
    const { jobs = {} } = await chrome.storage.session.get("jobs");
    for (const [id, row] of Object.entries(jobs))
      if (row.expiresAt < Date.now()) delete jobs[id];
    jobs[tab.id] = {
      ...job,
      appTabId: sender.tab.id,
      appOrigin: origin,
      tabId: tab.id,
    };
    await chrome.storage.session.set({ jobs });
    return { ok: true, tabId: tab.id };
  }
  if (sender.url !== chrome.runtime.getURL("popup.html"))
    throw new Error("Use the Borderlens extension popup.");
  const { jobs = {}, lastAppUrl = "http://127.0.0.1:4317" } =
    await chrome.storage.session.get(["jobs", "lastAppUrl"]);
  if (message.type === "TARGET") {
    let [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });
    // Also support opening the helper as a standalone extension page.
    if (tab?.url === chrome.runtime.getURL("popup.html")) {
      const pending = Object.values(jobs)
        .filter((job) => job.expiresAt > Date.now())
        .at(-1);
      if (pending) {
        try {
          tab = await chrome.tabs.get(pending.tabId);
        } catch {}
      }
    }
    const job = jobs[tab?.id];
    return {
      ok: true,
      job: job?.expiresAt > Date.now() ? job : null,
      tab: tab ? { id: tab.id, url: tab.url } : null,
      appUrl: lastAppUrl,
    };
  }
  if (message.type === "DELIVER") {
    const job = jobs[message.tabId];
    if (!job || job.expiresAt < Date.now())
      throw new Error(
        "Open this article from Borderlens again; its import ticket expired.",
      );
    if (sourceKey(message.capture.url) !== sourceKey(job.url))
      throw new Error(
        "This is not the requested article. Reopen it from the workshop.",
      );
    if (
      typeof message.capture.html !== "string" ||
      message.capture.html.length > 5000000
    )
      throw new Error("Article is too large to import.");
    try {
      const response = await chrome.tabs.sendMessage(job.appTabId, {
        type: "IMPORT_CAPTURE",
        captureId: crypto.randomUUID(),
        jobId: job.jobId,
        token: job.token,
        url: message.capture.url,
        html: message.capture.html,
      });
      if (!response?.ok)
        throw new Error(
          response?.error || "The workshop could not save this page.",
        );
      delete jobs[message.tabId];
      await chrome.storage.session.set({ jobs });
      return { ...response, appTabId: job.appTabId, appUrl: job.appOrigin };
    } catch (error) {
      throw new Error(
        error.message?.includes("Receiving end") ||
          error.message?.includes("Could not establish")
          ? "The workshop tab was closed or reloaded. Open this source from Borderlens again."
          : error.message,
      );
    }
  }
  throw new Error("Unknown helper request.");
}
chrome.runtime.onMessage.addListener((message, sender, respond) => {
  handle(message, sender).then(respond, (error) =>
    respond({ ok: false, error: error.message }),
  );
  return true;
});
chrome.runtime.onInstalled.addListener(async () => {
  for (const tab of await chrome.tabs.query({
    url: ["http://127.0.0.1/*", "http://localhost/*"],
  })) {
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ["bridge.js"],
      });
    } catch {}
  }
});
