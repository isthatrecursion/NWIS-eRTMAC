export type PageId =
  | 'overview'
  | 'brief'
  | 'offsets'
  | 'compare'
  | 'evidence'
  | 'documents'
  | 'review'
  | 'ask'
  | 'validation'
  | 'rig'
  | 'settings'

export type DataMode = 'MOCK' | 'SYNTHETIC' | 'API'
export type EvidenceState = 'LESSON' | 'ELEVATED' | 'WARNING'
export type Freshness = 'FRESH' | 'STALE' | 'MISSING' | 'SUSPECT'

export interface Formation {
  id: string
  name: string
  top: number
  base: number
  uncertainty: number
}

export interface OffsetWell {
  id: string
  name: string
  surfaceDistance: number
  targetDistance: number
  formation: string
  relevance: 'HIGH' | 'MEDIUM' | 'LOW' | 'EXCLUDED'
  decision: 'INCLUDED' | 'PENALIZED' | 'EXCLUDED'
  support: string[]
  penalties: string[]
  unknowns: string[]
  x: number
  y: number
  event: string
  coverage: 'VERIFIED' | 'UNKNOWN'
}

export interface EvidenceItem {
  id: string
  role: 'SUPPORT' | 'COUNTER' | 'UNKNOWN'
  well: string
  formation: string
  historicalDepth: string
  projectedInterval: string
  summary: string
  source: string
}

export interface DocumentItem {
  id: string
  well: string
  title: string
  type: string
  pages: number
  scan: boolean
  confidence: number
  status: 'VERIFIED' | 'AUTO_ACCEPTED' | 'NEEDS_REVIEW' | 'QUARANTINED'
  coverage: string
}

export interface ReviewItem {
  id: string
  priority: 'HIGH' | 'MEDIUM' | 'LOW'
  document: string
  field: string
  extracted: string
  excerpt: string
  reason: string
}

