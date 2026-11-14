import type { IndicatorStatus, Meta, SystemId } from '../types'
import { TrendChart } from './TrendChart'

const ARROW = { up: '↑', down: '↓', flat: '→' } as const

// Where the value comes from. Shown on every indicator so the demo never passes
// synthetic or self-reported numbers off as device readings.
const SOURCE_LABEL = { sensor: 'device', manual: 'self-report', synthetic: 'synthetic' } as const

interface Props {
  system: SystemId
  meta: Meta
  indicators: IndicatorStatus[]
}

export function SystemPanel({ system, meta, indicators }: Props) {
  const mine = indicators.filter((i) => meta.indicators[i.type]?.system === system)
  return (
    <section className="panel">
      <h2>{meta.systems[system].label}</h2>
      {/* TODO: system description + how spaceflight affects it (content from research) */}
      {mine.map((i) => {
        const m = meta.indicators[i.type]
        return (
          <article key={i.type} className={`indicator status-${i.status}`}>
            <header>
              <span className="dot" />
              <strong>{m.label}</strong>
              {i.source && <span className={`source source-${i.source}`}>{SOURCE_LABEL[i.source]}</span>}
              <span className="value">
                {i.latest ?? '—'} <small>{m.unit}</small> {i.trend ? ARROW[i.trend] : ''}
              </span>
            </header>
            {i.message && <p className="muted">{i.message}</p>}
            {i.actions.map((a) => <p key={a} className="action">→ {a}</p>)}
            <TrendChart type={i.type} baseline={i.baseline} />
          </article>
        )
      })}
    </section>
  )
}
