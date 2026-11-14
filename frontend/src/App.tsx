import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { BloodReference } from './components/BloodReference'
import { BodyMap } from './components/BodyMap'
import { CheckIn } from './components/CheckIn'
import { InsightsCard, TasksCard } from './components/Sidebar'
import { SystemPanel } from './components/SystemPanel'
import type { EnvironmentId, Insights, Meta, MissionContext, StatusResponse, SystemId, Task } from './types'

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [insights, setInsights] = useState<Insights | null>(null)
  const [tasks, setTasks] = useState<Task[]>([])
  const [ctx, setCtx] = useState<MissionContext | null>(null)
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
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  if (error) return <main className="center"><p className="err">{error}</p></main>
  if (!meta || !status || !insights || !ctx) return <main className="center muted">Loading…</main>

  const changeEnv = async (environment: EnvironmentId) => {
    setCtx(await api.setContext({ ...ctx, environment }))
    refresh()
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>CCKJAV Health Monitoring</h1>
        <span className="muted">Mission day {ctx.mission_day}</span>
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
            Demo: heart rate, sleep, mood and exercise are real days of one PMData participant
            (device or self-report). Blood pressure, glucose and temperature have no data for
            this person, so they stay grey.
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
      <footer className="muted">Demo thresholds. Not medical advice.</footer>
    </div>
  )
}
