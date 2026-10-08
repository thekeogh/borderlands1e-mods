# AutopickupBL1E 2.0.0

Author: keogh. Private replacement for the supplied Enhanced port v1.5.7.
Original work: Miner Of Worlds and RedxYeti; Enhanced port: galqawala.
GPL-3.0 license retained. Original documentation is in `ORIGINAL_README.md`.

## Why containers and stations can say "Full"

The port is based on the original Auto-Pickup SDK. It keeps the original's
direct collection sequence (`HasRoomInInventoryFor`, `PickupQuery`, coop clone,
pickup mesh and `GiveTo`), but omits the original controller-target cleanup.
The port's touch/seen hooks also fetch `GetCurrentPickupable()` rather than
the item supplied by the event, so they can act on an unrelated or stale target.

An empty pickup can remain in `CurrentSeenPickupable` or
`CurrentTouchedPickupable`. The use key then attempts that pickup instead of
opening a container or using a station. Disabling the old mod does not clear
those fields; ordinary game cleanup can take time, matching the delayed recovery.

Evidence comes from the supplied source, not yet a live reproduction on Windows:

- `../reference/Autopickup SDK/Source/sdk_mods/Autopickup/__init__.py` explicitly
  clears both targets after direct collection and refreshes ammo counts.
- `../reference/AutopickupBL1E/__init__.py` leaves them set after `GiveTo`.
- `../reference/AutoLoot/__init__.py` documents this same empty-husk / "Full" /
  blocked chest/shop issue and uses `PickupSomething(False)` to fix its collection
  lifecycle in BL1/Enhanced.

This is a strong explanation for the reported symptoms. Windows gameplay still
needs to confirm it accounts for every reported interaction failure.

## What changed

- Collection runs through native `PickupSomething(False)`, letting the game
  perform its normal pickup eligibility, award, coop and actor cleanup.
- The exact eligible pickup is selected only for that synchronous native call.
  Other live seen/touched items are restored afterwards, including on exceptions.
  Empty, unavailable or deleting pickups are never restored as interaction targets.
- Touch/seen hooks use the event's `Pickup` and ignore other players' events.
- Readiness/deletion/range checks avoid taking unopened or unavailable loot.
  Full ammo and instant health are left alone. Healing kits can still be carried
  when health is full, provided there is backpack room.
- A reentry guard prevents pickup events raised during collection from starting
  another automatic collection inside it.
- Enable/disable clear stale targets only, preserving live manual loot targets.
- The four existing categories and option settings file `AutoPickupSDK.json`
  are retained: ammo, currency/valuables, health and usable quest collectibles.
  Weapons, equipment and `WillowMissionItem` pickups stay manual.

The mod adds no timers, world scans, persistent actor lists or input/container
hooks. It changes no cash formulas; the PT3 economy mod stays independent.
Collection retains the original port's single-player/host scope. Remote-client
auto collection and coop gameplay have not been validated.

## Install and test

1. Fully close BL1 GOTY Enhanced.
2. Replace `sdk_mods/AutopickupBL1E.sdkmod` with `dist/AutopickupBL1E.sdkmod`.
   If you use an unpacked `AutopickupBL1E` folder, move it out of `sdk_mods`
   first. Keep one AutopickupBL1E copy. Keep the original BL1 Auto-Pickup SDK
   disabled; do not run both pickup mods.
3. Restart and enable **AutopickupBL1E**. Check author **keogh**, version **2.0.0**.
4. With full ammo and health, repeatedly open ordinary containers and red chests
   after collecting cash/ammo. Check New-U interaction without changing mods.
5. Fire some ammo, approach an existing ammo drop, and check collection resumes.
   Check quest tally pickups and that weapons/gear still require manual collection.

No save reset or map reset is required. Restarting is recommended for this first
comparison so old pickup references and the old mod's code are out of the session.
If the bug persists, note the interaction and any `[AutoPickup Enhanced]` messages
in `Binaries/Win64/Plugins/unrealsdk.log`. This mod has no separate JSON exporter.
The existing PT3 F10 exporter is specific to economy diagnostics.

## Validation

25 mocked-SDK tests pass. One runs the untouched original source in memory and
reproduces an empty selected pickup causing the next red chest/New-U use to say
"Full" in the interaction model. The replacement clears that state. Tests also
cover exact event selection, unrelated manual loot, native refusal/exceptions,
reentry, duplicate events, full ammo/health, kit/backpack handling, range, toggles,
quest categories, deleted actors and enable/disable cleanup.

The native engine itself is not installed on this Mac. These tests check the
mod's state and call sequence, not native BL1E execution or its internal scripts.
The first Windows check is still required. No reference files were edited.

Run `python3 -m unittest discover -s tests -v`; build with `python3 package.py`.
