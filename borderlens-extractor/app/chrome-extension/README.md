# Borderlens Page Capture

Use **Chrome helper** in the local workshop for setup.

1. Open `chrome://extensions/` in Chrome and turn on **Developer mode**.
2. Click **Load unpacked** and select this folder (the one containing manifest.json).
3. Pin **Borderlens Page Capture** using Chrome’s Extensions puzzle menu.

Keep the workshop tab open. In **Sources & evidence**, click **Open wiki in Chrome**. When the article is visible, click the extension icon, then **Send page to Borderlens**. Return to the workshop and rebuild the item. No HTML copying, cookies, API keys or browser-profile configuration required.

Only the article you explicitly send is captured. The helper does not fetch wiki pages or solve access challenges. Wiki text must be visible in the normal browser. Captures are bound to the item and article opened by the workshop, expire after 30 minutes, and are saved locally. If processing is active, imports apply at its next safe checkpoint.

If you move this project, remove/reload the unpacked extension from its new folder. After changing extension source, use its **Reload** button on chrome://extensions/, then refresh the workshop tab.
