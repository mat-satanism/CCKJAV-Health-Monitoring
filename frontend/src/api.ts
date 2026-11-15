import type {
  Alarm, AstronautCard, Brief, PatientFile, AstronautHistory, AstronautState, BloodRow, CrewAlert, DoctorView, Insights, Measurement, Meta, MissionContext, MissionInfo,
  Forecast, MissionTask, NowLine, Readiness, Report, StatusResponse, Task, TimelineDay, Wellbeing,
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
  forecast: (type: string) => req<Forecast>(`/forecast/${type}`),
  addMeasurements: (items: Measurement[]) =>
    req<Measurement[]>('/measurements', { method: 'POST', body: JSON.stringify(items) }),
  tasks: () => req<Task[]>('/tasks'),
  completeTask: (id: string) => req<Task>(`/tasks/${id}/complete`, { method: 'POST' }),
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
  enterForAstronaut: (aid: string, day: number, values: Record<string, number>, symptoms?: string[]) =>
    req<AstronautCard>(`/mission/astronaut/${aid}/entries?day=${day}`, { method: 'POST', body: JSON.stringify({ values, symptoms }) }),
  setReadiness: (aid: string, day: number, ready: boolean, note = '') =>
    req<Readiness>(`/mission/astronaut/${aid}/readiness?day=${day}`, { method: 'POST', body: JSON.stringify({ ready, note }) }),
  patientFile: (aid: string, day: number) => req<PatientFile>(`/mission/astronaut/${aid}/file?day=${day}`),
  missionBrief: (day: number) => req<Brief>(`/mission/brief?day=${day}`),
  missionNow: (day: number) => req<NowLine[]>(`/mission/now?day=${day}`),
  missionAlarms: (day: number) => req<Alarm[]>(`/mission/alarms?day=${day}`),
  missionReport: (day: number, period: 'day' | 'week') => req<Report>(`/mission/report?day=${day}&period=${period}`),
  missionDoctor: (role: 'cmo' | 'ground') => req<DoctorView>(`/mission/doctor?role=${role}`),
}
