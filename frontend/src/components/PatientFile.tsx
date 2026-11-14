import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Meta, PatientFile as File } from '../types'
import { SourceLinks } from './Sources'

// The patient file: a fictional biography turned into an exposure history, and from it sourced risks and
// what to monitor, as NASA's Lifetime Surveillance of Astronaut Health does. Then the mission so far.

export function PatientFile({ aid, day, meta, onBack }: { aid: string; day: number; meta: Meta; onBack: () => void }) {
  const [f, setF] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.patientFile(aid, day).then((x) => { setF(x); setError(null) }).catch((e) => setError(String(e)))
  }, [aid, day])

  if (error) return <p className="err">{error}</p>
  if (!f) return <p className="muted">Loading the file…</p>
  const b = f.biography
  const a = f.anamnesis
  const s = f.mission_so_far
  const list = (xs: string[]) => (xs.length ? xs.join('; ') : 'none recorded')

  return (
    <main className="patient-file">
      <button className="back" onClick={onBack}>Back to the card</button>
      <section className="panel file-head">
        <h2>{f.name} <small className="muted">{f.role}</small> <span className="badge-synthetic">fictional person</span></h2>
        <p>{b.background}</p>
        <dl>
          <dt>Age, sex</dt><dd>{a.age}, {a.sex}</dd>
          <dt>Before the astronaut corps</dt><dd>{list(b.previous_jobs)}</dd>
          <dt>Hobbies</dt><dd>{list(b.hobbies)}</dd>
          <dt>Previous spaceflights</dt><dd>{b.flights} ({b.long_duration_flights} long-duration)</dd>
        </dl>
      </section>

      <section className="panel">
        <h2>Exposure history and what to monitor</h2>
        <p className="small muted">
          Like NASA's lifetime surveillance of astronaut health: each past exposure brings its own risks and its own checks.
          "Monitoring" comes from the sources; "our plan" is our step that follows from the risk.
        </p>
        {f.exposures.length === 0 && <p className="muted">No exposures recorded.</p>}
        {f.exposures.map((e) => (
          <article key={e.id} className="exposure">
            <h3>{e.label}</h3>
            <p>{e.risk}</p>
            {e.monitoring.length > 0 && <><p className="small"><strong>Monitoring</strong></p><ul>{e.monitoring.map((m) => <li key={m}>{m}</li>)}</ul></>}
            {e.our_plan.length > 0 && <><p className="small"><strong>Our plan</strong></p><ul className="plan">{e.our_plan.map((m) => <li key={m}>{m}</li>)}</ul></>}
            <SourceLinks ids={e.sources} sources={meta.content.sources} />
          </article>
        ))}
        <SourceLinks ids={['nasa-lsah']} sources={meta.content.sources} />
      </section>

      <div className="doc-cols">
        <section className="panel">
          <h2>Medical history</h2>
          <dl>
            <dt>Conditions</dt><dd>{list(a.conditions)}</dd>
            <dt>Allergies</dt><dd className={a.allergies.length ? 'warn' : ''}>{list(a.allergies)}</dd>
            <dt>Regular medicine</dt><dd>{a.medications.length ? a.medications.map((m) => `${m.drug} ${m.dose}, ${m.schedule}`).join('; ') : 'none'}</dd>
            <dt>Family history</dt><dd>{list(a.family_history)}</dd>
            <dt>Genetic predispositions</dt><dd>{list(a.genetic)}</dd>
          </dl>
        </section>
        <section className="panel">
          <h2>This mission, days 1-{f.day}</h2>
          <dl>
            <dt>Days off usual</dt><dd>{s.days_red} red, {s.days_yellow} yellow</dd>
            <dt>Symptoms</dt><dd>{list(s.symptoms)}</dd>
            <dt>Medicine given</dt><dd>{s.medication_given.length ? s.medication_given.map((m) => `day ${m.day}: ${m.drug} ${m.dose}`).join('; ') : 'none'}</dd>
            <dt>"Not quite" mornings</dt><dd>{s.not_ready_days.length ? s.not_ready_days.join(', ') : 'none'}</dd>
            <dt>This week</dt><dd>{list(s.worse_trends)}</dd>
          </dl>
        </section>
      </div>
    </main>
  )
}
