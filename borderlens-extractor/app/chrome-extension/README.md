# Borderlens Page Capture 1.3.0

Use **Chrome helper** in the local workshop for setup.

1. Open `chrome://extensions/` and enable **Developer mode**.
2. Click **Load unpacked** and choose this folder (containing manifest.json).
3. Pin **Borderlens Page Capture** using Chrome’s Extensions puzzle menu.

Keep the workshop open. Open a Wiki/Lootlemon source from the workshop, click the
pinned extension. Choose **Capture whole page** to immediately save all loaded
article text and tables, or **Select content on page** for boxes. Whole-page capture
also appears in the floating panel and requires no selected boxes. It includes
loaded Lootlemon tab content even on pages without a main/article element. It
cannot load data the website has not rendered yet; wait for the content to load.
Sending either mode uses the same source/recapture ticket and return preferences.
A whole-page recapture replaces an earlier excerpt, and a selection recapture
can replace a full page. Both preserve the source's owner and do not start builds.

For **Select content on page**, a floating panel appears:

- Hold **Ctrl** and drag to select text. Release the mouse or Ctrl to save a box.
- Repeat for up to 30 boxes. Drag labels to move boxes; drag corners to resize.
- **Fit content** snaps outward to complete intersecting paragraphs/lists/tables.
- Use each box’s **×** to remove it, or **Clear boxes** to start again.
- Green means complete visible text/table boundaries; red means clipped text,
  a partial table or no readable text. Green does not prove factual completeness.
- Check **Preview selected text**. Nonempty partial selections can be sent after
  checking the explicit acknowledgement. Empty selections cannot be sent.
- **Send to Borderlens** stores only selected text/HTML, deduplicating overlaps.
  The webpage title is retained for reference. No screenshots or images are sent.
- Return to the workshop and rebuild from saved sources. Saved entries are
  labelled **Selected page content**; only their excerpts are available to AI.

**Back to workshop** opens the source’s item in **Sources & evidence** and scrolls
to/highlights the changed source. Shared sources open their owning shared group.
The **Close source tab when returning after capture** checkbox is available in
both the popup and on-page panel. It is off initially and saved in extension local
storage across captures, reloads and browser restarts. With it on, returning after
an accepted capture closes only that matching external tab, after the workshop
acknowledges navigation. It does not close unsent tabs, tabs navigated elsewhere,
or a tab when workshop navigation fails. Sending alone does not close the tab.

Selections stay in this tab while the panel is open. Reopening the popup resumes
it. Closing the panel or refreshing/navigating clears unsent selections. Scroll
between selections as needed; boxes use document coordinates. Page reflow can
move content, so check the preview before sending. The send check detects changed
content and asks for another review. Capture remains limited to the requested
article and its existing 30-minute import ticket. Reopen expired sources from the
workshop; reload the article to remove old selection UI.

Excerpts remain attached to their item (or explicitly promoted shared parent),
not the global complete-page cache. Website refresh does not expand them into a
full page; recapture the source to replace an excerpt. Re-capturing replaces the
saved content for that URL at its owner, rather than adding another source.

Only content you explicitly send is captured. No cookies, passwords, background
wiki requests or account/API keys. Forms/editable fields, scripts, navigation and
known ad containers are omitted. Captures are stored locally and apply at a safe
checkpoint if processing is active. Extraction cannot read text rendered only in
images/canvas or inside cross-origin frames.

## Reload after an update

Open `chrome://extensions/`, find **Borderlens Page Capture**, click its **Reload**
(circular arrow), then refresh the workshop and article tabs. Open the article
from the workshop again to get a new ticket. No reinstall needed if Chrome loaded
this same folder. If you installed a downloaded copy, replace that copy with the
updated helper ZIP first, or load this project’s extension folder instead.
