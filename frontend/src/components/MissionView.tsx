import { useEffect, useState } from 'react'
import { api } from '../api'
import { useCountUp } from '../anim'
import type { AstronautState, CrewAlert, MissionTask } from '../types'

// The simulated crew mission for one day: who is fit, what is coming, and who does which task.
// All data is synthetic (calibrated on real people), and the page says so.

const LAMP_LABEL: Record<string, string> = {
  heart_rate: 'Pulse', bp_sys: 'Sys', bp_dia: 'Dia', glucose: 'Gluc',
  temp: 'Temp', sleep_hours: 'Sleep', mood: 'Mood', exercise_min: 'Exer', hrv_ms: 'HRV', reaction_ms: 'React',
}

export function AlertList({ alerts }: { alerts: CrewAlert[] }) {
  if (!alerts.length) return null
  return (
    <div className="alerts" role="status">
      {alerts.map((a, n) => (
        <p key={`${a.kind}-${n}`} className={`alert status-${a.level}`}><span className="dot" />{a.message}</p>
      ))}
    </div>
  )
}

function initials(name: string) { return name.slice(0, 2).toUpperCase() }

function CrewCard({ a, onOpen, i }: { a: AstronautState; onOpen: (aid: string) => void; i: number }) {
  const top = a.risks.find((r) => r.level !== 'normal')
  const off = a.indicators.filter((x) => x.status === 'yellow' || x.status === 'red')
  return (
    <article className={`crew-card status-${a.status}`} style={{ '--i': i } as React.CSSProperties}>
      <button className="crew-top linkish" onClick={() => onOpen(a.astronaut_id)} title={`Open ${a.name}'s card`}>
        <span className="avatar" aria-hidden="true"><span>{initials(a.name)}</span></span>
        <span className="who"><strong>{a.name}</strong><small>{a.role}</small></span>
        <span className="dot" aria-label={`status ${a.status}`} />
      </button>
      <div className="lamps" aria-label="Indicators">
        {a.indicators.map((x) => (
          <span key={x.type} className={`lamp status-${x.status}`}
            title={`${x.label}: ${x.value} ${x.unit}. ${x.message}`}>{LAMP_LABEL[x.type] ?? x.label}</span>
        ))}
      </div>
      <div className="crew-note">
        {top
          ? <p className={`risk risk-${top.level}`}><b className="num">{top.multiple}×</b> {top.label.toLowerCase()} risk, next 48 h</p>
          : <p className="muted">{off.length ? off.map((x) => `${x.label}: ${x.message.toLowerCase()}`).join('; ') : 'As usual for this person'}</p>}
        {(a.symptoms.length > 0 || a.isolated || a.contact_of.length > 0) && (
          <p className="chips">
            {a.isolated && <span className="chip chip-strong">isolated</span>}
            {a.contact_of.length > 0 && <span className="chip chip-watch">contact of {a.contact_of.join(', ')}</span>}
            {a.symptoms.map((s) => <span key={s} className="chip">{s}</span>)}
          </p>
        )}
      </div>
      <span className={`fit ${a.fit_for_high_demand ? 'ok' : 'no'}`}>
        {a.fit_for_high_demand ? '✓ Fit for EVA' : '✕ Not fit for EVA'}
      </span>
    </article>
  )
}

function Tile({ label, value, of, unit, note, tone, i }: {
  label: string; value: number; of?: number; unit?: string; note: string; tone: string; i: number; }) {
  const v = useCountUp(value)
  const shown = Number.isInteger(value) ? Math.round(v) : v.toFixed(1)
  return (
    <div className={`tile status-${tone}`} style={{ '--i': i } as React.CSSProperties}>
      <span className="tile-label">{label}</span>
      <span className="tile-value num">{shown}{unit && <small>{unit}</small>}{of != null && <small>/{of}</small>}</span>
      <span className="tile-note">{note}</span>
    </div>
  )
}

function Overview({ crew, tasks }: { crew: AstronautState[]; tasks: MissionTask[] }) {
  const ok = crew.filter((a) => a.status === 'green').length
  const fit = crew.filter((a) => a.fit_for_high_demand).length
  const risks = crew.flatMap((a) => a.risks.filter((r) => r.level !== 'normal').map((r) => ({ ...r, name: a.name })))
  const top = risks.sort((x, y) => y.multiple - x.multiple)[0]
  const moved = tasks.filter((t) => t.status !== 'planned').length
  const worst = crew.some((a) => a.status === 'red') ? 'red' : crew.some((a) => a.status === 'yellow') ? 'yellow' : 'green'
  return (
    <section className="overview" aria-label="Mission overview">
      <Tile i={0} label="Crew nominal" value={ok} of={crew.length} tone={worst}
        note={ok === crew.length ? 'everyone as usual' : `${crew.length - ok} need a look`} />
      <Tile i={1} label="Highest 48 h risk" value={top ? top.multiple : 1} unit="×" tone={top ? (top.level === 'high' ? 'red' : 'yellow') : 'green'}
        note={top ? `${top.name}: ${top.label.toLowerCase()}, vs usual` : 'no raised risks'} />
      <Tile i={2} label="Fit for EVA" value={fit} of={crew.length} tone={fit === crew.length ? 'green' : 'yellow'}
        note={fit === crew.length ? 'all can go outside' : 'some stay inside'} />
      <Tile i={3} label="Tasks today" value={tasks.length} tone={moved ? 'yellow' : 'green'}
        note={moved ? `${moved} moved or postponed` : 'all as planned'} />
    </section>
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
      <Overview crew={crew} tasks={tasks} />
      <AlertList alerts={alerts} />
      <section className="crew-grid" aria-label="Crew">
        {crew.map((a, i) => <CrewCard key={a.astronaut_id} a={a} onOpen={onOpen} i={i} />)}
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
                    {t.partner_name && <small className="muted"> with {t.partner_name}</small>}
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
