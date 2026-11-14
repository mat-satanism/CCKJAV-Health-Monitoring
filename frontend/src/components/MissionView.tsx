import { useEffect, useState } from 'react'
import { api } from '../api'
import type { AstronautState, CrewAlert, MissionTask } from '../types'

// The simulated crew mission: who is fit today, what the risks are, and who does which task.
// All data is synthetic (calibrated on real people), and the page says so.

const STATUS_TEXT = {
  planned: 'planned', reassigned: 'reassigned', postponed: 'postponed', 'needs decision': 'needs decision',
} as const

export function AlertList({ alerts }: { alerts: CrewAlert[] }) {
  if (!alerts.length) return null
  return (
    <div className="alerts">
      {alerts.map((a) => (
        <p key={a.kind} className={`alert status-${a.level}`}><span className="dot" />{a.message}</p>
      ))}
    </div>
  )
}

function CrewCard({ a }: { a: AstronautState }) {
  const top = a.risks.find((r) => r.level !== 'normal')
  const off = a.indicators.filter((i) => i.status !== 'green' && i.status !== 'grey')
  return (
    <article className={`crew-card status-${a.status}`}>
      <header>
        <span className="dot" />
        <strong>{a.name}</strong>
        <small className="muted">{a.role}</small>
      </header>
      {top && (
        <p className={`risk risk-${top.level}`}>
          {top.label} risk ×{top.multiple} usual, next 48 h
        </p>
      )}
      {off.map((i) => (
        <p key={i.type} className="muted small">{i.label}: {i.value} {i.unit}, {i.message.toLowerCase()}</p>
      ))}
      {a.symptoms.length > 0 && <p className="chips">{a.symptoms.map((s) => <span key={s} className="chip">{s}</span>)}</p>}
      {!a.fit_for_high_demand && <p className="small unfit">Not fit for EVA or heavy work</p>}
    </article>
  )
}

export function MissionView({ day }: { day: number }) {
  const [crew, setCrew] = useState<AstronautState[] | null>(null)
  const [tasks, setTasks] = useState<MissionTask[]>([])
  const [alerts, setAlerts] = useState<CrewAlert[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.missionCrew(), api.missionTasks(), api.missionAlerts()])
      .then(([c, t, a]) => { setCrew(c); setTasks(t); setAlerts(a); setError(null) })
      .catch((e) => setError(String(e)))
  }, [day])

  if (error) return <p className="err">{error}</p>
  if (!crew) return <p className="muted">Loading…</p>

  return (
    <div className="mission">
      <AlertList alerts={alerts} />
      <section className="crew-grid">
        {crew.map((a) => <CrewCard key={a.astronaut_id} a={a} />)}
      </section>
      <section className="panel">
        <h2>Tasks for day {day}</h2>
        <table className="task-table">
          <thead><tr><th>Task</th><th>Who</th><th>Status</th><th>Why</th></tr></thead>
          <tbody>
            {tasks.map((t) => (
              <tr key={t.task_id} className={`task-${t.status.replace(' ', '-')}`}>
                <td>{t.title}{t.demand === 'high' && <small className="muted"> · high demand</small>}</td>
                <td>
                  {t.reassigned_to_name
                    ? <><s className="muted">{t.assignee_name}</s> → <strong>{t.reassigned_to_name}</strong></>
                    : t.assignee_name}
                </td>
                <td><span className="pill">{STATUS_TEXT[t.status]}</span></td>
                <td className="small">{t.reason ?? t.warning ?? ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
