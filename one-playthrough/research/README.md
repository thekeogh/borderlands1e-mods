# HUD skull contract, 4.8.0

Source: user-supplied `logs/GfxHUD.upk`. Derived hashes and clip metadata live in
`tests/fixtures/bl1e_hud_icon_contract.json`; no proprietary data is bundled.

The embedded GFX 9 stream starts at offset 13683, length 738541. Extracted locally
and inspected using JPEXS 26.4.0 script/XML exports. Root layout variants contain
`p1`, whose `ring` instance uses sprite 495. The ring places sprite 491 as
`dangerous`, sprite 492 as `elevel`. `dangerous.ename` holds the target name.

Sprite 491 has four frames: normal (1), dangerous (2), deadly (3), friendly (4).
The deadly frame places animated sprite 490 as `skull`. This gives a direct
cosmetic override without modifying the shared LevelDifference_Impossible value.

The runtime uses the displayed target level, warning frame and visibility to
select only +5 targets. Flash native APIs are reflected before invocation. The
viewport callback updates after normal rendering; Windows timing/visibility must
be verified in game. If native rendering overwrites the frame before it can be
seen, F10's hud_icons state/readback counts will guide a more targeted HUD hook.

Actual HUD gameplay-level decision code is native, not present in this package.
No claim is made that this asset proves the native level-difference thresholds.
Ignored local exports are research inputs, not part of the mod distribution.
