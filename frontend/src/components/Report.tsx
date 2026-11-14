import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Alarm, Report as R } from '../types'

// Report for the flight surgeon on Earth, made overnight. "Save as PDF" uses the browser's print dialog,
// with print styles that keep only the report.

export function AlarmLog({ alarms }: { alarms: Alarm[] }) {
  if (!alarms.length) return <p className="muted">No alarms.</p>
  return (
    <div className="table-wrap"><table className="doc-table">
      <thead><tr><th>Day</th><th>Who</th><th>What</th><th>Action</th></tr></thead>
      <tbody>
        {[...alarms].reverse().map((a, n) => (
          <tr key={n} className={`status-${a.level}`}>
            <td className="num">{a.day}</td><td>{a.who}</td><td className="small">{a.what}</td>
            <td className="small muted">{a.action}</td>
          </tr>
        ))}
      </tbody>
    </table></div>
  )
}

export function Report({ day }: { day: number }) {
  const [period, setPeriod] = useState<'day' | 'week'>('day')
  const [r, setR] = useState<R | null>(null)

  useEffect(() => { api.missionReport(day, period).then(setR).catch(() => setR(null)) }, [day, period])
  if (!r) return <p className="muted">Loading the report…</p>

  return (
    <section className="panel report">
      <div className="report-head">
        <h2>{period === 'day' ? `Daily report, day ${r.to_day}` : `Weekly report, days ${r.from_day}-${r.to_day}`}</h2>
        <div className="row-buttons no-print">
          <button className={period === 'day' ? 'primary' : ''} onClick={() => setPeriod('day')}>Day</button>
          <button className={period === 'week' ? 'primary' : ''} onClick={() => setPeriod('week')}>Week</button>
          <button onClick={() => window.print()}>Save as PDF</button>
        </div>
      </div>
      <p className="small muted">{r.made} {r.note}</p>
      <div className="table-wrap"><table className="doc-table">
        <thead><tr><th>Who</th><th>Today</th><th>Days off usual</th><th>Notes</th></tr></thead>
        <tbody>
          {r.crew.map((c) => (
            <tr key={c.astronaut_id} className={`status-${c.status}`}>
              <td><strong>{c.name}</strong><br /><small className="muted">{c.role}</small></td>
              <td><span className="dot" /> {c.status}{!c.fit_for_high_demand && <><br /><small className="err">not fit for EVA</small></>}</td>
              <td className="num">{c.days_red} red, {c.days_yellow} yellow</td>
              <td className="small">
                {[...c.off_today, ...c.top_risks.map((x) => `Risk: ${x}`),
                  ...(c.symptoms.length ? [`Symptoms: ${c.symptoms.join(', ')}`] : []),
                  ...c.medication_given, ...c.worse_trends,
                  ...(c.not_ready_days.length ? [`Not ready on day ${c.not_ready_days.join(', ')}`] : []),
                ].join('. ') || 'As usual'}
              </td>
            </tr>
          ))}
        </tbody>
      </table></div>
      <h3>Alarm log ({r.alarms.length}{r.tasks_changed ? `, ${r.tasks_changed} tasks moved` : ''})</h3>
      <AlarmLog alarms={r.alarms} />
    </section>
  )
}
