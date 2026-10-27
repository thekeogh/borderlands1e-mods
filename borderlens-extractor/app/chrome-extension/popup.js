const title = document.querySelector("#title"),
  message = document.querySelector("#message"),
  send = document.querySelector("#send"),
  back = document.querySelector("#back");
let target;
async function request(type, payload = {}) {
  const response = await chrome.runtime.sendMessage({ type, ...payload });
  if (!response?.ok)
    throw new Error(response?.error || "The Chrome helper did not respond.");
  return response;
}
async function init() {
  try {
    target = await request("TARGET");
    if (!target.job) {
      title.textContent = "Start in your workshop";
      message.textContent =
        "On an item’s Sources & evidence tab, click Open wiki in Chrome. Then return to this helper on that article.";
      return;
    }
    title.textContent = target.job.name;
    back.textContent = "Back to workshop";
    if (target.job.completed) {
      message.textContent =
        "Capture saved. Return to its Sources & evidence entry in the workshop.";
      back.textContent = "Back to workshop";
      return;
    }
    message.textContent =
      "Select just the content you need on the page. Hold Ctrl and drag boxes, then preview and send from the floating panel.";
    send.hidden = false;
    send.disabled = true;
    document.querySelector("#select").hidden = false;
    try {
      const status = await chrome.tabs.sendMessage(target.tab.id, {
        type: "SELECTION_STATUS",
      });
      if (status?.count) {
        message.textContent = `Saved ${status.count} boxes · ${(status.bytes / 1000).toFixed(1)} KB selected text. Continue editing or send from the panel.`;
        send.disabled = status.warnings > 0;
      }
    } catch {}
  } catch (error) {
    title.textContent = "Unable to connect";
    message.textContent = error.message;
    message.className = "error";
  }
}
send.addEventListener("click", async () => {
  send.disabled = true;
  send.textContent = "Saving article…";
  message.className = "";
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: target.tab.id },
      func: () => globalThis.__borderlensSelection?.capture(),
    });
    const capture = results[0]?.result;
    if (!capture)
      throw new Error(
        "No article was captured. Wait for the page to load and try again.",
      );
    const result = await request("DELIVER", { tabId: target.tab.id, capture });
    target = { ...target, appTabId: result.appTabId, appUrl: result.appUrl };
    title.textContent = "Article saved";
    message.textContent =
      result.message ||
      "Saved in Borderlens. Return to the workshop to rebuild this item.";
    message.className = "success";
    send.hidden = true;
    back.textContent = "Back to workshop";
  } catch (error) {
    message.textContent = error.message;
    message.className = "error";
  } finally {
    send.disabled = false;
    send.textContent = "Send selections to Borderlens";
  }
});
document.querySelector("#select").addEventListener("click", async () => {
  try {
    await chrome.scripting.executeScript({
      target: { tabId: target.tab.id },
      files: ["selection.js"],
    });
    window.close();
  } catch (error) {
    message.textContent = error.message;
    message.className = "error";
  }
});
back.addEventListener("click", async () => {
  try {
    if (target?.job)
      await request("OPEN_WORKSHOP", {
        tabId: target.tab?.id || target.job.tabId,
      });
    else
      await chrome.tabs.create({
        url: target?.appUrl || "http://127.0.0.1:4317",
      });
    window.close();
  } catch (error) {
    message.textContent = error.message;
    message.className = "error";
  }
});
const closePreference = document.querySelector("#close-source-tab");
chrome.storage.local.get({ closeSourceTab: false }).then((value) => {
  closePreference.checked = value.closeSourceTab;
  closePreference.disabled = false;
});
closePreference.addEventListener("change", async () => {
  try {
    await chrome.storage.local.set({ closeSourceTab: closePreference.checked });
  } catch (error) {
    message.textContent = error.message;
  }
});
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes.closeSourceTab)
    closePreference.checked = !!changes.closeSourceTab.newValue;
});
init();
