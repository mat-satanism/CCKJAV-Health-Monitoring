import type { ReactElement } from 'react'
import type { BodySystemStatus, Status, SystemId } from '../types'

// An astronaut figure with one clickable zone per body system. Decorative parts (helmet ring, orbit
// rings, scan line, heartbeat) ignore the pointer; only the zones are buttons. Keep the `system` ids.
const ARM = 'M62 84 C50 85 44 93 43 104 L36 176 C35 186 40 192 46 192 C52 192 55 187 56 179 L64 112 Z'
const LEG = 'M75 204 C83 208 91 209 98 207 L96 302 C96 312 91 316 85 316 C79 316 75 312 75 303 L73 214 Z'
const mirror = (d: string) => <path d={d} transform="translate(200 0) scale(-1 1)" />

const ZONES: { system: SystemId; label: string; shapes: ReactElement[] }[] = [
  { system: 'behavioral', label: 'Mind & mood', shapes: [<circle key="head" cx="100" cy="40" r="23" />] },
  {
    system: 'sleep', label: 'Sleep',
    shapes: [  // a bed beside the helmet: headboard, pillow, sleeper under a blanket, mattress, foot
      <rect key="bed-head" x="146" y="12" width="5" height="30" rx="2" />,
      <rect key="bed-pillow" x="153" y="21" width="11" height="7" rx="3.5" />,
      <path key="bed-blanket" d="M166 28 C166 21 172 19 177 21 L186 24 C189 25 190 27 190 29 L190 30 L166 30 Z" />,
      <rect key="bed-mattress" x="146" y="31" width="46" height="7" rx="2.5" />,
      <rect key="bed-foot" x="187" y="27" width="5" height="15" rx="2" />,
    ],
  },
  { system: 'immune', label: 'Immune system', shapes: [<path key="neck" d="M89 64 L111 64 L113 78 L87 78 Z" />] },
  {
    system: 'cardiovascular', label: 'Heart & vessels',
    shapes: [<path key="chest" d="M70 80 C80 78 120 78 130 80 C137 82 139 88 138 96 L133 146 C112 151 88 151 67 146 L62 96 C61 88 63 82 70 80 Z" />],
  },
  {
    system: 'metabolic', label: 'Metabolism',
    shapes: [<path key="belly" d="M68 151 C89 156 111 156 132 151 L128 194 C110 201 90 201 72 194 Z" />],
  },
  {
    system: 'musculoskeletal', label: 'Bones & muscles',
    shapes: [
      <path key="arm-l" d={ARM} />, <g key="arm-r">{mirror(ARM)}</g>,
      <path key="leg-l" d={LEG} />, <g key="leg-r">{mirror(LEG)}</g>,
    ],
  },
]

interface Props {
  systems: BodySystemStatus[]
  selected: SystemId | null
  onSelect: (s: SystemId) => void
}

const WORD: Record<Status, string> = { green: 'as usual', yellow: 'watch', red: 'act now', grey: 'no data' }

export function BodyMap({ systems, selected, onSelect }: Props) {
  const statusOf = (id: SystemId): Status => systems.find((s) => s.system === id)?.status ?? 'grey'
  const current = ZONES.find((z) => z.system === selected)
  return (
    <figure className="body-wrap">
      <svg viewBox="0 0 200 330" className="body-map" role="group" aria-label="Body systems">
        <g className="body-deco" aria-hidden="true">
          <ellipse cx="100" cy="320" rx="70" ry="7" className="body-floor" />
          <circle cx="100" cy="170" r="98" className="body-ring" />
          <circle cx="100" cy="170" r="86" className="body-ring ring-dash" />
          <circle cx="100" cy="40" r="30" className="helmet" />
          <path d="M80 34 A21 21 0 0 1 118 30" className="visor" />
        </g>
        {ZONES.map((z) => (
          <g
            key={z.system}
            className={`zone status-${statusOf(z.system)} ${selected === z.system ? 'selected' : ''}`}
            onClick={() => onSelect(z.system)}
            onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelect(z.system)}
            tabIndex={0}
            role="button"
            aria-pressed={selected === z.system}
            aria-label={`${z.label}: ${WORD[statusOf(z.system)]}`}
          >
            <title>{`${z.label}: ${WORD[statusOf(z.system)]}`}</title>
            {z.shapes}
          </g>
        ))}
        <g className="body-deco" aria-hidden="true">
          <path d="M80 112 h10 l4 -8 l6 16 l4 -8 h16" className="heartbeat" />
        </g>
      </svg>
      {current && (
        <figcaption className={`body-caption status-${statusOf(current.system)}`}>
          <span className="dot" />{current.label}<small>{WORD[statusOf(current.system)]}</small>
        </figcaption>
      )}
      {!current && <figcaption className="body-caption muted">Tap a body part</figcaption>}
      {current && (
        <p className="body-hint">Tap another body part to switch</p>
      )}
    </figure>
  )
}
