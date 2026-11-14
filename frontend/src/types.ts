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

export interface Meta {
  indicators: Record<string, { label: string; unit: string; system: SystemId }>
  systems: Record<SystemId, { label: string }>
  environments: Record<EnvironmentId, { label: string; gravity_g: number; comm_delay_s: number }>
}
