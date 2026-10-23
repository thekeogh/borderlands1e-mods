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
// Self-contained: Chrome serializes this function into the user-invoked active tab.
function captureArticle() {
  const url = new URL(location.href);
  if (
    url.protocol !== "https:" ||
    !["borderlands.fandom.com", "www.lootlemon.com", "lootlemon.com"].includes(
      url.hostname,
    )
  )
    throw new Error("Open the requested wiki or Lootlemon article.");
  const article =
    url.hostname === "borderlands.fandom.com"
      ? document.querySelector(".mw-parser-output")
      : document.querySelector("main");
  if (!article || article.textContent.trim().length < 60)
    throw new Error(
      "The article has not loaded yet. Finish any browser prompts and reopen this helper when the article is visible.",
    );
  const clone = article.cloneNode(true);
  clone
    .querySelectorAll(
      'script,style,iframe,noscript,form,input,textarea,button,nav,header,footer,[contenteditable="true"],.advertisement,.ad-slot,.ad-container',
    )
    .forEach((node) => node.remove());
  const page = document.implementation.createHTMLDocument(document.title);
  page.documentElement.lang = document.documentElement.lang || "en";
  const main = page.createElement("main");
  const heading = page.createElement("h1");
  heading.textContent =
    document
      .querySelector("#firstHeading,.page-header__title,h1")
      ?.textContent?.trim() || document.title;
  main.append(heading, clone);
  page.body.append(main);
  url.hash = "";
  return {
    url: url.href,
    html: "<!doctype html>" + page.documentElement.outerHTML,
  };
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
    message.textContent =
      "When the article has finished loading, send its visible content to this item. Your workshop will save it automatically.";
    send.hidden = false;
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
      func: captureArticle,
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
    back.textContent = "Return to workshop";
  } catch (error) {
    message.textContent = error.message;
    message.className = "error";
  } finally {
    send.disabled = false;
    send.textContent = "Send page to Borderlens";
  }
});
back.addEventListener("click", async () => {
  try {
    const tabId = target?.appTabId || target?.job?.appTabId;
    if (tabId) await chrome.tabs.update(tabId, { active: true });
    else
      await chrome.tabs.create({
        url: target?.appUrl || "http://127.0.0.1:4317",
      });
    window.close();
  } catch {
    await chrome.tabs.create({
      url: target?.appUrl || "http://127.0.0.1:4317",
    });
  }
});
init();
