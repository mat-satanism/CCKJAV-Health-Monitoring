import { useState, type ReactNode } from 'react'

export interface TabItem { id: string; label: string; badge?: ReactNode; content: ReactNode }

/** One panel, several cards behind small tabs: keeps a long side column to one screen. */
export function Tabbed({ tabs, label }: { tabs: TabItem[]; label: string }) {
  const [on, setOn] = useState(tabs[0]?.id)
  const current = tabs.find((t) => t.id === on) ?? tabs[0]
  return (
    <section className="panel tabbed" aria-label={label}>
      <div className="tabbed-head" role="tablist">
        {tabs.map((t) => (
          <button key={t.id} role="tab" aria-selected={t.id === current.id} className={t.id === current.id ? 'on' : ''}
            onClick={() => setOn(t.id)}>
            {t.label}{t.badge != null && <span className="tab-badge">{t.badge}</span>}
          </button>
        ))}
      </div>
      <div className="tabbed-body" role="tabpanel" key={current.id}>{current.content}</div>
    </section>
  )
}
