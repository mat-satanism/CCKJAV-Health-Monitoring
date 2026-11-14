# Frontend

React + Vite + TypeScript, charts with Recharts.

```bash
npm install
npm run dev        # http://localhost:5173
```

The backend must be running (see root README). API URL defaults to `http://127.0.0.1:8000`; override with `VITE_API_URL` in `frontend/.env.local`.

## Structure
```
src/
  api.ts                 all backend calls
  types.ts               types mirroring docs/api-contract.md
  App.tsx                layout: top bar, body map, system detail, sidebar
  components/
    BodyMap.tsx          clickable SVG figure, zones colored by status
    SystemPanel.tsx      indicators of the selected body system
    TrendChart.tsx       history + baseline line + 7-day forecast
    CheckIn.tsx          daily measurement form + mood
    Sidebar.tsx          escalation level (insights) and daily tasks
  index.css              theme tokens and status colors
```

## Next ideas
- Nicer body illustration (keep the system ids in `BodyMap.tsx`).
- How-to-measure hints in check-in, system descriptions in `SystemPanel`.
- Streaks and badges, mission timeline replay, ground report screen.
