import type { IndicatorStatus, Meta, Source, SystemId } from '../types'
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

function SourceLinks({ ids, sources }: { ids: string[]; sources: Record<string, Source> }) {
  return (
    <p className="sources small">
      Sources:{' '}
      {ids.map((id, n) => {
        const s = sources[id]
        return s ? (
          <span key={id}>{n > 0 && '; '}<a href={s.url} target="_blank" rel="noreferrer">{s.title}</a>{s.year ? ` (${s.year})` : ''}</span>
        ) : null
      })}
    </p>
  )
}

export function SystemPanel({ system, meta, indicators }: Props) {
  const mine = indicators.filter((i) => meta.indicators[i.type]?.system === system)
  const about = meta.content.systems[system]
  return (
    <section className="panel">
      <h2>{meta.systems[system].label}</h2>
      {about && (
        <div className="about">
          <p>{about.what}</p>
          <p><strong>In space.</strong> {about.in_space}</p>
          <p className="small muted">Spaceflight hazards: {about.hazards.join(', ')}</p>
          <SourceLinks ids={about.sources} sources={meta.content.sources} />
        </div>
      )}
      {mine.map((i) => {
        const m = meta.indicators[i.type]
        const c = meta.content.indicators[i.type]
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
            {i.actions.map((a) => <p key={a} className="action">{a}</p>)}
            <TrendChart type={i.type} baseline={i.baseline} />
            {c && (
              <details className="learn">
                <summary>Why it matters and how to measure</summary>
                <p>{c.why}</p>
                <p><strong>How often.</strong> {c.frequency}. <strong>How to measure.</strong> {c.how_to_measure}</p>
                <ul>{c.advice.map((a) => <li key={a}>{a}</li>)}</ul>
                <SourceLinks ids={c.sources} sources={meta.content.sources} />
              </details>
            )}
          </article>
        )
      })}
      <p className="small muted">General information from NASA and peer-reviewed studies, not medical advice.</p>
    </section>
  )
}
