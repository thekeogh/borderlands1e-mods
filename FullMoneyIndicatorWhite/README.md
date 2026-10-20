# Full Money Indicator White

**3.0.1 · keogh · Borderlands / GOTY Enhanced**

Shows your full wallet with the inventory’s **gold dollar symbol with a black outline** and crisp
white **LV-label lettering with a black edge**, including at 4K. Money handling
is unchanged.

## Install

1. **Fully close the game**, including exiting to Windows.
2. Copy `FullMoneyIndicatorWhite.sdkmod` into the game’s `sdk_mods` folder.
3. Disable **Full Money Indicator** and enable **Full Money Indicator White**.
4. Start or continue your game normally.

A full restart is required after updating: the text field loads with the HUD.

Adjust **Y offset** in the mod’s options: **positive moves down**, **negative
moves up**, **0 keeps the original bottom spacing**. Range: −200 to +200 in
one-pixel steps at 1920×1080, scaled for other resolutions. Existing Y settings
are retained. The amount stays horizontally centered.

Appearance is fixed at the final settings: **dollar size 105%**, **spacing 7**
(scaled pixels at 1920×1080), and **amount size 100%**. The symbol and amount
stay centred together; the Y offset remains adjustable.

For troubleshooting, **F11 during gameplay** exports a ZIP to
`sdk_mods/settings/FullMoneyIndicatorWhite/diagnostics/`. Exports are manual only.

Based on **Full Money Indicator 1.0.1** by
[eeriegoesd](https://eeriegoesd.com/gaming/mods/).
Original wallet reading, formatting, update interval and overflow protection
are unchanged. Native fonts and the currency contour are read from the installed game; no
game artwork or fonts are included in this download.
[GPL-3.0-or-later](LICENSE).
