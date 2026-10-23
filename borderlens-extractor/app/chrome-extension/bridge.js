// Runs only on the local workshop. Never installs a persistent script on the wiki.
(() => {
  if (
    !document.querySelector('meta[name="borderlens-workshop"]') ||
    globalThis.__borderlensBridge
  )
    return;
  globalThis.__borderlensBridge = true;
  const waits = new Map();
  window.addEventListener("message", async (event) => {
    const message = event.data;
    if (
      event.source !== window ||
      event.origin !== location.origin ||
      message?.source !== "borderlens-workshop"
    )
      return;
    if (message.type === "CAPTURE_RESULT") {
      waits.get(message.captureId)?.(message.response);
      return;
    }
    if (
      !["HELLO", "OPEN_SOURCE"].includes(message.type) ||
      typeof message.requestId !== "string"
    )
      return;
    let response;
    try {
      response = await chrome.runtime.sendMessage({
        type: message.type,
        payload: message.payload,
      });
    } catch {
      response = {
        ok: false,
        error:
          "Reload the workshop after installing or updating the Chrome helper.",
      };
    }
    window.postMessage(
      {
        source: "borderlens-chrome-helper",
        requestId: message.requestId,
        response,
      },
      location.origin,
    );
  });
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (sender.id !== chrome.runtime.id || message.type !== "IMPORT_CAPTURE")
      return;
    const timer = setTimeout(() => {
      waits.delete(message.captureId);
      sendResponse({
        ok: false,
        error:
          "The workshop did not respond. Return to it, refresh, then try again.",
      });
    }, 30000);
    waits.set(message.captureId, (response) => {
      clearTimeout(timer);
      waits.delete(message.captureId);
      sendResponse(response);
    });
    window.postMessage(
      {
        source: "borderlens-chrome-helper",
        type: "IMPORT_CAPTURE",
        ...message,
      },
      location.origin,
    );
    return true;
  });
})();
