// Mirrors docs/api-contract.md. Keep in sync with backend/app/models.py.
export type Status = 'green' | 'yellow' | 'red' | 'grey'
export type SystemId =
  | 'cardiovascular' | 'musculoskeletal' | 'behavioral' | 'immune' | 'metabolic' | 'sleep'
export type EnvironmentId = 'iss' | 'transit' | 'rover' | 'moon_base' | 'mars_base'

export interface Measurement {
  id?: string
  astronaut_id?: string
  ts: string
  type: string
  value: number
  unit: string
  source?: 'manual' | 'sensor' | 'synthetic'
}

export interface IndicatorStatus {
  type: string
  latest: number | null
  status: Status
  baseline?: number | null
  deviation?: number | null
  trend?: 'up' | 'down' | 'flat' | null
  source?: 'manual' | 'sensor' | 'synthetic' | null
  message: string
  actions: string[]
}

// ---------- simulated crew mission (synthetic, docs/simulation.md) ----------
export interface CrewMember {
  astronaut_id: string; name: string; role: string; skills: string; calibrated_from: string
}
export interface MissionInfo {
  day: number; days_total: number; crew: CrewMember[]; source: 'synthetic'; note: string
}
export interface MissionIndicator {
  type: string; label: string; unit: string; value: number
  norm: number | null; z: number | null; status: Status; message: string
}
export interface EventRisk {
  event: string; label: string; risk: number; multiple: number
  level: 'high' | 'watch' | 'normal'; signs: string[]; action: string
}
export interface AstronautState {
  astronaut_id: string; name: string; role: string; skills: string[]; calibrated_from: string; day: number
  status: Status; indicators: MissionIndicator[]; symptoms: string[]; risks: EventRisk[]
  fit_for_high_demand: boolean; unfit_reasons: string[]; cautions: string[]; source: 'synthetic'
}
// ---------- one crew member's card (synthetic) ----------
export interface Medication { drug: string; dose: string; schedule?: string; reason: string; day?: number; given_by?: string }
export interface Anamnesis {
  age: number; sex: string; conditions: string[]; allergies: string[]; medications: Medication[]
  family_history: string[]; genetic: string[]; notes: string
}
export interface Readiness { ready: boolean; note: string; reply: string }
export interface AstronautCard extends AstronautState {
  indicators: (MissionIndicator & { entered: boolean })[]
  systems: BodySystemStatus[]
  anamnesis: Anamnesis
  medication_today: Medication[]
  readiness: Readiness | null
}
export interface HistoryPoint {
  day: number; value: number; status: Status; norm: number | null; low: number | null; high: number | null
  z: number | null; entered: boolean
}
export type AstronautHistory = Record<string, HistoryPoint[]>
export interface MissionTask {
  task_id: string; mission_day: number; title: string; kind: string; demand: 'high' | 'normal'; skill: string
  assignee: string; assignee_name: string
  status: 'planned' | 'reassigned' | 'postponed' | 'needs decision'
  reassigned_to: string | null; reassigned_to_name: string | null; reason: string | null; warning: string | null
}
export interface TimelineDay {
  day: number; status: Status; high_risks: number; alerts: string[]; changed_tasks: number
}
export interface NowLine {
  astronaut_id: string; name: string; role: string; level: Status; what: string; do: string; symptoms: string[]
}
export interface Alarm { day: number; who: string; level: Status; kind: 'value' | 'risk' | 'alert' | 'task'; what: string; action: string }
export interface ReportCrew {
  astronaut_id: string; name: string; role: string; status: Status; fit_for_high_demand: boolean
  days_yellow: number; days_red: number; off_today: string[]; symptoms: string[]; top_risks: string[]
  medication_given: string[]; not_ready_days: number[]
}
export interface Report {
  day: number; period: 'day' | 'week'; from_day: number; to_day: number; made: string
  crew: ReportCrew[]; alarms: Alarm[]; tasks_changed: number; source: 'synthetic'; note: string
}
export interface CrewAlert { kind: string; level: Status; who: string; message: string }
export interface DoctorView {
  role: 'cmo' | 'ground'; title: string; data_delay_min: number; reply_round_trip_min: number; guidance: string
  day: number
  anomalies: (MissionIndicator & { astronaut_id: string; name: string })[]
  risks: (EventRisk & { astronaut_id: string; name: string })[]
  symptoms: { astronaut_id: string; name: string; symptoms: string[] }[]
  alerts: CrewAlert[]
  source: 'synthetic'
}

export interface BloodRow {
  panel: 'cmp' | 'cbc'
  analyte: string
  unit: string
  timepoint: string
  days_from_flight: number
  value: number | null
  ref_min: number | null
  ref_max: number | null
  flag: 'low' | 'normal' | 'high' | null
  quality_note: string | null
}

export interface BodySystemStatus {
  system: SystemId
  status: Status
  indicators: string[]
}

export interface StatusResponse {
  indicators: IndicatorStatus[]
  systems: BodySystemStatus[]
}

export interface Insights {
  level: 'self' | 'crew' | 'ground'
  items: { type: string; status: Status; message: string; actions: string[] }[]
  comm_note: string | null
}

export interface Task { id: string; title: string; points: number; done: boolean }

export interface MissionContext {
  environment: EnvironmentId
  mission_day: number
  gravity_g?: number | null
  comm_delay_s?: number | null
}

export interface Source { title: string; publisher: string; year: number | null; url: string }
export interface IndicatorContent { why: string; how_to_measure: string; advice: string[]; sources: string[]; frequency: string }
export interface PlanItem { what: string; how: string; how_often: string; why: string; sources: string[] }
export interface SystemContent { what: string; in_space: string; hazards: string[]; sources: string[] }

export interface Meta {
  indicators: Record<string, { label: string; unit: string; system: SystemId }>
  systems: Record<SystemId, { label: string }>
  environments: Record<EnvironmentId, { label: string; gravity_g: number; comm_delay_s: number }>
  content: {
    indicators: Record<string, IndicatorContent>
    systems: Record<SystemId, SystemContent>
    sources: Record<string, Source>
    measurement_plan: { items: PlanItem[] }
  }
}
