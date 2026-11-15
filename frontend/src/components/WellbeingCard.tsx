import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Wellbeing, WellbeingDay } from '../types'

const TARGETS = [
  { key: 'mood', label: 'Lower mood' },
  { key: 'fatigue', label: 'Less energy' },
] as const

const WATCH = 2       // twice the usual chance or more: worth a look
const EXPLAIN = 1.5   // below this the reasons are noise, not a story

/** Real-data demo: chance that tomorrow is a worse day than usual for this person, with the reasons. */
export function WellbeingCard() {
  const [data, setData] = useState<Wellbeing | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => { api.wellbeing().then(setData).catch(() => setError(true)) }, [])

  if (error) return null
  if (!data) return <section className="panel wellbeing"><h2>Tomorrow's outlook</h2><p className="muted">Loading…</p></section>
  if (!data.available || data.days.length === 0) return null

  const today: WellbeingDay = data.days[data.days.length - 1]
  return (
    <section className="panel wellbeing">
      <h2>Tomorrow's outlook <small className="tag">forecast · real data</small></h2>
      {TARGETS.map(({ key, label }) => {
        const f = today[key]
        const m = 'mood' in data.models ? data.models[key] : undefined
        const watch = f.times_usual >= WATCH
        return (
          <div key={key} className={`wb-row ${watch ? 'status-yellow' : 'status-green'}`}>
            <p className="wb-head">
              <span className="dot" /> <strong>{label}</strong>
              <span className="wb-x">{f.times_usual.toFixed(1)}× usual</span>
            </p>
            {f.times_usual >= EXPLAIN && f.reasons.length > 0
              ? (
                <>
                  <p className="muted wb-why">Why:</p>
                  <ul className="wb-reasons">
                    {f.reasons.map((r) => <li key={r}>{r}</li>)}
                  </ul>
                </>
              )
              : <p className="muted wb-why">Nothing unusual for this person.</p>}
            <Strip days={data.days} target={key} />
            {m && (
              <p className="muted wb-score">
                On people it never saw: {m.within_person_auc.toFixed(2)} vs {m.same_as_today_auc.toFixed(2)} for
                "same as today" (AUC within a person, 0.5 = guessing).
              </p>
            )}
          </div>
        )
      })}
      <p className="muted wb-note">
        Learned from other PMData people, never from this one. {anyWatch(today) ? 'Take it easier and check in tomorrow. ' : ''}
        A forecast, not a diagnosis.
      </p>
    </section>
  )
}

function anyWatch(d: WellbeingDay) {
  return d.mood.times_usual >= WATCH || d.fatigue.times_usual >= WATCH
}

/** 30 small bars: the forecast for each next day; a dot where it really was a worse day. */
function Strip({ days, target }: { days: WellbeingDay[]; target: 'mood' | 'fatigue' }) {
  const max = Math.max(3, ...days.map((d) => d[target].times_usual))
  return (
    <figure className="wb-strip" aria-label={`${target} forecast for the last ${days.length} days`}>
      <div className="wb-bars">
        {days.map((d) => {
          const f = d[target]
          return (
            <span key={d.mission_day} className={f.times_usual >= WATCH ? 'hi' : ''}
              title={`${d.for_date}: ${f.times_usual.toFixed(1)}× usual${f.happened === null ? '' : f.happened ? ', it happened' : ', it did not'}`}>
              <i style={{ height: `${(100 * f.times_usual) / max}%` }} />
              {f.happened && <b aria-hidden="true" />}
            </span>
          )
        })}
      </div>
      <figcaption className="muted">last {days.length} days: bar = forecast, dot = it really was a worse day</figcaption>
    </figure>
  )
}
