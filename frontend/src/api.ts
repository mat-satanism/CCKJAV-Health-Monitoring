import type {
  Alarm, AstronautCard, Brief, PatientFile, AstronautHistory, AstronautState, BloodRow, CrewAlert, DoctorView, Insights, Measurement, Meta, MissionContext, MissionInfo,
  Forecast, MissionTask, NowLine, Readiness, Report, StatusResponse, Task, TaskOutcome, TimelineDay, Wellbeing,
} from './types'

const BASE = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

/** An error from the API, with its own reason (`detail`) when it gave one. */
export class ApiError extends Error {
  status: number
  detail: string | null
  constructor(status: number, message: string, detail: string | null) {
    super(message); this.status = status; this.detail = detail
  }
}

/** FastAPI explains a 422 either as a text or as a list of field problems. */
function reason(body: unknown): string | null {
  const d = (body as { detail?: unknown } | null)?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((e: { loc?: unknown[]; msg?: string }) => `${(e.loc ?? []).slice(-1)[0] ?? ''}: ${e.msg ?? ''}`).join('; ')
  return null
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const detail = reason(await res.json().catch(() => null))
    throw new ApiError(res.status, `${init?.method ?? 'GET'} ${path}: ${res.status}`, detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  meta: () => req<Meta>('/meta'),
  status: () => req<StatusResponse>('/status'),
  insights: () => req<Insights>('/insights'),
  measurements: (type: string) => req<Measurement[]>(`/measurements?type=${encodeURIComponent(type)}`),
  forecast: (type: string) => req<Forecast>(`/forecast/${type}`),
  addMeasurements: (items: Measurement[]) =>
    req<Measurement[]>('/measurements', { method: 'POST', body: JSON.stringify(items) }),
  tasks: () => req<Task[]>('/tasks'),
  completeTask: (id: string) => req<Task>(`/tasks/${id}/complete`, { method: 'POST' }),
  taskFeedback: (id: string, outcome: TaskOutcome) =>
    req<Task>(`/tasks/${id}/feedback`, { method: 'POST', body: JSON.stringify({ outcome }) }),
  context: () => req<MissionContext>('/context'),
  setContext: (ctx: MissionContext) =>
    req<MissionContext>('/context', { method: 'PUT', body: JSON.stringify(ctx) }),
  resetDemo: () => req<{ ok: boolean }>('/demo/reset', { method: 'POST' }),
  wellbeing: () => req<Wellbeing>('/wellbeing'),
  bloodReference: (crew: string) => req<BloodRow[]>(`/reference/blood?crew=${encodeURIComponent(crew)}`),
  // simulated crew mission
  mission: () => req<MissionInfo>('/mission'),
  setMissionDay: (day: number) => req<{ day: number }>(`/mission/day?day=${day}`, { method: 'PUT' }),
  missionTimeline: () => req<TimelineDay[]>('/mission/timeline'),
  missionCrew: () => req<AstronautState[]>('/mission/crew'),
  missionTasks: () => req<MissionTask[]>('/mission/tasks'),
  missionAlerts: () => req<CrewAlert[]>('/mission/alerts'),
  astronaut: (aid: string, day: number) => req<AstronautCard>(`/mission/astronaut/${aid}?day=${day}`),
  astronautHistory: (aid: string) => req<AstronautHistory>(`/mission/astronaut/${aid}/history`),
  enterForAstronaut: (aid: string, day: number, values: Record<string, number>, symptoms?: string[],
    by: 'astronaut' | 'medic' = 'astronaut', reason = '') =>
    req<AstronautCard>(`/mission/astronaut/${aid}/entries?day=${day}`, { method: 'POST', body: JSON.stringify({ values, symptoms, by, reason }) }),
  logMedication: (aid: string, day: number, med: { drug: string; dose: string; reason: string; given_by: 'medic' | 'self'; note: string }) =>
    req<AstronautCard>(`/mission/astronaut/${aid}/medications?day=${day}`, { method: 'POST', body: JSON.stringify(med) }),
  addNote: (aid: string, day: number, note: { subjective: string; objective: string; assessment: string; plan: string }) =>
    req<AstronautCard>(`/mission/astronaut/${aid}/notes?day=${day}`, { method: 'POST', body: JSON.stringify(note) }),
  setReadiness: (aid: string, day: number, ready: boolean, note = '') =>
    req<Readiness>(`/mission/astronaut/${aid}/readiness?day=${day}`, { method: 'POST', body: JSON.stringify({ ready, note }) }),
  patientFile: (aid: string, day: number) => req<PatientFile>(`/mission/astronaut/${aid}/file?day=${day}`),
  missionBrief: (day: number) => req<Brief>(`/mission/brief?day=${day}`),
  missionNow: (day: number) => req<NowLine[]>(`/mission/now?day=${day}`),
  missionAlarms: (day: number) => req<Alarm[]>(`/mission/alarms?day=${day}`),
  missionReport: (day: number, period: 'day' | 'week') => req<Report>(`/mission/report?day=${day}&period=${period}`),
  missionDoctor: (role: 'cmo' | 'ground') => req<DoctorView>(`/mission/doctor?role=${role}`),
}
