# Local API checks

`api/openapi.yaml` is the local service contract. The schemas used for catalogue
validation live in `src/shared/models.ts`. No Postman workspace is required.

```sh
postman spec lint api/openapi.yaml --issueType syntax --no-report-events
postman simulation run postman/simulations/research.sim.yaml --port 4318 --no-history --output ndjson
BORDERLENS_SIMULATION=http://127.0.0.1:4318/research pnpm test
```

The research simulation models documented MediaWiki category pagination and
ordinary HTML responses, blocked robots paths and upstream HTML errors. It is
not a live Borderlands/Fandom or Lootlemon dataset. No owning-team mock was reused:
Postman is signed out and these public content sources provide no confirmed owner
mock here. Orbit discovery returned MediaWiki transformation endpoints, not the
category query used here; the integration uses official MediaWiki query docs.
No workspace, mock or user data is uploaded/published by these checks.
