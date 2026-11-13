import type {
  Insights, Measurement, Meta, MissionContext, StatusResponse, Task,
} from './types'

const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) throw new Error(`${init?.method ?? 'GET'} ${path}: ${res.status}`)
  return res.json() as Promise<T>
}

export const api = {
  meta: () => req<Meta>('/meta'),
  status: () => req<StatusResponse>('/status'),
  insights: () => req<Insights>('/insights'),
  measurements: (type: string) => req<Measurement[]>(`/measurements?type=${encodeURIComponent(type)}`),
  forecast: (type: string) => req<{ type: string; values: number[] }>(`/forecast/${type}`),
  addMeasurements: (items: Measurement[]) =>
    req<Measurement[]>('/measurements', { method: 'POST', body: JSON.stringify(items) }),
  tasks: () => req<Task[]>('/tasks'),
  completeTask: (id: string) => req<Task>(`/tasks/${id}/complete`, { method: 'POST' }),
  context: () => req<MissionContext>('/context'),
  setContext: (ctx: MissionContext) =>
    req<MissionContext>('/context', { method: 'PUT', body: JSON.stringify(ctx) }),
  resetDemo: () => req<{ ok: boolean }>('/demo/reset', { method: 'POST' }),
}
