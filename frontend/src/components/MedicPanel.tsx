import { useState } from 'react'
import { api, ApiError } from '../api'
import { COLLECTED_BY } from '../collected'
import type { AstronautCard, Meta } from '../types'

const err = (e: unknown) => (e instanceof ApiError ? (e.detail ?? 'Please check the values.') : 'Is the backend running?')

/** What only the crew medical officer records: medicines, a SOAP note, a reading typed by hand with a reason.
 * As in NASA's Medical Data Architecture: device data arrives by itself, the medic adds the clinical record. */
export function MedicPanel({ card, meta, onSaved }: { card: AstronautCard; meta: Meta; onSaved: () => void }) {
  return (
    <section className="medic-panel">
      <p className="small muted">For the crew medical officer. Everything is saved for day {card.day}.</p>
      <MedicineForm card={card} onSaved={onSaved} />
      <NoteForm card={card} onSaved={onSaved} />
      <ReadingForm card={card} meta={meta} onSaved={onSaved} />
      <Notes card={card} />
    </section>
  )
}

function MedicineForm({ card, onSaved }: { card: AstronautCard; onSaved: () => void }) {
  const [m, setM] = useState({ drug: '', dose: '', reason: '', given_by: 'medic' as 'medic' | 'self', note: '' })
  const [msg, setMsg] = useState('')
  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.logMedication(card.astronaut_id, card.day, m)
      setM({ drug: '', dose: '', reason: '', given_by: 'medic', note: '' }); setMsg('Logged'); onSaved()
    } catch (x) { setMsg(err(x)) }
  }
  return (
    <form className="medic-form" onSubmit={save}>
      <h3>Medicine</h3>
      <div className="grid">
        <label><span>Medicine</span><input required maxLength={80} value={m.drug} onChange={(e) => setM({ ...m, drug: e.target.value })} /></label>
        <label><span>Dose</span><input required maxLength={40} value={m.dose} placeholder="e.g. 500 mg" onChange={(e) => setM({ ...m, dose: e.target.value })} /></label>
        <label><span>Why</span><input required maxLength={120} value={m.reason} onChange={(e) => setM({ ...m, reason: e.target.value })} /></label>
        <label><span>Given by</span>
          <select value={m.given_by} onChange={(e) => setM({ ...m, given_by: e.target.value as 'medic' | 'self' })}>
            <option value="medic">medic</option><option value="self">taken by themselves</option>
          </select>
        </label>
      </div>
      <label className="wide"><span>Side effects, effect</span><input maxLength={300} value={m.note} onChange={(e) => setM({ ...m, note: e.target.value })} /></label>
      <button className="primary">Log medicine</button>
      {msg && <span className={msg === 'Logged' ? 'muted' : 'err'}> {msg}</span>}
    </form>
  )
}

const SOAP = [
  { key: 'subjective', label: 'Subjective', hint: 'what the person says' },
  { key: 'objective', label: 'Objective', hint: 'what was measured or seen' },
  { key: 'assessment', label: 'Assessment', hint: 'what you think it is' },
  { key: 'plan', label: 'Plan', hint: 'what happens next' },
] as const

function NoteForm({ card, onSaved }: { card: AstronautCard; onSaved: () => void }) {
  const empty = { subjective: '', objective: '', assessment: '', plan: '' }
  const [n, setN] = useState(empty)
  const [msg, setMsg] = useState('')
  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    try { await api.addNote(card.astronaut_id, card.day, n); setN(empty); setMsg('Saved'); onSaved() } catch (x) { setMsg(err(x)) }
  }
  return (
    <form className="medic-form" onSubmit={save}>
      <h3>Note (SOAP)</h3>
      {SOAP.map((f) => (
        <label key={f.key} className="wide">
          <span>{f.label} <small className="muted">{f.hint}</small></span>
          <textarea rows={2} maxLength={1000} value={n[f.key]} onChange={(e) => setN({ ...n, [f.key]: e.target.value })} />
        </label>
      ))}
      <button className="primary">Save note</button>
      {msg && <span className={msg === 'Saved' ? 'muted' : 'err'}> {msg}</span>}
    </form>
  )
}

function ReadingForm({ card, meta, onSaved }: { card: AstronautCard; meta: Meta; onSaved: () => void }) {
  const types = Object.keys(meta.indicators).filter((k) => meta.indicators[k].collected_by !== 'self')
  const [type, setType] = useState('temp')
  const [value, setValue] = useState('')
  const [reason, setReason] = useState('')
  const [msg, setMsg] = useState('')
  const how = meta.indicators[type].collected_by
  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.enterForAstronaut(card.astronaut_id, card.day, { [type]: Number(value) }, undefined, 'medic', reason)
      setValue(''); setReason(''); setMsg('Saved'); onSaved()
    } catch (x) { setMsg(err(x)) }
  }
  return (
    <form className="medic-form" onSubmit={save}>
      <h3>Reading by hand</h3>
      <div className="grid">
        <label><span>What</span>
          <select value={type} onChange={(e) => setType(e.target.value)}>
            {types.map((k) => <option key={k} value={k}>{meta.indicators[k].label}</option>)}
          </select>
        </label>
        <label><span>Value <small>{meta.indicators[type].unit}</small></span>
          <input required type="number" step="any" inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)} />
        </label>
      </div>
      <p className="small muted">Normally {COLLECTED_BY[how]}.</p>
      {how !== 'medic' && (
        <label className="wide"><span>Why by hand</span>
          <input required maxLength={200} value={reason} placeholder="e.g. wearable was off" onChange={(e) => setReason(e.target.value)} />
        </label>
      )}
      <button className="primary">Save reading</button>
      {msg && <span className={msg === 'Saved' ? 'muted' : 'err'}> {msg}</span>}
    </form>
  )
}

function Notes({ card }: { card: AstronautCard }) {
  if (!card.notes.length) return <p className="small muted">No notes yet.</p>
  return (
    <div className="notes">
      <h3>Notes so far</h3>
      {card.notes.map((n) => (
        <article key={n.logged_at + n.day} className="note">
          <p className="small muted">Day {n.day}, {n.author}</p>
          {SOAP.filter((f) => n[f.key]).map((f) => <p key={f.key}><strong>{f.label[0]}</strong> {n[f.key]}</p>)}
        </article>
      ))}
    </div>
  )
}
