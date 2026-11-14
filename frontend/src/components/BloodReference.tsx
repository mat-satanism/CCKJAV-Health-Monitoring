import { useEffect, useState } from 'react'
import { api } from '../api'
import type { BloodRow } from '../types'

// NASA Inspiration4 blood tests: 7 timepoints around one flight. Shown as reference,
// not as daily status, so it has no traffic-light colours of its own.
const CREW = ['C001', 'C002', 'C003', 'C004'] as const
const ANALYTES = ['glucose', 'potassium'] as const
const TIMEPOINTS = ['L-92', 'L-44', 'L-3', 'R+1', 'R+45', 'R+82', 'R+194'] as const

export function BloodReference() {
  const [crew, setCrew] = useState<(typeof CREW)[number]>('C001')
  const [rows, setRows] = useState<BloodRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setRows(null)
    api.bloodReference(crew).then(setRows).catch((e) => setError(String(e)))
  }, [crew])

  const cell = (analyte: string, tp: string) => rows?.find((r) => r.analyte === analyte && r.timepoint === tp)
  const unitOf = (analyte: string) => rows?.find((r) => r.analyte === analyte)?.unit.replace(/_/g, ' ')
  const refOf = (analyte: string) => {
    const r = rows?.find((x) => x.analyte === analyte)
    return r && r.ref_min != null && r.ref_max != null ? `${r.ref_min}–${r.ref_max}` : '—'
  }

  return (
    <section className="panel">
      <h2>
        Blood tests (NASA Inspiration4)
        <select value={crew} onChange={(e) => setCrew(e.target.value as (typeof CREW)[number])}
          aria-label="Crew member" style={{ marginLeft: 'auto' }}>
          {CREW.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </h2>
      <p className="muted demo-note">
        Real lab results, taken on 7 days around a 3-day flight. Not daily data.
      </p>
      {error && <p className="err">{error}</p>}
      {!rows && !error && <p className="muted">Loading…</p>}
      {rows && (
        <>
          <table className="blood-table">
            <thead>
              <tr>
                <th>Analyte</th>
                {TIMEPOINTS.map((tp) => <th key={tp}>{tp}</th>)}
                <th>Lab range</th>
              </tr>
            </thead>
            <tbody>
              {ANALYTES.map((a) => (
                <tr key={a}>
                  <th scope="row">{a} <small className="muted">{unitOf(a)}</small></th>
                  {TIMEPOINTS.map((tp) => {
                    const r = cell(a, tp)
                    const cls = [r?.flag === 'high' ? 'high' : r?.flag === 'low' ? 'low' : '',
                      r?.quality_note ? 'noted' : ''].join(' ').trim()
                    return (
                      <td key={tp} className={cls} title={r?.quality_note ?? undefined}>
                        {r?.value ?? '—'}
                      </td>
                    )
                  })}
                  <td>{refOf(a)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.some((r) => r.quality_note) ? (
            <p className="muted blood-note">
              Dotted cells: likely delayed sample processing. Hover to see the note. Kept in the data, but not used for conclusions.
            </p>
          ) : null}
        </>
      )}
    </section>
  )
}
