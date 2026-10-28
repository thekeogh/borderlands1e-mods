# Offline build: isolated payload baseline

Measured at the actual `AI.run` prompt boundary using synthetic fixtures and mock responses. No model calls, provider tokens, costs or provider latency were measured.

Each fixture uses one saved passage and an intentionally repetitive raw definition graph. The source-reading mock returns no facts, so this measures fixed prompt/raw-graph overhead, not complete real-game content. The same fixture code was run before and after the writer change.

| Category     | Previous writer characters | New writer characters | Reduction | Previous total request characters | New total request characters |
| ------------ | -------------------------: | --------------------: | --------: | --------------------------------: | ---------------------------: |
| Weapons      |                     23,190 |                 8,975 |     61.3% |                            33,287 |                       20,605 |
| Shields      |                     23,066 |                 8,970 |     61.1% |                            33,039 |                       20,476 |
| Grenade mods |                     23,055 |                 8,980 |     61.0% |                            33,007 |                       20,465 |
| Class mods   |                     23,055 |                 8,976 |     61.1% |                            33,011 |                       20,465 |
| Artifacts    |                     23,021 |                 8,974 |     61.0% |                            32,945 |                       20,431 |

| Category     | Fresh calls | Cached rebuild | Shared cold index + build | Second item reusing shared index |
| ------------ | ----------: | -------------: | ------------------------: | -------------------------------: |
| Weapons      |           2 |              1 |                         2 |                                1 |
| Shields      |           2 |              1 |                         2 |                                1 |
| Grenade mods |           2 |              1 |                         2 |                                1 |
| Class mods   |           2 |              1 |                         2 |                                1 |
| Artifacts    |           2 |              1 |                         2 |                                1 |

Starting compiler: `0.12.0`. New compiler: `0.13.0`.

New fact-reading prompts include structured metadata, so the first read can be slightly larger. The writer no longer receives the unused raw graph and no longer regenerates established structured fields. Separate tests cover recognised tables making zero source-reading AI calls, cached readings, shared reuse, and targeted corrections.

These are repeatable fixture payload measurements, not a promise of equivalent savings on real items. A source with many Always include facts still makes a larger outline. Model output completeness, provider timing and actual token savings need observation during user-requested real builds.

Reproduce current payloads: `pnpm exec tsx tests/offline-build-baseline.ts`. Its JSON report is saved under `../temp/offline-build-baseline.json`; it uses temporary projects and never contacts providers.
