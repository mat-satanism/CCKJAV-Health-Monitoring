import { useEffect, useState } from 'react'
import { api } from '../api'
import type { DoctorView as View } from '../types'
import { AlertList } from './MissionView'

// One tab for both medical roles: the CMO onboard (live data, acts now) and the flight surgeon
// on Earth (data and advice both travel ~20 minutes, so they work on trends and risks).

export function DoctorView({ day }: { day: number }) {
  const [role, setRole] = useState<'cmo' | 'ground'>('cmo')
  const [view, setView] = useState<View | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.missionDoctor(role).then((v) => { setView(v); setError(null) }).catch((e) => setError(String(e)))
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

      <section className="panel">
        <h2>Risks in the next 48 hours</h2>
        {view.risks.length === 0 ? <p className="muted">Nobody above the usual level.</p> : (
          <table className="doc-table">
            <thead><tr><th>Who</th><th>What</th><th>vs usual</th><th>Signs</th><th>Suggested action</th></tr></thead>
            <tbody>
              {view.risks.map((r) => (
                <tr key={`${r.astronaut_id}-${r.event}`} className={`risk-${r.level}`}>
                  <td>{r.name}</td>
                  <td>{r.label}</td>
                  <td>×{r.multiple} <small className="muted">({Math.round(r.risk * 100)}%)</small></td>
                  <td className="small">{r.signs.join('; ') || '—'}</td>
                  <td className="small">{r.action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="muted small">
          Model trained on simulated missions; it has not been validated on real astronauts. Placeholder advice, not medical guidance.
        </p>
      </section>

      <section className="panel">
        <h2>Anomalies today</h2>
        {view.anomalies.length === 0 ? <p className="muted">All values as usual for each person.</p> : (
          <table className="doc-table">
            <thead><tr><th>Who</th><th>Indicator</th><th>Value</th><th>Usual</th><th>Status</th><th>Why</th></tr></thead>
            <tbody>
              {view.anomalies.map((a) => (
                <tr key={`${a.astronaut_id}-${a.type}`} className={`status-${a.status}`}>
                  <td>{a.name}</td>
                  <td>{a.label}</td>
                  <td>{a.value} <small className="muted">{a.unit}</small></td>
                  <td>{a.norm ?? '—'}</td>
                  <td><span className="dot" /> {a.status}</td>
                  <td className="small">{a.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {view.symptoms.length > 0 && (
        <section className="panel">
          <h2>Reported symptoms</h2>
          {view.symptoms.map((s) => (
            <p key={s.astronaut_id}><strong>{s.name}</strong>: {s.symptoms.join(', ')}</p>
          ))}
        </section>
      )}
    </div>
  )
}
