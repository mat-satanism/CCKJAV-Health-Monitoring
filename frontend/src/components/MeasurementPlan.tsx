import type { Meta } from '../types'

// What else is measured on a mission, beyond the daily numbers: how and how often, with sources.
export function MeasurementPlan({ meta }: { meta: Meta }) {
  const { items } = meta.content.measurement_plan
  const sources = meta.content.sources
  return (
    <section className="panel plan">
      <h2>Also measured, not daily</h2>
      {items.map((i) => (
        <details key={i.what} className="learn">
          <summary><strong>{i.what}</strong> <small className="muted">{i.how_often}</small></summary>
          <p>{i.why}</p>
          <p className="small"><strong>How.</strong> {i.how}</p>
          <p className="sources small">
            Sources:{' '}
            {i.sources.map((id, n) => sources[id] && (
              <span key={id}>{n > 0 && '; '}<a href={sources[id].url} target="_blank" rel="noreferrer">{sources[id].title}</a></span>
            ))}
          </p>
        </details>
      ))}
    </section>
  )
}
