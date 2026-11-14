import type { ReactElement } from 'react'
import type { BodySystemStatus, Status, SystemId } from '../types'

// Each body system is drawn as one or more SVG shapes on a simple figure.
// Swap these shapes for a nicer illustration later; keep the `system` ids.
const ZONES: { system: SystemId; label: string; shapes: ReactElement[] }[] = [
  {
    system: 'behavioral', label: 'Mind & mood',
    shapes: [<circle key="head" cx="100" cy="42" r="26" />],
  },
  {
    system: 'sleep', label: 'Sleep',
    shapes: [<path key="moon" d="M150 18 a14 14 0 1 0 12 22 a11 11 0 1 1 -12 -22z" />],
  },
  {
    system: 'immune', label: 'Immune system',
    shapes: [<rect key="neck" x="88" y="68" width="24" height="14" rx="5" />],
  },
  {
    system: 'cardiovascular', label: 'Heart & vessels',
    shapes: [<rect key="chest" x="66" y="84" width="68" height="62" rx="16" />],
  },
  {
    system: 'metabolic', label: 'Metabolism',
    shapes: [<rect key="abdomen" x="70" y="150" width="60" height="48" rx="14" />],
  },
  {
    system: 'musculoskeletal', label: 'Bones & muscles',
    shapes: [
      <rect key="arm-l" x="38" y="88" width="22" height="100" rx="11" />,
      <rect key="arm-r" x="140" y="88" width="22" height="100" rx="11" />,
      <rect key="leg-l" x="72" y="202" width="25" height="112" rx="12" />,
      <rect key="leg-r" x="103" y="202" width="25" height="112" rx="12" />,
    ],
  },
]

interface Props {
  systems: BodySystemStatus[]
  selected: SystemId | null
  onSelect: (s: SystemId) => void
}

export function BodyMap({ systems, selected, onSelect }: Props) {
  const statusOf = (id: SystemId): Status => systems.find((s) => s.system === id)?.status ?? 'grey'
  return (
    <svg viewBox="0 0 200 330" className="body-map" role="group" aria-label="Body systems">
      {ZONES.map((z) => (
        <g
          key={z.system}
          className={`zone status-${statusOf(z.system)} ${selected === z.system ? 'selected' : ''}`}
          onClick={() => onSelect(z.system)}
          onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelect(z.system)}
          tabIndex={0}
          role="button"
          aria-label={`${z.label}: ${statusOf(z.system)}`}
        >
          <title>{z.label}</title>
          {z.shapes}
        </g>
      ))}
    </svg>
  )
}
