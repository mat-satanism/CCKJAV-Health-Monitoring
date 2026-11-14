import { useEffect, useState } from 'react'
import {
  CartesianGrid, Legend, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from '../api'
import type { AstronautHistory, MissionInfo, Meta } from '../types'

// The whole crew on one chart: each person's distance from their OWN norm (Bayesian prediction),
// in prediction scales. 0 = as expected; the shaded band (about ±2) is the 95% "usual" range.
const COLORS = ['#7cc4e0', '#f0b429', '#b48ead', '#5bb98c', '#e88c6a']

export function CrewChart({ mission, meta, day }: { mission: MissionInfo; meta: Meta; day: number }) {
  const [hist, setHist] = useState<Record<string, AstronautHistory> | null>(null)
  const [ind, setInd] = useState('heart_rate')

  useEffect(() => {
    Promise.all(mission.crew.map((c) => api.astronautHistory(c.astronaut_id).then((h) => [c.astronaut_id, h] as const)))
      .then((pairs) => setHist(Object.fromEntries(pairs)))
      .catch(() => setHist(null))
  }, [mission, day])

  if (!hist) return null
  const data = Array.from({ length: mission.days_total }, (_, i) => {
    const row: Record<string, number | null> = { day: i + 1 }
    for (const c of mission.crew) {
      const p = hist[c.astronaut_id][ind][i]
      row[c.name] = p.z
    }
    return row
  })

  return (
    <section className="panel crew-chart">
      <div className="chart-head">
        <h2>Crew over the mission</h2>
        <select value={ind} onChange={(e) => setInd(e.target.value)} aria-label="Indicator">
          {Object.entries(meta.indicators).map(([id, m]) => <option key={id} value={id}>{m.label}</option>)}
        </select>
      </div>
      <p className="small muted">Distance from each person's own expected value. Shaded = their usual range (95%). Starts after 6 days of calibration.</p>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -20 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <ReferenceArea y1={-2} y2={2} fill="var(--accent)" fillOpacity={0.08} />
          <XAxis dataKey="day" tick={{ fontSize: 10, fill: 'var(--muted)' }} interval={4} />
          <YAxis tick={{ fontSize: 10, fill: 'var(--muted)' }} domain={[-8, 8]} allowDataOverflow />
          <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
            labelFormatter={(d) => `Day ${d}`} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <ReferenceLine x={day} stroke="var(--text)" strokeOpacity={0.5} />
          {mission.crew.map((c, n) => (
            <Line key={c.astronaut_id} dataKey={c.name} stroke={COLORS[n % COLORS.length]} dot={false}
              strokeWidth={1.8} connectNulls={false} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </section>
  )
}
