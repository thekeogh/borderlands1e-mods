// Injected only after a toolbar click. All selection state stays in this tab.
(() => {
  if (globalThis.__borderlensSelection) {
    globalThis.__borderlensSelection.show();
    return;
  }
  const article =
    location.hostname === "borderlands.fandom.com"
      ? document.querySelector(".mw-parser-output")
      : document.querySelector("main");
  if (!article || !article.textContent.trim())
    throw Error("Wait for the article to load, then try again.");
  const startUrl = location.href;
  const host = document.createElement("div");
  host.id = "borderlens-selection-overlay";
  host.style.cssText =
    "all:initial;position:fixed;inset:0;z-index:2147483647;pointer-events:none;";
  const shadow = host.attachShadow({ mode: "open" });
  shadow.innerHTML = `<style>
    :host{font-family:system-ui,sans-serif;color:#25352b;font-size:13px}*{box-sizing:border-box}[hidden]{display:none!important}.panel,.box{font:13px/1.4 system-ui,sans-serif}
    .panel{pointer-events:auto;position:absolute;right:18px;bottom:18px;width:350px;max-width:calc(100vw - 36px);max-height:70vh;overflow:auto;background:#fbfcf8;border:1px solid #aebda7;border-radius:12px;box-shadow:0 8px 40px #0005;padding:18px}
    h2{font-size:18px;margin:0 0 10px}p{line-height:1.5;margin:8px 0}small{font-size:11px;color:#65745e}button{font:inherit;cursor:pointer;border:1px solid #bdcbb4;background:#fff;color:#315337;border-radius:6px;padding:8px 10px}button:disabled{opacity:.45;cursor:default}button:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid #ba9942;outline-offset:2px}.send{background:#315c3c;color:white;border-color:#315c3c;width:100%;margin-top:12px;font-weight:650}.close{float:right;padding:2px 7px}.tools{display:flex;gap:6px;margin-top:10px}.error{color:#9c352c}.ok{color:#2d643c}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:160px;overflow:auto;background:#eef2e7;padding:8px;font-size:12px}summary{cursor:pointer;margin-top:10px}label{display:block;line-height:1.5;margin:10px 0}
    .box{position:absolute;border:2px solid #348252;background:#33825212;pointer-events:none;min-width:8px;min-height:8px}.box.bad{border-color:#c13e35;background:#c13e3512}.bar{position:absolute;left:-2px;top:-30px;display:flex;align-items:center;gap:4px;white-space:nowrap;background:#fff;border:1px solid currentColor;border-radius:5px;padding:2px;pointer-events:auto;color:#267343;cursor:move;box-shadow:0 1px 4px #0002}.bad .bar{color:#a32d25}.bar button{padding:2px 5px;font-size:11px}.caption{padding:0 4px;font-size:11px;max-width:170px;overflow:hidden;text-overflow:ellipsis}.handle{position:absolute;width:12px;height:12px;background:white;border:2px solid #348252;pointer-events:auto}.bad .handle{border-color:#c13e35}.nw{left:-7px;top:-7px;cursor:nwse-resize}.ne{right:-7px;top:-7px;cursor:nesw-resize}.sw{left:-7px;bottom:-7px;cursor:nesw-resize}.se{right:-7px;bottom:-7px;cursor:nwse-resize}.drawing{pointer-events:none}.hint{padding:8px;border-radius:5px;background:#eef2e7}a{color:#315c3c}
  </style><div id="boxes"></div><section class="panel" aria-label="Borderlens content selection"><button class="close" aria-label="Close selection">×</button><h2>Borderlens · Select content</h2><label class="close-tab-preference"><input id="close-source-tab" type="checkbox" disabled> Close source tab when returning after capture</label><p>Hold <b>Ctrl</b> and drag around the content you want. Release to save a box. Repeat for more.</p><small>Resize using the corner handles. Drag a box’s label to move it. “Fit content” expands to complete paragraphs or tables.</small><p id="count">Saved 0 boxes</p><p class="hint" id="hint">Select some article text to enable sending.</p><details><summary>Preview selected text</summary><pre id="preview">No content selected.</pre></details><label id="partial" hidden><input type="checkbox"> I checked the preview; send partial selections anyway.</label><button class="send" disabled>Send to Borderlens</button><button id="whole" style="width:100%;margin-top:8px">Capture whole page</button><div class="tools"><button id="clear">Clear boxes</button><button id="workshop">Back to workshop</button></div><p id="message" role="status"></p><small>Green = structurally complete text. Red = clipped text/table or no usable content. Green does not guarantee complete facts. Navigation or refresh clears selections.</small></section>`;
  document.documentElement.append(host);
  const $ = (s) => shadow.querySelector(s);
  const boxesRoot = $("#boxes"),
    panel = $(".panel"),
    send = $(".send"),
    ack = $("#partial input");
  const ignored =
    'script,style,iframe,noscript,form,input,textarea,button,nav,header,footer,[contenteditable="true"],.advertisement,.ad-slot,.ad-container';
  const allowed = new Set(
    "DIV P SPAN H1 H2 H3 H4 H5 H6 UL OL LI DL DT DD BLOCKQUOTE PRE CODE TABLE THEAD TBODY TFOOT TR TD TH CAPTION STRONG EM B I SUP SUB BR A SECTION ARTICLE".split(
      " ",
    ),
  );
  const boxes = [];
  let drag = null,
    payload = null,
    busy = false,
    delivered = false,
    raf = 0;
  const point = (e) => ({ x: e.clientX + scrollX, y: e.clientY + scrollY });
  const rectOf = (r) => ({
    x: r.left + scrollX,
    y: r.top + scrollY,
    w: r.width,
    h: r.height,
  });
  const intersects = (a, b) =>
    a.w > 0 &&
    a.h > 0 &&
    a.x < b.x + b.w &&
    a.x + a.w > b.x &&
    a.y < b.y + b.h &&
    a.y + a.h > b.y;
  const contains = (a, b) =>
    b.x >= a.x - 1 &&
    b.y >= a.y - 1 &&
    b.x + b.w <= a.x + a.w + 1 &&
    b.y + b.h <= a.y + a.h + 1;
  const visible = (el) => {
    const style = getComputedStyle(el);
    return (
      style.display !== "none" &&
      style.visibility !== "hidden" &&
      style.opacity !== "0"
    );
  };
  const normalized = (text) =>
    text
      .replace(/[\t\r ]+/g, " ")
      .replace(/\n\s*\n/g, "\n")
      .trim();
  function build() {
    const warnings = boxes.map(() => new Set()),
      used = boxes.map(() => 0);
    const page = document.implementation.createHTMLDocument(document.title),
      main = page.createElement("main");
    const title = page.createElement("h1");
    title.textContent =
      document
        .querySelector("#firstHeading,.page-header__title,h1")
        ?.textContent.trim() || document.title;
    title.append(page.createTextNode("\n"));
    main.append(title);
    let selectedChars = 0;
    function clone(node) {
      if (node.nodeType === Node.TEXT_NODE) {
        if (!node.textContent.trim()) return null;
        const range = document.createRange();
        range.selectNodeContents(node);
        const rects = [...range.getClientRects()]
          .map(rectOf)
          .filter((r) => r.w && r.h);
        const touching = boxes
          .map((b, i) => (rects.some((r) => intersects(b, r)) ? i : -1))
          .filter((i) => i >= 0);
        if (!touching.length) return null;
        const full = touching.filter((i) =>
          rects.every((r) => contains(boxes[i], r)),
        );
        let text = "";
        if (full.length) text = node.textContent;
        else {
          for (const i of touching)
            warnings[i].add("Clipped text — expand to complete the paragraph.");
          // Only inspect characters in intersecting text nodes; preserve selected runs.
          let gap = false;
          for (let at = 0; at < node.length;) {
            const size = node.textContent.codePointAt(at) > 0xffff ? 2 : 1;
            range.setStart(node, at);
            range.setEnd(node, at + size);
            const hit = [...range.getClientRects()].some((r) =>
              boxes.some((b) =>
                contains(b, {
                  x: r.left + scrollX + r.width / 2,
                  y: r.top + scrollY + r.height / 2,
                  w: 0,
                  h: 0,
                }),
              ),
            );
            if (hit) {
              if (gap && text) text += " ";
              text += node.textContent.slice(at, at + size);
              gap = false;
            } else gap = true;
            at += size;
          }
        }
        for (const i of touching) {
          used[i] += text.trim().length;
          if (!rects.every((r) => contains(boxes[i], r)))
            warnings[i].add("Clipped text — expand to complete the paragraph.");
        }
        selectedChars += text.trim().length;
        return text.trim() ? page.createTextNode(text) : null;
      }
      if (
        node.nodeType !== Node.ELEMENT_NODE ||
        node.matches(ignored) ||
        !visible(node)
      )
        return null;
      // Skip off-selection subtrees before walking their text.
      const bounds = [...node.getClientRects()].map(rectOf);
      if (
        bounds.some((r) => r.w && r.h) &&
        !bounds.some((r) => boxes.some((b) => intersects(b, r)))
      )
        return null;
      if (node.tagName === "BR") return page.createTextNode("\n");
      const children = [];
      for (const child of node.childNodes) {
        const result = clone(child);
        if (result) children.push(result);
      }
      if (!children.length) return null;
      if (node.tagName === "TABLE") {
        const bounds = rectOf(node.getBoundingClientRect());
        for (let i = 0; i < boxes.length; i++)
          if (intersects(boxes[i], bounds) && !contains(boxes[i], bounds))
            warnings[i].add(
              "Partial table — use Fit content to include the whole table.",
            );
      }
      const copy = page.createElement(
        allowed.has(node.tagName) ? node.tagName.toLowerCase() : "div",
      );
      // Keep empty cells in selected rows so partial tables cannot shift column alignment.
      if (node.tagName === "TR") {
        for (const cell of node.children) {
          const match = children.find((c) => c.__original === cell);
          copy.append(
            match || page.createElement(cell.tagName === "TH" ? "th" : "td"),
          );
        }
      } else copy.append(...children);
      if (node.matches("td,th"))
        for (const attr of ["colspan", "rowspan"])
          if (node.hasAttribute(attr))
            copy.setAttribute(attr, node.getAttribute(attr));
      if (node.tagName === "A") {
        try {
          const u = new URL(node.getAttribute("href"), location.href);
          if (u.protocol === "https:") copy.setAttribute("href", u.href);
        } catch {}
      }
      if (
        node.matches(
          "p,li,div,section,article,h1,h2,h3,h4,h5,h6,tr,blockquote,pre",
        )
      )
        copy.append(page.createTextNode("\n"));
      if (node.matches("td,th")) copy.append(page.createTextNode(" "));
      copy.__original = node;
      return copy;
    }
    const selected = clone(article);
    if (selected) main.append(selected);
    page.body.append(main);
    const warningCount = warnings.filter((w, i) => w.size || !used[i]).length;
    for (let i = 0; i < boxes.length; i++)
      boxes[i].issues = !used[i]
        ? ["No usable article text — resize or remove this box."]
        : [...warnings[i]];
    for (const [name, content] of [
      ["borderlens-capture", "selected"],
      ["borderlens-selection-count", String(boxes.length)],
      ["borderlens-selection-warnings", String(warningCount)],
    ]) {
      const meta = page.createElement("meta");
      meta.name = name;
      meta.content = content;
      page.head.append(meta);
    }
    const text = normalized(main.textContent),
      bytes = new TextEncoder().encode(text).byteLength;
    payload = {
      url: location.href.split("#")[0],
      html: "<!doctype html>" + page.documentElement.outerHTML,
    };
    return {
      text,
      bytes,
      warningCount,
      empty: used.some((n) => !n),
      selectedChars,
    };
  }
  function position(box) {
    box.el.style.left = box.x - scrollX + "px";
    box.el.style.top = box.y - scrollY + "px";
    box.el.style.width = box.w + "px";
    box.el.style.height = box.h + "px";
    box.el.querySelector(".bar").style.top =
      box.y - scrollY < 32 ? "4px" : "-30px";
  }
  function refresh() {
    if (delivered) return;
    const data = build();
    ack.checked = false;
    $("#count").textContent =
      `Saved ${boxes.length} ${boxes.length === 1 ? "box" : "boxes"} · ${(data.bytes / 1000).toFixed(1)} KB selected text`;
    $("#preview").textContent = data.selectedChars
      ? data.text
      : "No content selected.";
    $("#partial").hidden = !data.warningCount;
    $("#hint").textContent = !boxes.length
      ? "Select some article text to enable sending."
      : data.empty
        ? "A box has no usable text. Resize it or remove it."
        : data.warningCount
          ? `${data.warningCount} partial selection(s). Check red boxes and the preview, or use Fit content.`
          : "All boxes are structurally clean. Check the preview, then send.";
    $("#hint").className = "hint " + (data.warningCount ? "error" : "ok");
    for (const [i, b] of boxes.entries()) {
      b.el.classList.toggle("bad", !!b.issues.length);
      b.el.querySelector(".caption").textContent =
        `${i + 1} · ${b.issues.length ? "Check selection" : "Clean"}`;
      b.el.querySelector(".caption").title =
        b.issues.join("\n") || "Complete visible text and table boundaries.";
      position(b);
    }
    updateSend();
    return data;
  }
  function updateSend() {
    send.disabled =
      busy ||
      delivered ||
      !boxes.length ||
      boxes.some((b) => b.issues.some((x) => x.startsWith("No usable"))) ||
      (boxes.some((b) => b.issues.length) && !ack.checked);
  }
  function fit(b) {
    const candidates = [
      ...article.querySelectorAll(
        "p,li,h1,h2,h3,h4,h5,h6,table,pre,blockquote,dt,dd",
      ),
    ];
    const touched = candidates.filter(
      (el) => visible(el) && intersects(b, rectOf(el.getBoundingClientRect())),
    );
    const bounds = touched.map((el) => rectOf(el.getBoundingClientRect()));
    if (!bounds.length) return;
    b.x = Math.min(b.x, ...bounds.map((r) => r.x)) - 2;
    b.y = Math.min(b.y, ...bounds.map((r) => r.y)) - 2;
    const right = Math.max(...bounds.map((r) => r.x + r.w), b.x + b.w) + 2,
      bottom = Math.max(...bounds.map((r) => r.y + r.h), b.y + b.h) + 2;
    b.w = right - b.x;
    b.h = bottom - b.y;
    refresh();
  }
  function addBox(r) {
    const b = { ...r, issues: [], el: document.createElement("div") };
    b.el.className = "box";
    b.el.innerHTML =
      '<div class="bar"><span class="caption"></span><button class="fit" title="Snap to complete paragraphs and tables">Fit content</button><button class="remove" aria-label="Remove selection">×</button></div><span class="handle nw"></span><span class="handle ne"></span><span class="handle sw"></span><span class="handle se"></span>';
    b.el.querySelector(".remove").onclick = () => {
      boxes.splice(boxes.indexOf(b), 1);
      b.el.remove();
      refresh();
    };
    b.el.querySelector(".fit").onclick = () => fit(b);
    b.el.addEventListener("pointerdown", (e) => {
      if (busy || delivered || e.target.closest("button")) return;
      e.preventDefault();
      e.stopPropagation();
      const handle = e.target.closest(".handle");
      drag = {
        type: handle ? handle.classList[1] : "move",
        b,
        start: point(e),
        original: { x: b.x, y: b.y, w: b.w, h: b.h },
      };
    });
    boxes.push(b);
    boxesRoot.append(b.el);
    position(b);
    return b;
  }
  function down(e) {
    if (
      !e.ctrlKey ||
      e.button !== 0 ||
      e.composedPath().includes(panel) ||
      busy ||
      delivered
    )
      return;
    if (boxes.length >= 30) {
      $("#message").textContent =
        "Maximum 30 boxes. Remove one before adding another.";
      return;
    }
    e.preventDefault();
    e.stopImmediatePropagation();
    document.getSelection()?.removeAllRanges();
    drag = {
      type: "new",
      start: point(e),
      b: addBox({ ...point(e), w: 1, h: 1 }),
    };
  }
  function move(e) {
    if (!drag) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    const p = point(e),
      d = drag;
    if (d.type === "new") {
      d.b.x = Math.min(d.start.x, p.x);
      d.b.y = Math.min(d.start.y, p.y);
      d.b.w = Math.abs(p.x - d.start.x);
      d.b.h = Math.abs(p.y - d.start.y);
    } else if (d.type === "move") {
      d.b.x = Math.max(0, d.original.x + p.x - d.start.x);
      d.b.y = Math.max(0, d.original.y + p.y - d.start.y);
    } else {
      const o = d.original,
        left = d.type.includes("w") ? Math.min(p.x, o.x + o.w - 8) : o.x,
        top = d.type.includes("n") ? Math.min(p.y, o.y + o.h - 8) : o.y,
        right = d.type.includes("e") ? Math.max(p.x, o.x + 8) : o.x + o.w,
        bottom = d.type.includes("s") ? Math.max(p.y, o.y + 8) : o.y + o.h;
      Object.assign(d.b, { x: left, y: top, w: right - left, h: bottom - top });
    }
    position(d.b);
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      const data = build();
      d.b.el.classList.toggle("bad", !!d.b.issues.length);
      d.b.el.querySelector(".caption").textContent = data.warningCount
        ? "Partial selection"
        : "Clean selection";
    });
  }
  function up() {
    if (!drag) return;
    const b = drag.b;
    drag = null;
    if (b.w < 8 || b.h < 8) {
      boxes.splice(boxes.indexOf(b), 1);
      b.el.remove();
    }
    cancelAnimationFrame(raf);
    refresh();
  }
  function key(e) {
    if (e.key === "Control" && e.type === "keyup") up();
    if (e.key === "Escape" && drag) {
      const b = drag.b;
      if (drag.original) Object.assign(b, drag.original);
      else {
        boxes.splice(boxes.indexOf(b), 1);
        b.el.remove();
      }
      drag = null;
      refresh();
    }
  }
  const scroll = () => {
    for (const b of boxes) position(b);
  };
  const contextmenu = (e) => {
    if (e.ctrlKey) {
      e.preventDefault();
      e.stopImmediatePropagation();
    }
  };
  const api = {
    show() {
      panel.hidden = false;
    },
    status() {
      const data = refresh() || build();
      return {
        count: boxes.length,
        bytes: data.bytes,
        warnings: data.warningCount,
      };
    },
    capture() {
      const previous = payload.html;
      build();
      if (previous !== payload.html) {
        refresh();
        throw Error(
          "Page content changed. Review the updated preview in the on-page panel.",
        );
      }
      updateSend();
      if (send.disabled)
        throw Error(
          "Finish selecting and review partial boxes in the on-page panel.",
        );
      return payload;
    },
  };
  function listener(message, _sender, respond) {
    if (message.type === "SELECTION_STATUS") respond(api.status());
    if (message.type === "FULL_CAPTURE_SAVED") {
      delivered = true;
      for (const button of boxesRoot.querySelectorAll("button"))
        button.disabled = true;
      $("#clear").disabled = true;
      $("#whole").disabled = true;
      $("#whole").textContent = "Whole page saved";
      send.textContent = "Saved to Borderlens";
      $("#message").textContent = "Whole page saved. Return to the workshop.";
      updateSend();
      respond({ ok: true });
    }
  }
  function close() {
    cancelAnimationFrame(raf);
    for (const [type, fn] of [
      ["pointerdown", down],
      ["pointermove", move],
      ["pointerup", up],
      ["pointercancel", up],
      ["keyup", key],
      ["keydown", key],
      ["contextmenu", contextmenu],
    ])
      document.removeEventListener(type, fn, true);
    window.removeEventListener("scroll", scroll);
    window.removeEventListener("resize", scroll);
    chrome.runtime.onMessage.removeListener(listener);
    chrome.storage.onChanged.removeListener(preferenceChanged);
    host.remove();
    delete globalThis.__borderlensSelection;
  }
  for (const [type, fn] of [
    ["pointerdown", down],
    ["pointermove", move],
    ["pointerup", up],
    ["pointercancel", up],
    ["keyup", key],
    ["keydown", key],
    ["contextmenu", contextmenu],
  ])
    document.addEventListener(type, fn, true);
  window.addEventListener("scroll", scroll, { passive: true });
  window.addEventListener("resize", scroll);
  chrome.runtime.onMessage.addListener(listener);
  $(".close").onclick = close;
  $("#clear").onclick = () => {
    boxes.splice(0).forEach((b) => b.el.remove());
    refresh();
  };
  ack.onchange = updateSend;
  const closePreference = $("#close-source-tab");
  chrome.storage.local.get({ closeSourceTab: false }).then((value) => {
    closePreference.checked = value.closeSourceTab;
    closePreference.disabled = false;
  });
  closePreference.onchange = async () => {
    try {
      await chrome.storage.local.set({
        closeSourceTab: closePreference.checked,
      });
    } catch (error) {
      $("#message").textContent = error.message;
    }
  };
  function preferenceChanged(changes, area) {
    if (area === "local" && changes.closeSourceTab)
      closePreference.checked = !!changes.closeSourceTab.newValue;
  }
  chrome.storage.onChanged.addListener(preferenceChanged);
  $("#workshop").onclick = async () => {
    try {
      const result = await chrome.runtime.sendMessage({
        type: "OPEN_WORKSHOP",
      });
      if (!result?.ok)
        throw Error(result?.error || "Unable to return to the workshop.");
    } catch (error) {
      $("#message").textContent = error.message;
      $("#message").className = "error";
    }
  };
  $("#whole").onclick = async () => {
    if (busy || delivered) return;
    busy = true;
    updateSend();
    $("#whole").disabled = true;
    $("#message").textContent = "Saving whole page…";
    $("#message").className = "";
    try {
      const result = await chrome.runtime.sendMessage({ type: "CAPTURE_PAGE" });
      if (!result?.ok)
        throw Error(result?.error || "The workshop did not respond.");
      delivered = true;
      for (const button of boxesRoot.querySelectorAll("button"))
        button.disabled = true;
      $("#clear").disabled = true;
      $("#message").textContent =
        result.message || "Whole page saved. Return to the workshop.";
      send.textContent = "Saved to Borderlens";
      $("#whole").textContent = "Whole page saved";
    } catch (error) {
      $("#message").textContent = error.message;
      $("#message").className = "error";
    } finally {
      busy = false;
      $("#whole").disabled = delivered;
      updateSend();
    }
  };
  send.onclick = async () => {
    if (
      location.href !== startUrl &&
      location.href.split("#")[0] !== startUrl.split("#")[0]
    ) {
      $("#message").textContent =
        "The page changed. Reopen the source from Borderlens.";
      return;
    }
    const previous = payload.html;
    build();
    if (previous !== payload.html) {
      refresh();
      $("#message").textContent =
        "Page content changed. Check the updated preview, then send again.";
      return;
    }
    busy = true;
    updateSend();
    $("#message").textContent = "Saving selected content…";
    try {
      const result = await chrome.runtime.sendMessage({
        type: "DELIVER_SELECTION",
        capture: payload,
      });
      if (!result?.ok)
        throw Error(result?.error || "The workshop did not respond.");
      delivered = true;
      $("#whole").disabled = true;
      for (const button of boxesRoot.querySelectorAll("button"))
        button.disabled = true;
      $("#clear").disabled = true;
      $("#message").textContent =
        result.message || "Selected content saved. Return to the workshop.";
      send.textContent = "Saved to Borderlens";
    } catch (e) {
      $("#message").textContent = e.message;
      $("#message").className = "error";
    } finally {
      busy = false;
      updateSend();
    }
  };
  globalThis.__borderlensSelection = api;
  refresh();
})();
