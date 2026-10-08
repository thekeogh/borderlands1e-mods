# AutopickupBL1E

Automatically picks up ammo, currency (cash, Bobbleheads, Skag Pearls),
health vials, and mission tally collectibles in **Borderlands: Game of the
Year Enhanced (BL1E)**.

## Credit

This is a **BL1E port of [Miner Of Worlds and RedxYeti's original "Auto-Pickup
SDK" mod](https://github.com/MOW531/MOW531-BL1-SDK-Mods/tree/main/Autopickup%20SDK)**,
written for vanilla BL1. All credit for the original idea and implementation
goes to them. This project is licensed GPL-3.0, same as the original, in
compliance with and respect for their license.

## What's different from the original

The original patches each pickup's `ItemDefinition.bAutomaticallyPickup` flag
once at map load and relies on BL1's native auto-pickup/auto-loot systems to
act on it. That doesn't carry over cleanly to BL1E: its native pickup
handling didn't reliably collect items ejected in a burst from a container
(e.g. opening a locker), even with the flag set correctly.

This port instead hooks the game's own pickup lifecycle directly
(`SpawnPickupParticles`, `PickupAtRest`, `TouchedPickupable`,
`SawPickupable`) and runs the same give-sequence the game itself uses for a
manual `[F]` pickup (`HasRoomInInventoryFor` -> `PickupQuery` ->
`ShouldUseCoopRange`/`CloneAndGiveToCoopPawns` -> `ClientSpawnPickupableMesh`
-> `GiveTo`), rather than depending on either of BL1E's native auto-pickup
systems. It's a from-scratch rewrite of the collection mechanism, but that
core give-sequence is carried over directly from the original mod's
`TouchedPickupable` hook.

## Install

Grab `AutopickupBL1E.sdkmod` from the latest release and drop it in your
`sdk_mods` folder, same as any other [PythonSDK](https://bl-sdk.github.io/)
mod for BL1E.

## License

GPL-3.0 — see [LICENSE](LICENSE).
