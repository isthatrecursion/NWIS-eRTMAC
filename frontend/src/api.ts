import type { RuntimeFormation, RuntimeWell, RuntimeDocument, EventType, ReviewStatus } from './generated-contracts'
export const API_BASE = import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV?'http://127.0.0.1:8000':window.location.origin)

export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const versionedPath = path.startsWith('/api/') && !path.startsWith('/api/v1/') ? path.replace('/api/', '/api/v1/') : path
  const response = await fetch(`${API_BASE}${versionedPath}`, options)
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try { const error = await response.json(); message = typeof error.detail === 'string' ? error.detail : message } catch { /* Preserve HTTP status */ }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export type ApiFormation = RuntimeFormation

export interface ApiWell extends Pick<RuntimeWell, 'id' | 'name' | 'x_m' | 'y_m' | 'formations'> {
  id: string
  name: string
  x_m: number
  y_m: number
  latitude?: number
  longitude?: number
  held_out: boolean
  formations: ApiFormation[]
}

export interface ApiDocument extends Pick<RuntimeDocument, 'id' | 'title' | 'well_id' | 'pages' | 'is_scan' | 'ocr_confidence' | 'review_status' | 'event_ids'> {
  classification?: 'PUBLIC' | 'PRIVATE'
  doc_type?: string
  id: string
  title: string
  well_id: string
  pages: number
  is_scan: boolean
  synthetic: boolean
  ocr_confidence: number
  review_status: ReviewStatus
  event_ids: string[]
}

export interface ApiEvent {
  numerical_fields?: Record<string, { value: number; measurement: {unit: string; original_value: number; original_unit: string}; source: {text: string; page: number} }>
  id: string
  well_id: string
  event_type: EventType
  source_span_id?: string
  extraction_confidence?: string
  md_from_m: number | null
  md_to_m?: number | null
  severity?: string
  event_md_interval_m?: number[] | null
  formation_id: string | null
  review_status: string
  symptom: string | null
  mitigation: string | null
  outcome: string | null
  original_value: number | null
  original_unit: string | null
  source: { text: string; page: number; bbox: number[] | null }
}

export interface ApiOffset {
  well: ApiWell
  surface_distance_km: number
  target_distance_km: number | null
  reason: string | null
  geometry: { minimum_distance_m: number; samples: number } | null
}

export interface ApiProjection {
  inputs?: Record<string, unknown>
  uncertainty_components?: {datum_margin_m: number; event_depth_margin_m: number; datum_uncertainty_status: string}
  decision: string
  reason?: string
  method?: string
  strat_fraction?: number
  projected_md_interval_m: [number, number] | null
  alignment_confidence?: string
  algorithm_version?: string
}

export interface ApiReview {
  affects_active_lookahead?: boolean
  impact_reason?: string
  id: string
  kind: string
  entity_id: string
  document_id: string
  reason: string
  priority: string
  record: { source_text?: string; md_interval?: [number, number] | null; date_from?: string | null; date_to?: string | null; date_source?: {text: string}; doc_type?: string; classification?: string }
}

export interface ApiAnalog {
  context_comparisons?: {comparisons: {name: string; active_value: number | string | null; offset_value: number | string | null; status: string; factor: number}[]; derived_inputs?: Record<string, unknown>}
  well_id: string
  decision: string
  relevance: number
  support: string[]
  penalties: string[]
  unknowns: string[]
  blockers: string[]
}
export interface ApiTransfer extends ApiAnalog {
  event_id: string
  document_id: string
  source_span_id: string
  weight: number
  projection: ApiProjection | null
  factors: Record<string, number>
  source: {text: string; page: number} | null
}
export interface ApiEvidence {
  risk: string
  md_interval_m: number[]
  operation_state: string
  id: string
  computed_at: string
  state: string
  sentence: string
  support_count: number
  counter_count: number
  unknown_count: number
  excluded_count: number
  internal_statistics: { p_hat: number | null; n_eff: number; sum_weights: number }
  policy_version: string
  context_source: string
  rows: {well_id: string; role: string; weight: number; reason: string; analog: ApiAnalog; transfers: ApiTransfer[];
    clean_source?: {document_id: string; page: number; source_text: string; required_source_interval_m: number[]}}[]
}
