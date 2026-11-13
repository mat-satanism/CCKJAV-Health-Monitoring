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
Everyone codes against `docs/api-contract.md`. The backend always runs with a synthetic demo mission, so the UI has data from the start. Data/ML work plugs in through `backend/app/analytics.py` and `backend/app/demo.py` (see README).
