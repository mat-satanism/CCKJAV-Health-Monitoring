import { useEffect, useState } from 'react'
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from '../api'

interface Point { day: string; value?: number; forecast?: number }

export function TrendChart({ type, baseline }: { type: string; baseline?: number | null }) {
  const [data, setData] = useState<Point[]>([])

  useEffect(() => {
    let alive = true
    Promise.all([api.measurements(type), api.forecast(type)]).then(([ms, fc]) => {
      if (!alive) return
      const hist: Point[] = ms.map((m) => ({ day: m.ts.slice(5, 10), value: m.value }))
      const last = hist[hist.length - 1]
      if (last) last.forecast = last.value // connect history to the forecast line
      const future: Point[] = fc.values.map((v, i) => ({ day: `+${i + 1}d`, forecast: v }))
      setData([...hist, ...future])
    }).catch(() => alive && setData([]))
    return () => { alive = false }
  }, [type])

  if (!data.length) return <p className="muted">No history yet</p>
  return (
    <ResponsiveContainer width="100%" height={160}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
        <CartesianGrid stroke="var(--grid)" vertical={false} />
        <XAxis dataKey="day" tick={{ fontSize: 10, fill: 'var(--muted)' }} interval="preserveStartEnd" />
        <YAxis tick={{ fontSize: 10, fill: 'var(--muted)' }} domain={['auto', 'auto']} />
        <Tooltip contentStyle={{ background: 'var(--panel)', border: '1px solid var(--border)' }} />
        {baseline != null && (
          <ReferenceLine y={baseline} stroke="var(--muted)" strokeDasharray="4 4"
            label={{ value: 'your baseline', fontSize: 10, fill: 'var(--muted)', position: 'insideTopLeft' }} />
        )}
        <Line dataKey="value" stroke="var(--accent)" strokeWidth={2} dot={false} isAnimationActive />
        <Line dataKey="forecast" stroke="var(--accent)" strokeDasharray="3 3" dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}
