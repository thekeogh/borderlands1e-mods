# Economy Buster

**Version 0.1.0 · Author: keogh · Borderlands GOTY Enhanced**

Keep monetary scaling at level 1, from a new character through level 69,
across every playthrough and the DLCs.

## Install

1. Close the game.
2. Copy `dist/EconomyBuster.sdkmod` into the game's `sdk_mods/` folder.
3. Restart, then enable **Economy Buster** in the Mods menu.

Requires the BL1 PythonSDK mod manager. No UPK or other mod is required.

## Economy

- Equipment buying, selling and buyback use level-1 cash values.
- Cash drops, large cash, Marcus bobbleheads and skag pearls use level-1 scaling.
- Mission cash rewards use level-1 scaling, retaining each mission's multiplier.
- Ammo SDUs and Moxxi bank upgrades use level-1 price scaling.
- Skill respec formulas and the death-fee ceiling use level 1.
  Death still charges the native wallet percentage, up to that low ceiling.
- Fixed ammo/health prices, item-value differences and vendor markups remain native.

Your existing money is retained; there is no wallet cap or automatic deduction.
Money can still accumulate. Player/mission/item levels, XP, gear stats, rarity,
loot generation, enemy balance and quest progress are unaffected.

Designed to run alongside **One Playthrough**: its level changes do not increase
Economy Buster's cash scaling. Native wallet transactions and other mods' reward
hooks are preserved. Mods that also rewrite these money formulas can conflict;
unknown inputs are left alone and reported in diagnostics. Simultaneous economy
overrides, including the old PT3 economy, are not coordinated.

Disabling restores the captured money inputs and refreshes cash caches. Reopen
inventory/vendor screens to refresh cards. External formula changes made after
our writes are retained. Existing transactions are never reversed.

## Export diagnostics

After viewing prices or collecting/selling something, open:

**Start → Mods → Economy Buster → Export diagnostics**

No keybind is registered. The export also works without a loaded character or
after activation fails. Files are saved under:

```text
sdk_mods/settings/EconomyBuster/diagnostics/economy-buster-<timestamp>.json
```

Includes active/original money inputs, bounded inventory/vendor snapshots,
currency slots, hook registration, recent price/reward queries and observed
wallet deltas, loaded mods and errors. Exporting reads existing state; it does
not generate items, award rewards, change money or force prices to refresh.
The saved path or export failure appears in the SDK log.

This first release needs Windows gameplay verification. Local checks model the
captured formulas and hooks; they cannot prove every map script, native purchase
or multiplayer path. Initial testing should cover purchases/sales, cash pickups,
mission payouts, respecs and death, both alone and with One Playthrough enabled.

## Credits and license

Economy module adapted from keogh's Playthrough 3 economy implementation, originally
part of the Playthrough 3 project based on RedxYeti and Miner Of Worlds' mod.
Only economy code is reused. No PT3 assets or non-economy systems are included.
Definition evidence: supplied Borderlens BL1E extraction, 10 November 2026.
License: GPL-3.0. Release changes: [CHANGELOG.md](CHANGELOG.md).
