import { useEffect, useState } from 'react'
import { api } from '../api'
import type { TimelineDay } from '../types'

// The whole mission at a glance: one cell per day, coloured by the crew's worst status,
// with marks for crew alerts, moved tasks and high risks. Click a day to go there.

interface Props {
  day: number
  total: number
  note: string
  onDay: (day: number) => void
  reloadKey: number
}

export function MissionStrip({ day, total, note, onDay, reloadKey }: Props) {
  const [days, setDays] = useState<TimelineDay[]>([])

  useEffect(() => { api.missionTimeline().then(setDays).catch(() => setDays([])) }, [reloadKey])

  return (
    <section className="strip panel" aria-label="Mission timeline">
      <div className="strip-head">
        <span className="strip-day"><span className="strip-kicker">Mission day</span><b key={day}>{day}</b><small>of {total}</small></span>
        <div className="strip-nav">
          <button onClick={() => onDay(day - 1)} disabled={day <= 1} aria-label="Previous day">◀</button>
          <button onClick={() => onDay(day + 1)} disabled={day >= total} aria-label="Next day">▶</button>
        </div>
        <span className="badge-synthetic">{note}</span>
      </div>
      <div className="strip-progress" aria-hidden="true"><i style={{ width: `${(day / total) * 100}%` }} /></div>
      <div className="days">
        {days.map((d) => {
          const what = [
            d.alerts.length ? 'crew alert' : '', d.changed_tasks ? 'task moved or postponed' : '',
            d.high_risks ? `${d.high_risks} high risk${d.high_risks > 1 ? 's' : ''}` : '',
          ].filter(Boolean).join(', ')
          return (
            <button key={d.day} className={`day status-${d.status} ${d.day === day ? 'now' : ''} ${d.day < day ? 'past' : ''}`}
              style={{ '--i': d.day } as React.CSSProperties}
              onClick={() => onDay(d.day)} aria-current={d.day === day ? 'date' : undefined}
              aria-label={`Day ${d.day}, crew status ${d.status}${what ? `, ${what}` : ''}`} title={`Day ${d.day}${what ? `: ${what}` : ''}`}>
              <span className="marks">
                {d.alerts.length > 0 && <span className="mark m-alert" />}
                {d.changed_tasks > 0 && <span className="mark m-task" />}
                {d.high_risks > 0 && <span className="mark m-risk" />}
              </span>
              {d.day}
            </button>
          )
        })}
      </div>
      <p className="strip-key">
        <span><span className="mark m-alert" />crew alert</span>
        <span><span className="mark m-task" />task moved or postponed</span>
        <span><span className="mark m-risk" />risk 5× usual or more</span>
        <span>Cell colour: the crew's worst status that day</span>
      </p>
    </section>
  )
}
