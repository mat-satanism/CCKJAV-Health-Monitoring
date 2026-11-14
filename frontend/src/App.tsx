import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { BloodReference } from './components/BloodReference'
import { BodyMap } from './components/BodyMap'
import { CheckIn } from './components/CheckIn'
import { DoctorView } from './components/DoctorView'
import { MissionStrip } from './components/MissionStrip'
import { MissionView } from './components/MissionView'
import { PatientFile } from './components/PatientFile'
import { PersonView } from './components/PersonView'
import { InsightsCard, TasksCard } from './components/Sidebar'
import { SystemPanel } from './components/SystemPanel'
import type {
  Insights, Meta, MissionContext, MissionInfo, StatusResponse, SystemId, Task,
} from './types'

type Tab = 'mission' | 'doctor' | 'astronaut'
const TABS: { id: Tab; label: string }[] = [
  { id: 'mission', label: 'Crew mission' },
  { id: 'doctor', label: 'Doctors' },
  { id: 'astronaut', label: 'Check-in' },
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
  const [fileOpen, setFileOpen] = useState(false)
  const [chosen, setPatient] = useState<string | null>(null)   // a crew member id, or 'real' for the real-data demo
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

  const changeDay = async (day: number) => {
    if (!mission) return
    const next = Math.min(mission.days_total, Math.max(1, day))
    await api.setMissionDay(next)
    setMission({ ...mission, day: next })
  }
  const patient = chosen ?? mission?.crew[0]?.astronaut_id ?? 'real'
  const openPerson = (aid: string) => { setPatient(aid); setFileOpen(false); setTab('astronaut') }
  const strip = mission && (
    <MissionStrip day={mission.day} total={mission.days_total} note={mission.note} onDay={changeDay} reloadKey={version} />
  )

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
        <div className="context">
          {/* One mission, one crew: the environment is fixed (switching it kept the same crew, which made no sense). */}
          <span className="env">{meta.environments[ctx.environment]?.label ?? ctx.environment}</span>
          <span>{ctx.gravity_g ?? 0} g</span>
          <span>
            {ctx.comm_delay_s && ctx.comm_delay_s >= 60
              ? `${Math.round(ctx.comm_delay_s / 60)} min` : `${ctx.comm_delay_s ?? 0} s`} signal delay
          </span>
          <button onClick={() => api.resetDemo().then(refresh)}>Reset demo</button>
        </div>
      </header>

      {tab !== 'astronaut' && (
        missionError || !mission ? <p className="err">{missionError ?? 'Loading mission…'}</p> : (
          <>
            {strip}
            {tab === 'mission' ? <MissionView day={mission.day} onOpen={openPerson} /> : <DoctorView day={mission.day} mission={mission} meta={meta} />}
          </>
        )
      )}

      {tab === 'astronaut' && (
        <nav className="patients" aria-label="Choose who to check in">
          {mission?.crew.map((c) => (
            <button key={c.astronaut_id} className={patient === c.astronaut_id ? 'on' : ''}
              aria-pressed={patient === c.astronaut_id} onClick={() => { setPatient(c.astronaut_id); setFileOpen(false) }}>
              {c.name}<small>{c.role}</small>
            </button>
          ))}
          <button className={patient === 'real' ? 'on' : ''} aria-pressed={patient === 'real'}
            onClick={() => setPatient('real')}>Real-data demo<small>PMData person</small></button>
        </nav>
      )}

      {tab === 'astronaut' && patient !== 'real' && mission && (
        <>
          {strip}
          {fileOpen
            ? <PatientFile aid={patient} day={mission.day} meta={meta} onBack={() => setFileOpen(false)} />
            : <PersonView aid={patient} day={mission.day} meta={meta} onDay={changeDay}
                onChanged={() => setVersion((v) => v + 1)} onOpenFile={() => setFileOpen(true)} />}
        </>
      )}

      {tab === 'astronaut' && patient === 'real' && (
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
            <InsightsCard insights={insights} meta={meta} />
            <TasksCard tasks={tasks} onDone={(id) => api.completeTask(id).then(refresh)} />
            <CheckIn meta={meta} onSaved={refresh} />
          </aside>
        </main>
      )}
      <footer className="muted">Demo thresholds and simulated crew data. Not medical advice.</footer>
    </div>
  )
}
