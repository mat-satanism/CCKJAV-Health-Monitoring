import { useEffect, useState } from 'react'
import {
  Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from '../api'
import type { AstronautCard, AstronautHistory, HistoryPoint, Meta, Status, SystemId } from '../types'
import { BodyMap } from './BodyMap'
import { MeasurementPlan } from './MeasurementPlan'
import { SourceLinks } from './Sources'

// One crew member of the simulated mission: body map for the chosen day, history of every indicator with
// the personal norm band, check-in for that day, readiness, medical history. All data is synthetic.

const FIELDS = ['heart_rate', 'bp_sys', 'bp_dia', 'glucose', 'temp', 'sleep_hours', 'exercise_min', 'hrv_ms', 'reaction_ms']
const MOODS = ['😞', '🙁', '😐', '🙂', '😄']
const SYMPTOMS = ['fever', 'headache', 'fatigue', 'trouble sleeping', 'dizziness when standing']
const DOT: Record<Status, string> = {
  green: 'var(--green)', yellow: 'var(--yellow)', red: 'var(--red)', grey: 'var(--grey)',
}

interface Props {
  aid: string; day: number; meta: Meta; onDay: (day: number) => void; onChanged: () => void; onOpenFile: () => void
}

function HistoryChart({ points, day, onDay }: { points: HistoryPoint[]; day: number; onDay: (d: number) => void }) {
  const data = points.map((p) => ({ ...p, band: p.low != null && p.high != null ? [p.low, p.high] : null }))
  return (
    <ResponsiveContainer width="100%" height={150}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}
        onClick={(e) => { if (e?.activeLabel != null) onDay(Number(e.activeLabel)) }}>
        <CartesianGrid stroke="var(--grid)" vertical={false} />
        <XAxis dataKey="day" tick={{ fontSize: 10, fill: 'var(--muted)' }} interval={4} />
        <YAxis tick={{ fontSize: 10, fill: 'var(--muted)' }} domain={['auto', 'auto']} />
        <Tooltip contentStyle={{ background: 'var(--panel)', border: '1px solid var(--border-hi)', borderRadius: 10, fontFamily: 'var(--font-mono)', fontSize: 12 }}
          formatter={(v, name) => (Array.isArray(v) ? [`${v[0]} to ${v[1]}`, 'usual range'] : [v, name])}
          labelFormatter={(d) => `Day ${d}`} />
        <Area dataKey="band" stroke="none" fill="var(--accent)" fillOpacity={0.12} isAnimationActive={false} name="usual range" />
        <Line dataKey="norm" stroke="var(--muted)" strokeDasharray="4 4" dot={false} name="personal norm" isAnimationActive={false} />
        <Line dataKey="value" stroke="var(--accent)" strokeWidth={2} name="value" isAnimationActive={false}
          dot={(p) => {
            const pt = p.payload as HistoryPoint
            return <circle key={pt.day} cx={p.cx} cy={p.cy} r={pt.entered ? 4 : 2.5}
              fill={DOT[pt.status]} stroke={pt.entered ? 'var(--text)' : 'none'} />
          }} />
        <ReferenceLine x={day} stroke="var(--text)" strokeOpacity={0.5} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

function Readiness({ card, onDone }: { card: AstronautCard; onDone: () => void }) {
  const r = card.readiness
  const answer = (ready: boolean) => api.setReadiness(card.astronaut_id, card.day, ready).then(onDone)
  return (
    <section className={`panel readiness ${r ? (r.ready ? 'status-green' : 'status-yellow') : ''}`}>
      <h2>Ready for day {card.day}?</h2>
      {r ? <p>{r.reply}</p> : <p className="muted">A quick morning check, one tap.</p>}
      <p className={`support support-${card.support.level}`}>{card.support.message}</p>
      <div className="row-buttons">
        <button className={r?.ready ? 'primary' : ''} onClick={() => answer(true)}>I'm ready for the day</button>
        <button className={r && !r.ready ? 'primary' : ''} onClick={() => answer(false)}>Not quite</button>
      </div>
    </section>
  )
}

function CheckInFor({ card, meta, onSaved }: { card: AstronautCard; meta: Meta; onSaved: () => void }) {
  const [values, setValues] = useState<Record<string, string>>({})
  const [mood, setMood] = useState<number | null>(null)
  const [symptoms, setSymptoms] = useState<string[]>(card.symptoms)
  const [msg, setMsg] = useState('')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const out: Record<string, number> = {}
    for (const [k, v] of Object.entries(values)) if (v.trim() !== '') out[k] = Number(v)
    if (mood) out.mood = mood
    const symptomsChanged = symptoms.join() !== card.symptoms.join()
    if (!Object.keys(out).length && !symptomsChanged) { setMsg('Enter at least one value, a mood or a symptom'); return }
    try {
      await api.enterForAstronaut(card.astronaut_id, card.day, out, symptoms)
      setValues({}); setMood(null); setMsg('Saved for day ' + card.day); onSaved()
    } catch (err) {
      setMsg(String(err).includes(': 422') ? 'A value is outside the possible range, please check it.'
        : 'Could not save. Is the backend running?')
    }
  }

  return (
    <form className="panel checkin" onSubmit={submit}>
      <h2>Check-in for {card.name}, day {card.day}</h2>
      <p className="small muted">Values you enter replace the simulated ones for this day. Statuses and tasks update; the 48-hour risks stay the model's.</p>
      <div className="grid">
        {FIELDS.map((f) => {
          const now = card.indicators.find((i) => i.type === f)
          return (
            <label key={f}>
              <span>{meta.indicators[f].label} <small>{meta.indicators[f].unit}</small></span>
              <input type="number" step="any" inputMode="decimal" value={values[f] ?? ''}
                placeholder={now ? String(now.value) : ''}
                onChange={(e) => setValues({ ...values, [f]: e.target.value })} />
            </label>
          )
        })}
      </div>
      <div className="moods" role="radiogroup" aria-label="Mood">
        {MOODS.map((m, i) => (
          <button type="button" key={m} role="radio" aria-checked={mood === i + 1}
            className={mood === i + 1 ? 'on' : ''} onClick={() => setMood(i + 1)}>{m}</button>
        ))}
      </div>
      <fieldset className="symptoms">
        <legend className="small muted">Symptoms today</legend>
        {SYMPTOMS.map((s) => (
          <label key={s} className="sym">
            <input type="checkbox" checked={symptoms.includes(s)}
              onChange={(e) => setSymptoms(e.target.checked ? [...symptoms, s] : symptoms.filter((x) => x !== s))} />
            {s}
          </label>
        ))}
      </fieldset>
      <button className="primary">Save</button>
      {msg && <span className={msg.startsWith('Saved') ? 'muted' : 'err'}> {msg}</span>}
    </form>
  )
}

function MedicalHistory({ card }: { card: AstronautCard }) {
  const a = card.anamnesis
  const list = (items: string[]) => (items.length ? items.join('; ') : 'none known')
  return (
    <section className="panel history-card">
      <h2>Medical history <span className="badge-synthetic">synthetic</span></h2>
      <dl>
        <dt>Age, sex</dt><dd>{a.age}, {a.sex}</dd>
        <dt>Conditions</dt><dd>{list(a.conditions)}</dd>
        <dt>Allergies</dt><dd className={a.allergies.length ? 'warn' : ''}>{list(a.allergies)}</dd>
        <dt>Regular medicine</dt>
        <dd>{a.medications.length ? a.medications.map((m) => `${m.drug} ${m.dose}, ${m.schedule}`).join('; ') : 'none'}</dd>
        <dt>Family history</dt><dd>{list(a.family_history)}</dd>
        <dt>Genetic predispositions</dt><dd>{list(a.genetic)}</dd>
      </dl>
      <h3>Medicine on day {card.day}</h3>
      {card.medication_today.length
        ? <ul>{card.medication_today.map((m) => (
          <li key={m.drug + m.reason}>{m.drug} {m.dose} <small className="muted">({m.reason}; given by {m.given_by})</small></li>
        ))}</ul>
        : <p className="muted">None</p>}
      {a.notes && <p className="small muted">{a.notes}</p>}
    </section>
  )
}

export function PersonView({ aid, day, meta, onDay, onChanged, onOpenFile }: Props) {
  const [card, setCard] = useState<AstronautCard | null>(null)
  const [hist, setHist] = useState<AstronautHistory | null>(null)
  const [selected, setSelected] = useState<SystemId | null>('cardiovascular')
  const [version, setVersion] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.astronaut(aid, day), api.astronautHistory(aid)])
      .then(([c, h]) => { setCard(c); setHist(h); setError(null) })
      .catch((e) => setError(String(e)))
  }, [aid, day, version])

  if (error) return <p className="err">{error}</p>
  if (!card || !hist) return <p className="muted">Loading…</p>

  const reload = () => { setVersion((v) => v + 1); onChanged() }
  const mine = card.indicators.filter((i) => selected && meta.indicators[i.type]?.system === selected)
  const risks = card.risks.filter((r) => r.level !== 'normal')

  return (
    <main className="layout">
      <section className="panel map">
        <div className={`person-head status-${card.status}`}>
          <span className="avatar" aria-hidden="true"><span>{card.name.slice(0, 2).toUpperCase()}</span></span>
          <div>
            <strong>{card.name}</strong>
            <small className="muted">{card.role}</small>
            <p className={`fit ${card.fit_for_high_demand ? 'ok' : 'no'}`}>
              {card.fit_for_high_demand ? '✓ Fit for EVA' : '✕ Not fit for EVA'}
            </p>
          </div>
          <button className="file-link" onClick={onOpenFile}>Patient file →</button>
        </div>
        <BodyMap systems={card.systems} selected={selected} onSelect={setSelected} />
        {(card.symptoms.length > 0 || card.isolated || card.contact_of.length > 0) && (
          <p className="chips">
            {card.isolated && <span className="chip chip-strong">isolated</span>}
            {card.contact_of.length > 0 && <span className="chip chip-watch">contact of {card.contact_of.join(', ')}</span>}
            {card.symptoms.map((s) => <span key={s} className="chip">{s}</span>)}
          </p>
        )}
        <p className="small muted hint">Tap a body part, then a day on any chart.</p>
      </section>

      <div className="detail">
        {risks.length > 0 && (
          <section className="panel">
            <h2>Risks in the next 48 hours</h2>
            {risks.map((r) => (
              <div key={r.event} className="risk-item">
                <p className={`risk risk-${r.level}`}>{r.label}: {r.multiple}× the usual risk</p>
                {r.signs.length > 0 && <p className="small muted">Why: {r.signs.join('; ')}</p>}
              </div>
            ))}
            <p className="small muted">Model trained on simulated missions; the reasons come from SHAP.</p>
          </section>
        )}
        {card.trends.length > 0 && (
          <section className="panel">
            <h2>This week</h2>
            <ul className="trends">
              {card.trends.map((t) => (
                <li key={t.type} className={t.worse ? 'worse' : 'better'}>
                  <span aria-hidden="true">{t.per_day > 0 ? '↗' : '↘'}</span> {t.message}
                  <small className="muted"> {t.worse ? 'worth watching' : 'a good direction'}</small>
                </li>
              ))}
            </ul>
          </section>
        )}
        {selected && (
          <section className="panel">
            <h2>{meta.systems[selected].label} <small className="muted">day {card.day}</small></h2>
            {mine.map((i) => (
              <article key={i.type} className={`indicator status-${i.status}`}>
                <header>
                  <span className="dot" />
                  <strong title={meta.content.indicators[i.type]?.why}>{i.label}</strong>
                  {i.entered && <span className="source source-manual">entered</span>}
                  <span className="value">{i.value} <small>{i.unit}</small></span>
                </header>
                <p className="muted">{i.message}</p>
                {meta.content.indicators[i.type] && (
                  <details className="learn">
                    <summary>Why we track this, and which tests</summary>
                    <p>{meta.content.indicators[i.type].why}</p>
                    <p><strong>How often.</strong> {meta.content.indicators[i.type].frequency}.{' '}
                      <strong>How.</strong> {meta.content.indicators[i.type].how_to_measure}</p>
                    {meta.content.indicators[i.type].tests?.length > 0 && (
                      <>
                        <p><strong>If it stays off, tests to consider:</strong></p>
                        <ul>{meta.content.indicators[i.type].tests.map((t) => <li key={t}>{t}</li>)}</ul>
                      </>
                    )}
                    <SourceLinks ids={meta.content.indicators[i.type].sources} sources={meta.content.sources} />
                  </details>
                )}
                <HistoryChart points={hist[i.type]} day={card.day} onDay={onDay} />
              </article>
            ))}
            <p className="small muted">Shaded: where 95% of this person's values should fall (Bayesian norm, learned from the last 14 days on top of what is typical for people). Big dots: values entered in the app.</p>
          </section>
        )}
      </div>

      <aside className="side">
        <Readiness card={card} onDone={reload} />
        <CheckInFor key={`${aid}-${card.day}`} card={card} meta={meta} onSaved={reload} />
        <MedicalHistory card={card} />
        <section className="panel">
          <h2>Food tips <span className="badge-synthetic">demo</span></h2>
          <ul className="small">{card.support.nutrition.map((n) => <li key={n}>{n}</li>)}</ul>
          <p className="small muted">Placeholder tips for the demo, not dietary advice.</p>
        </section>
        <MeasurementPlan meta={meta} />
      </aside>
    </main>
  )
}
