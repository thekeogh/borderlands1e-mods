// Injected only for an explicit whole-page capture. Reads the rendered DOM; no fetches.
(() => {
  globalThis.__borderlensCapturePage = () => {
    const root =
      location.hostname === "borderlands.fandom.com"
        ? document.querySelector(".mw-parser-output") || document.body
        : document.body;
    if (!root) throw Error("Wait for the article to load, then try again.");
    const copy = root.cloneNode(true);
    copy
      .querySelectorAll(
        "script,style,iframe,noscript,object,embed,svg,canvas,form,input,textarea,select,button,[contenteditable],nav,header,footer,.advertisement,.ad-slot,.ad-container,#borderlens-selection-overlay",
      )
      .forEach((node) => node.remove());
    for (const node of [copy, ...copy.querySelectorAll("*")]) {
      for (const attribute of [...node.attributes]) {
        if (!["colspan", "rowspan", "scope"].includes(attribute.name))
          node.removeAttribute(attribute.name);
      }
    }
    if (copy.textContent.trim().length < 60)
      throw Error(
        "No readable article content yet. Wait for the page to load and try again.",
      );
    const html = document.implementation.createHTMLDocument(document.title);
    const marker = html.createElement("meta");
    marker.name = "borderlens-capture";
    marker.content = "full";
    html.head.append(marker);
    const main = html.createElement("main");
    // Keep every loaded content section, including tab panels on Lootlemon.
    main.append(...copy.childNodes);
    if (!main.querySelector("h1")) {
      const heading = html.createElement("h1");
      heading.textContent =
        document.querySelector("h1")?.textContent || document.title;
      main.prepend(heading);
    }
    html.body.append(main);
    return {
      url: location.href,
      html: "<!doctype html>" + html.documentElement.outerHTML,
    };
  };
})();
