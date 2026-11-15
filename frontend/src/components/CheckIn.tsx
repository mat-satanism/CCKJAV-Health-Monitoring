import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api'
import { COLLECTED_BY } from '../collected'
import type { Meta } from '../types'

const MOODS = ['😞', '🙁', '😐', '🙂', '😄']

/** The real-data demo's check-in. The astronaut only says how they feel; everything a device or the medic
 * provides arrives by itself. A medic can still type a reading by hand, with a reason (sensor off, check-up).
 * `focus`: the indicator to re-measure (from "Re-measure now"); its field gets the cursor and a highlight. */
export function CheckIn({ meta, onSaved, focus }: { meta: Meta; onSaved: () => void; focus?: string | null }) {
  const form = useRef<HTMLFormElement>(null)
  const byHand = Object.keys(meta.indicators).filter((k) => meta.indicators[k].collected_by !== 'self')
  const [medicOpen, setMedicOpen] = useState(false)
  const [values, setValues] = useState<Record<string, string>>({})
  const [reason, setReason] = useState('')
  const [mood, setMood] = useState<number | null>(null)
  const [why, setWhy] = useState('')
  const [state, setState] = useState<'idle' | 'saving' | 'saved' | 'error' | 'empty' | 'reason'>('idle')

  useEffect(() => {
    if (!focus) return
    if (focus !== 'mood') setMedicOpen(true)
    // wait one frame so the medic section is open before the field is focused
    requestAnimationFrame(() => {
      const el = form.current?.querySelector<HTMLElement>(focus === 'mood' ? '.moods button' : `#ci-${focus}`)
      el?.scrollIntoView({ block: 'center', behavior: 'smooth' })
      el?.focus({ preventScroll: true })
    })
  }, [focus])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const ts = new Date().toISOString()
    const typed = Object.entries(values).filter(([, v]) => v.trim() !== '')
    if (typed.length && !reason.trim()) { setState('reason'); return }
    const items = typed.map(([type, v]) => ({
      ts, type, value: Number(v), unit: meta.indicators[type].unit, source: 'manual' as const, reason: reason.trim(),
    }))
    if (mood) items.push({ ts, type: 'mood', value: mood, unit: '1-5', source: 'manual', reason: '' })
    if (!items.length) { setState('empty'); return }
    setState('saving')
    try {
      await api.addMeasurements(items)
      setValues({}); setReason(''); setMood(null); setState('saved'); onSaved()
    } catch (err) {
      setWhy(err instanceof ApiError
        ? (err.detail ?? 'A value is outside the possible range, please check it.')
        : 'Is the backend running?')
      setState('error')
    }
  }

  return (
    <form className="panel checkin" onSubmit={submit} ref={form}>
      <h2>How do you feel today?</h2>
      <div className={focus === 'mood' ? 'moods focus' : 'moods'} role="radiogroup" aria-label="Mood">
        {MOODS.map((m, i) => (
          <button type="button" key={m} role="radio" aria-checked={mood === i + 1}
            className={mood === i + 1 ? 'on' : ''} onClick={() => setMood(i + 1)}>{m}</button>
        ))}
      </div>
      <p className="small muted">That is all you need to enter. The rest arrives by itself:</p>
      <ul className="arrives small">
        {byHand.map((k) => (
          <li key={k}>{meta.indicators[k].label} <span className="muted">{COLLECTED_BY[meta.indicators[k].collected_by]}</span></li>
        ))}
      </ul>

      <details className="medic-entry" open={medicOpen} onToggle={(e) => setMedicOpen((e.target as HTMLDetailsElement).open)}>
        <summary>Medic: enter a reading by hand</summary>
        <p className="small muted">Only when a device is off or for a check-up. Saved with the reason.</p>
        <div className="grid">
          {byHand.map((f) => (
            <label key={f} className={focus === f ? 'focus' : ''}>
              <span>{meta.indicators[f].label} <small>{meta.indicators[f].unit}</small></span>
              <input id={`ci-${f}`} type="number" step="any" inputMode="decimal" value={values[f] ?? ''}
                aria-describedby={`how-${f}`}
                onChange={(e) => setValues({ ...values, [f]: e.target.value })} />
              <small id={`how-${f}`} className="how">{meta.content.indicators[f]?.how_to_measure}</small>
            </label>
          ))}
        </div>
        <label className="reason">
          <span>Why by hand</span>
          <input type="text" maxLength={200} value={reason} placeholder="e.g. wearable was charging"
            onChange={(e) => setReason(e.target.value)} />
        </label>
      </details>

      <button className="primary" disabled={state === 'saving'}>Save</button>
      {state === 'saved' && <span className="muted"> Saved</span>}
      {state === 'error' && <span className="err"> Could not save. {why}</span>}
      {state === 'empty' && <span className="err"> Pick how you feel, or enter a reading</span>}
      {state === 'reason' && <span className="err"> Say why the reading is entered by hand</span>}
    </form>
  )
}
