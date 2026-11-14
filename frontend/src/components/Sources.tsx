import type { Source } from '../types'

export function SourceLinks({ ids, sources }: { ids: string[]; sources: Record<string, Source> }) {
  return (
    <p className="sources small">
      Sources:{' '}
      {ids.map((id, n) => {
        const s = sources[id]
        return s ? (
          <span key={id}>{n > 0 && '; '}<a href={s.url} target="_blank" rel="noreferrer">{s.title}</a>{s.year ? ` (${s.year})` : ''}</span>
        ) : null
      })}
    </p>
  )
}
