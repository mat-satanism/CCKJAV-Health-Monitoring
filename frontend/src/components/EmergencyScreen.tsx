import { useEffect, useRef, useState } from 'react'
import type { Insights, Meta } from '../types'

// The "call the ground" screen: only for a red confirmed by a second reading (level "ground").
// Big text, one question at a time, and how long a message takes to reach Earth.
// The steps are a placeholder workflow written by us, not a clinical protocol.

const STEPS = [
  { q: 'Have you told the crew medical officer?',
    no: 'Tell them now: they are on board and can act long before Earth replies.' },
  { q: 'Has the person stopped heavy and outside tasks?',
    no: 'Ask the commander to move today\'s heavy tasks to someone else.' },
  { q: 'Has the message to the flight surgeon gone out?',
    no: 'Send it now with today\'s values: the report on the Doctors tab has them.' },
]

function minutes(s: number): string {
  return s >= 60 ? `${Math.round(s / 60)} min` : `${s} s`
}

export function EmergencyScreen({ insights, meta, delayS, onClose }: {
  insights: Insights; meta: Meta; delayS: number; onClose: () => void
}) {
  const [answers, setAnswers] = useState<(boolean | null)[]>(STEPS.map(() => null))
  const head = useRef<HTMLHeadingElement>(null)
  useEffect(() => { head.current?.focus() }, [])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const confirmed = insights.items.filter((i) => i.status === 'red' && !i.recheck)
  const step = answers.findIndex((a) => a === null)
  const answer = (k: number, v: boolean) => setAnswers(answers.map((a, j) => (j === k ? v : a)))

  return (
    <div className="emergency" role="alertdialog" aria-modal="true" aria-labelledby="em-title" aria-describedby="em-what">
      <div className="emergency-box">
        <h2 id="em-title" tabIndex={-1} ref={head}>Call the flight surgeon</h2>
        <div id="em-what" className="em-what">
          {confirmed.map((i) => (
            <p key={i.type}><strong>{meta.indicators[i.type]?.label ?? i.type}</strong>: {i.message}</p>
          ))}
        </div>

        <p className="em-delay">
          A message reaches Earth in <strong>{minutes(delayS)}</strong>. The earliest reply is
          in <strong>{minutes(delayS * 2)}</strong>. Until then the crew acts on board.
        </p>

        <ol className="em-steps">
          {STEPS.map((s, k) => (
            <li key={s.q} className={k === step ? 'now' : answers[k] === null ? 'later' : 'done'}>
              <p className="em-q">{s.q}</p>
              {answers[k] === null && k <= Math.max(step, 0) ? (
                <div className="em-yn">
                  <button type="button" onClick={() => answer(k, true)}>Yes</button>
                  <button type="button" onClick={() => answer(k, false)}>No</button>
                </div>
              ) : answers[k] !== null && (
                <p className={answers[k] ? 'em-ok' : 'em-no'}>
                  {answers[k] ? 'Done.' : s.no}
                  {' '}<button type="button" className="linkish" onClick={() => answer(k, !answers[k])}>
                    Change to {answers[k] ? 'no' : 'yes'}
                  </button>
                </p>
              )}
            </li>
          ))}
        </ol>

        <p className="small muted">Placeholder steps written by the team, not a clinical protocol.</p>
        <button type="button" className="primary" onClick={onClose}>Back to the dashboard</button>
      </div>
    </div>
  )
}
