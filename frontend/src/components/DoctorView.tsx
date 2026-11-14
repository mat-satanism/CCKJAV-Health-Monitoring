import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Alarm, DoctorView as View, Meta, MissionInfo, NowLine } from '../types'
import { CrewChart } from './CrewChart'
import { AlertList } from './MissionView'
import { AlarmLog, Report } from './Report'

// One tab for both medical roles: the CMO onboard (live data, acts now) and the flight surgeon
// on Earth (data and advice both travel ~20 minutes, so they work on trends and risks).
// The CMO is busy with mission work, so the onboard view starts with one line per person and what to do;
// the full tables are one click away. The ground gets the overnight report.

function NowList({ lines }: { lines: NowLine[] }) {
  return (
    <section className="panel now">
      <h2>Right now</h2>
      {lines.map((l) => (
        <div key={l.astronaut_id} className={`now-row status-${l.level}`}>
          <span className="dot" />
          <strong>{l.name}</strong>
          <span className="what">{l.what}{l.symptoms.length > 0 && <small className="muted"> ({l.symptoms.join(', ')})</small>}</span>
          <span className="do">{l.do}</span>
        </div>
      ))}
    </section>
  )
}

export function DoctorView({ day, mission, meta }: { day: number; mission: MissionInfo; meta: Meta }) {
  const [role, setRole] = useState<'cmo' | 'ground'>('cmo')
  const [view, setView] = useState<View | null>(null)
  const [now, setNow] = useState<NowLine[]>([])
  const [alarms, setAlarms] = useState<Alarm[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.missionDoctor(role), api.missionNow(day), api.missionAlarms(day)])
      .then(([v, n, a]) => { setView(v); setNow(n); setAlarms(a); setError(null) })
      .catch((e) => setError(String(e)))
  }, [role, day])

  if (error) return <p className="err">{error}</p>
  if (!view) return <p className="muted">Loading…</p>

  return (
    <div className="doctor">
      <div className="role-switch" role="tablist" aria-label="Medical role">
        <button role="tab" aria-selected={role === 'cmo'} className={role === 'cmo' ? 'on' : ''}
          onClick={() => setRole('cmo')}>Crew medical officer (onboard)</button>
        <button role="tab" aria-selected={role === 'ground'} className={role === 'ground' ? 'on' : ''}
          onClick={() => setRole('ground')}>Flight surgeon (Earth)</button>
      </div>

      <section className={`panel guidance ${view.role === 'ground' ? 'delayed' : ''}`}>
        <h2>{view.title}</h2>
        {view.role === 'ground' && (
          <p className="delay">
            Data arrives {view.data_delay_min} min late · your advice reaches the crew {view.reply_round_trip_min} min after this data was taken
          </p>
        )}
        <p className="muted">{view.guidance}</p>
      </section>

      <AlertList alerts={view.alerts} />

      {view.role === 'cmo' && <NowList lines={now} />}
      {view.role === 'ground' && <Report day={day} />}
      <CrewChart mission={mission} meta={meta} day={day} />

      <details className="panel more" open={view.role === 'ground'}>
      <summary><h2>Details: risks, anomalies, symptoms</h2></summary>
      <div className="doc-cols">
      <section className="panel">
        <h2>Risks in the next 48 hours</h2>
        {view.risks.length === 0 ? <p className="muted">Nobody above the usual level.</p> : (
          <div className="table-wrap"><table className="doc-table">
            <thead><tr><th>Who</th><th>What</th><th>vs usual</th><th>Signs</th><th>Suggested action</th></tr></thead>
            <tbody>
              {view.risks.map((r) => (
                <tr key={`${r.astronaut_id}-${r.event}`} className={`lvl-${r.level}`}>
                  <td><strong>{r.name}</strong></td>
                  <td>{r.label}</td>
                  <td className={`num risk-${r.level}`}>×{r.multiple} <small className="muted">({Math.round(r.risk * 100)}%)</small></td>
                  <td className="small">{r.signs.join('; ') || '—'}</td>
                  <td className="small muted">{r.action}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
        <p className="muted small">
          Model trained on simulated missions; it has not been validated on real astronauts. Placeholder advice, not medical guidance.
        </p>
      </section>

      <section className="panel">
        <h2>Anomalies today</h2>
        {view.anomalies.length === 0 ? <p className="muted">All values as usual for each person.</p> : (
          <div className="table-wrap"><table className="doc-table">
            <thead><tr><th>Who</th><th>Indicator</th><th>Value</th><th>Usual</th><th>Why</th></tr></thead>
            <tbody>
              {view.anomalies.map((a) => (
                <tr key={`${a.astronaut_id}-${a.type}`} className={`status-${a.status}`}>
                  <td><strong>{a.name}</strong></td>
                  <td><span className="dot" /> {a.label}</td>
                  <td className="num">{a.value} <small className="muted">{a.unit}</small></td>
                  <td className="num muted">{a.norm ?? '—'}</td>
                  <td className="small">{a.message}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </section>
      </div>

      {view.symptoms.length > 0 && (
        <section className="panel">
          <h2>Reported symptoms</h2>
          {view.symptoms.map((s) => (
            <p key={s.astronaut_id}><strong>{s.name}</strong>: {s.symptoms.join(', ')}</p>
          ))}
        </section>
      )}
      </details>

      {view.role === 'cmo' && (
        <details className="panel more">
          <summary><h2>Alarm log, days 1-{day} ({alarms.length})</h2></summary>
          <AlarmLog alarms={alarms} />
        </details>
      )}
    </div>
  )
}
