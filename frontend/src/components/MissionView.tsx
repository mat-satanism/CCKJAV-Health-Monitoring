import { useEffect, useState } from 'react'
import { api } from '../api'
import type { AstronautState, CrewAlert, MissionTask } from '../types'

// The simulated crew mission for one day: who is fit, what is coming, and who does which task.
// All data is synthetic (calibrated on real people), and the page says so.

const LAMP_LABEL: Record<string, string> = {
  heart_rate: 'Pulse', bp_sys: 'Sys', bp_dia: 'Dia', glucose: 'Gluc',
  temp: 'Temp', sleep_hours: 'Sleep', mood: 'Mood', exercise_min: 'Exer',
}

export function AlertList({ alerts }: { alerts: CrewAlert[] }) {
  if (!alerts.length) return null
  return (
    <div className="alerts" role="status">
      {alerts.map((a) => (
        <p key={a.kind} className={`alert status-${a.level}`}><span className="dot" />{a.message}</p>
      ))}
    </div>
  )
}

function CrewRow({ a, onOpen }: { a: AstronautState; onOpen: (aid: string) => void }) {
  const top = a.risks.find((r) => r.level !== 'normal')
  const off = a.indicators.filter((i) => i.status === 'yellow' || i.status === 'red')
  return (
    <div className={`crew-row status-${a.status}`}>
      <span className="dot" aria-label={`status ${a.status}`} />
      <button className="who linkish" onClick={() => onOpen(a.astronaut_id)} title={`Open ${a.name}'s card`}>
        <strong>{a.name}</strong><small>{a.role}</small>
      </button>
      <div className="lamps" aria-label="Indicators">
        {a.indicators.map((i) => (
          <span key={i.type} className={`lamp status-${i.status}`}
            title={`${i.label}: ${i.value} ${i.unit}. ${i.message}`}>{LAMP_LABEL[i.type] ?? i.label}</span>
        ))}
      </div>
      <div className="crew-note">
        {top
          ? <p className={`risk risk-${top.level}`}>{top.label} risk {top.multiple}× usual in the next 48 h</p>
          : <p className="muted">{off.length ? off.map((i) => `${i.label}: ${i.message.toLowerCase()}`).join('; ') : 'As usual for this person'}</p>}
        {a.symptoms.length > 0 && <p className="chips">{a.symptoms.map((s) => <span key={s} className="chip">{s}</span>)}</p>}
      </div>
      <span className={`fit ${a.fit_for_high_demand ? 'ok' : 'no'}`}>
        {a.fit_for_high_demand ? 'Fit for EVA' : 'Not fit for EVA'}
      </span>
    </div>
  )
}

export function MissionView({ day, onOpen }: { day: number; onOpen: (aid: string) => void }) {
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
  if (!crew) return <p className="muted">Loading the crew…</p>

  return (
    <div className="mission">
      <AlertList alerts={alerts} />
      <section className="panel roster" aria-label="Crew">
        {crew.map((a) => <CrewRow key={a.astronaut_id} a={a} onOpen={onOpen} />)}
      </section>
      <section className="panel">
        <h2>Tasks on day {day}</h2>
        <div className="table-wrap">
          <table className="task-table">
            <thead><tr><th>Task</th><th>Who</th><th>Status</th><th>Why</th></tr></thead>
            <tbody>
              {tasks.map((t) => (
                <tr key={t.task_id} className={`task-${t.status.replace(' ', '-')}`}>
                  <td>{t.title}{t.demand === 'high' && <small className="muted"> · heavy</small>}</td>
                  <td>
                    {t.reassigned_to_name
                      ? <><s className="muted">{t.assignee_name}</s> to <strong>{t.reassigned_to_name}</strong></>
                      : t.assignee_name}
                  </td>
                  <td><span className="pill">{t.status}</span></td>
                  <td className="why small">{t.reason ?? t.warning ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
