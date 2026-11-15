import { useEffect, useRef, useState } from 'react'
import type { EnvironmentId, Meta } from '../types'

const ORDER: EnvironmentId[] = ['iss', 'moon_base', 'transit', 'mars_base', 'rover']

const delay = (s: number) => (s >= 60 ? `${Math.round(s / 60)} min` : s >= 1 ? `${s} s` : 'live')

/** The mission's place. Same crew everywhere; each place has its own simulated mission (pipeline/environments.py). */
export function EnvSwitch({ meta, current, available, onPick }: {
  meta: Meta; current: EnvironmentId; available: string[]; onPick: (env: EnvironmentId) => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const away = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', away)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', away); document.removeEventListener('keydown', esc) }
  }, [open])

  const pick = async (env: EnvironmentId) => {
    setOpen(false)
    if (env === current) return
    setBusy(true)
    try { await onPick(env) } finally { setBusy(false) }
  }

  return (
    <div className="env-switch" ref={box}>
      <button className={`env env-${current} ${busy ? 'busy' : ''}`} aria-haspopup="listbox" aria-expanded={open}
        onClick={() => setOpen(!open)} title="Change where the mission happens">
        <i aria-hidden="true" />{meta.environments[current]?.label ?? current}<span className="caret" aria-hidden="true" />
      </button>
      {open && (
        <ul className="env-menu" role="listbox" aria-label="Where the mission happens">
          <li className="env-menu-head">Same crew, another place. Each place has its own simulated mission.</li>
          {ORDER.filter((e) => available.includes(e)).map((e) => {
            const m = meta.environments[e]
            return (
              <li key={e}>
                <button role="option" aria-selected={e === current} className={`env-opt env-${e} ${e === current ? 'on' : ''}`}
                  onClick={() => pick(e)}>
                  <i aria-hidden="true" />
                  <span className="env-opt-text">
                    <strong>{m.label}</strong>
                    <small className="env-stats">{m.gravity_g} g · signal {delay(m.comm_delay_s)}</small>
                    {m.note && <small className="env-note">{m.note}</small>}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
