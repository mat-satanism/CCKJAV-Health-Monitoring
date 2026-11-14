import type { Insights, Meta, Task } from '../types'

const LEVEL = {
  self: { label: 'All good to self-manage', cls: 'status-green' },
  crew: { label: 'Tell your crew', cls: 'status-yellow' },
  ground: { label: 'Notify flight surgeon', cls: 'status-red' },
}

export function InsightsCard({ insights, meta }: { insights: Insights; meta: Meta }) {
  const l = LEVEL[insights.level]
  return (
    <section className={`panel insights ${l.cls}`}>
      <h2><span className="dot" /> {l.label}</h2>
      {insights.comm_note && <p className="muted">{insights.comm_note}</p>}
      <ul>
        {insights.items.map((i) => (
          <li key={i.type}><strong>{meta.indicators[i.type]?.label ?? i.type}</strong>: {i.message}{i.actions[0] ? `. ${i.actions[0]}` : ''}</li>
        ))}
      </ul>
    </section>
  )
}

export function TasksCard({ tasks, onDone }: { tasks: Task[]; onDone: (id: string) => void }) {
  const points = tasks.filter((t) => t.done).reduce((s, t) => s + t.points, 0)
  const total = tasks.reduce((s, t) => s + t.points, 0)
  return (
    <section className="panel tasks">
      <h2>Today <small className="muted">{points}/{total} pts</small></h2>
      <div className="progress"><div style={{ width: `${total ? (100 * points) / total : 0}%` }} /></div>
      {tasks.map((t) => (
        <label key={t.id} className={t.done ? 'done' : ''}>
          <input type="checkbox" checked={t.done} disabled={t.done} onChange={() => onDone(t.id)} />
          {t.title} <small className="muted">+{t.points}</small>
        </label>
      ))}
      {/* TODO: streaks and badges */}
    </section>
  )
}
