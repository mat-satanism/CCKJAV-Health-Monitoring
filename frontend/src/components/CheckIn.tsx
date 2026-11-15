import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api'
import type { Meta } from '../types'

// Indicators asked in the daily check-in; each field shows how to measure it (data/content/indicators.json).
const FIELDS = ['heart_rate', 'bp_sys', 'bp_dia', 'glucose', 'temp', 'sleep_hours', 'exercise_min', 'hrv_ms', 'reaction_ms']
const MOODS = ['😞', '🙁', '😐', '🙂', '😄']

/** `focus`: the indicator to re-measure (from "Re-measure now"); its field gets the cursor and a highlight. */
export function CheckIn({ meta, onSaved, focus }: { meta: Meta; onSaved: () => void; focus?: string | null }) {
  const form = useRef<HTMLFormElement>(null)
  useEffect(() => {
    if (!focus) return
    const el = form.current?.querySelector<HTMLElement>(focus === 'mood' ? '.moods button' : `#ci-${focus}`)
    el?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    el?.focus({ preventScroll: true })
  }, [focus])
  const [values, setValues] = useState<Record<string, string>>({})
  const [mood, setMood] = useState<number | null>(null)
  const [why, setWhy] = useState('')
  const [state, setState] = useState<'idle' | 'saving' | 'saved' | 'error' | 'empty'>('idle')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const ts = new Date().toISOString()
    const items = Object.entries(values)
      .filter(([, v]) => v.trim() !== '')
      .map(([type, v]) => ({ ts, type, value: Number(v), unit: meta.indicators[type].unit, source: 'manual' as const }))
    if (mood) items.push({ ts, type: 'mood', value: mood, unit: '1-5', source: 'manual' })
    if (!items.length) { setState('empty'); return }
    setState('saving')
    try {
      await api.addMeasurements(items)
      setValues({}); setMood(null); setState('saved'); onSaved()
    } catch (err) {
      setWhy(err instanceof ApiError
        ? (err.detail ?? 'A value is outside the possible range, please check it.')
        : 'Is the backend running?')
      setState('error')
    }
  }

  return (
    <form className="panel checkin" onSubmit={submit} ref={form}>
      <h2>Daily check-in</h2>
      <p className="small muted">Everything typed here is saved as a self-report. Blood pressure, glucose and
        temperature are optional: measure them at check-ups or when something feels wrong.</p>
      <div className="grid">
        {FIELDS.map((f) => (
          <label key={f} className={focus === f ? 'focus' : ''}>
            <span>{meta.indicators[f].label} <small>{meta.indicators[f].unit}</small>
              <span className="source source-manual">self-report</span></span>
            <input id={`ci-${f}`} type="number" step="any" inputMode="decimal" value={values[f] ?? ''}
              aria-describedby={`how-${f}`}
              onChange={(e) => setValues({ ...values, [f]: e.target.value })} />
            <small id={`how-${f}`} className="how">{meta.content.indicators[f]?.how_to_measure}</small>
          </label>
        ))}
      </div>
      <div className={focus === 'mood' ? 'moods focus' : 'moods'} role="radiogroup" aria-label="Mood (self-report)">
        {MOODS.map((m, i) => (
          <button type="button" key={m} role="radio" aria-checked={mood === i + 1}
            className={mood === i + 1 ? 'on' : ''} onClick={() => setMood(i + 1)}>{m}</button>
        ))}
      </div>
      <button className="primary" disabled={state === 'saving'}>Save</button>
      {state === 'saved' && <span className="muted"> Saved</span>}
      {state === 'error' && <span className="err"> Could not save. {why}</span>}
      {state === 'empty' && <span className="err"> Enter at least one value or pick a mood</span>}
    </form>
  )
}
