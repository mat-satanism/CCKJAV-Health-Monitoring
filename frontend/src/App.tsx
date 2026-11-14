import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { BloodReference } from './components/BloodReference'
import { BodyMap } from './components/BodyMap'
import { CheckIn } from './components/CheckIn'
import { DoctorView } from './components/DoctorView'
import { MissionView } from './components/MissionView'
import { InsightsCard, TasksCard } from './components/Sidebar'
import { SystemPanel } from './components/SystemPanel'
import type {
  EnvironmentId, Insights, Meta, MissionContext, MissionInfo, StatusResponse, SystemId, Task,
} from './types'

type Tab = 'mission' | 'doctor' | 'astronaut'
const TABS: { id: Tab; label: string }[] = [
  { id: 'mission', label: 'Crew mission' },
  { id: 'doctor', label: 'Doctors' },
  { id: 'astronaut', label: 'My check-in' },
]

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [insights, setInsights] = useState<Insights | null>(null)
  const [tasks, setTasks] = useState<Task[]>([])
  const [ctx, setCtx] = useState<MissionContext | null>(null)
  const [mission, setMission] = useState<MissionInfo | null>(null)
  const [missionError, setMissionError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('mission')
  const [selected, setSelected] = useState<SystemId | null>('cardiovascular')
  const [error, setError] = useState<string | null>(null)
  const [version, setVersion] = useState(0)

  const refresh = useCallback(async () => {
    try {
      const [m, s, i, t, c] = await Promise.all([
        api.meta(), api.status(), api.insights(), api.tasks(), api.context(),
      ])
      setMeta(m); setStatus(s); setInsights(i); setTasks(t); setCtx(c); setError(null)
      setVersion((v) => v + 1)
    } catch (e) {
      setError(`Backend not reachable. Start it with: uvicorn app.main:app --reload (${String(e)})`)
      return
    }
    api.mission().then((m) => { setMission(m); setMissionError(null) }).catch((e) => setMissionError(String(e)))
  }, [])

  useEffect(() => { refresh() }, [refresh])

  if (error) return <main className="center"><p className="err">{error}</p></main>
  if (!meta || !status || !insights || !ctx) return <main className="center muted">Loading…</main>

  const changeEnv = async (environment: EnvironmentId) => {
    setCtx(await api.setContext({ ...ctx, environment }))
    refresh()
  }
  const changeDay = async (day: number) => {
    if (!mission) return
    const next = Math.min(mission.days_total, Math.max(1, day))
    await api.setMissionDay(next)
    setMission({ ...mission, day: next })
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>Crew Health Navigator</h1>
        <nav className="tabs" role="tablist">
          {TABS.map((t) => (
            <button key={t.id} role="tab" aria-selected={tab === t.id} className={tab === t.id ? 'on' : ''}
              onClick={() => setTab(t.id)}>{t.label}</button>
          ))}
        </nav>
        <select value={ctx.environment} onChange={(e) => changeEnv(e.target.value as EnvironmentId)}>
          {Object.entries(meta.environments).map(([id, env]) => (
            <option key={id} value={id}>{env.label}</option>
          ))}
        </select>
        <span className="muted">
          {ctx.gravity_g ?? 0} g · comms delay {ctx.comm_delay_s && ctx.comm_delay_s >= 60
            ? `${Math.round(ctx.comm_delay_s / 60)} min` : `${ctx.comm_delay_s ?? 0} s`}
        </span>
        <button onClick={() => api.resetDemo().then(refresh)}>Reset demo</button>
      </header>

      {tab !== 'astronaut' && (
        missionError || !mission ? <p className="err">{missionError ?? 'Loading mission…'}</p> : (
          <>
            <div className="clock panel">
              <button onClick={() => changeDay(mission.day - 1)} disabled={mission.day <= 1} aria-label="Previous day">◀</button>
              <strong>Mission day {mission.day} / {mission.days_total}</strong>
              <button onClick={() => changeDay(mission.day + 1)} disabled={mission.day >= mission.days_total} aria-label="Next day">▶</button>
              <input type="range" min={1} max={mission.days_total} value={mission.day}
                onChange={(e) => changeDay(Number(e.target.value))} aria-label="Mission day" />
              <span className="badge-synthetic">{mission.note}</span>
            </div>
            {tab === 'mission' ? <MissionView day={mission.day} /> : <DoctorView day={mission.day} />}
          </>
        )
      )}

      {tab === 'astronaut' && (
        <main className="layout">
          <section className="panel map">
            <BodyMap systems={status.systems} selected={selected} onSelect={setSelected} />
            <p className="legend">
              <span className="status-green"><span className="dot" />ok</span>
              <span className="status-yellow"><span className="dot" />watch</span>
              <span className="status-red"><span className="dot" />act</span>
              <span className="status-grey"><span className="dot" />no data</span>
            </p>
          </section>

          <div className="detail">
            <p className="muted demo-note">
              Demo: heart rate, sleep, mood and exercise are 30 real days of one PMData participant
              (device or self-report). This person never measured blood pressure, glucose or temperature,
              so those are synthetic: a typical level from NHANES with simulated day-to-day changes,
              marked "synthetic".
            </p>
            {selected && (
              <SystemPanel key={`${selected}-${version}`} system={selected} meta={meta} indicators={status.indicators} />
            )}
            {selected === 'metabolic' && <BloodReference />}
          </div>

          <aside className="side">
            <InsightsCard insights={insights} />
            <TasksCard tasks={tasks} onDone={(id) => api.completeTask(id).then(refresh)} />
            <CheckIn meta={meta} onSaved={refresh} />
          </aside>
        </main>
      )}
      <footer className="muted">Demo thresholds and simulated crew data. Not medical advice.</footer>
    </div>
  )
}
