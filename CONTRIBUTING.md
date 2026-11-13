# How we work

## Branches
- `main` is always runnable. Work in branches, merge via PR.
- One branch per issue: `feat/<area>-<short>` or `fix/<area>-<short>`, e.g. `feat/fe-body-map`, `feat/be-status-endpoint`.
- Areas: `fe`, `be`, `ml`, `content`, `docs`, `pitch`.

## Pull requests
- Small PRs, link the issue (`Closes #12`).
- At least one teammate review before merge.
- If you change the API shape, update `docs/api-contract.md` in the same PR and ping frontend.

## Commits
Short, imperative: `add status endpoint`, `body map: color zones by status`.

## Working in parallel
Everyone codes against `docs/api-contract.md` and `data/sample/*.json`. Frontend does not wait for backend: use the sample JSON until the endpoint exists.
