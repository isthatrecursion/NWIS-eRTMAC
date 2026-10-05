import type { DocumentItem, EvidenceItem, Formation, OffsetWell, ReviewItem } from './types'

export const formations: Formation[] = [
  { id: 'NAMSANG', name: 'Namsang', top: 1980, base: 2210, uncertainty: 8 },
  { id: 'TIPAM', name: 'Tipam Sandstone', top: 2210, base: 2580, uncertainty: 12 },
  { id: 'BARAIL', name: 'Barail', top: 2580, base: 2860, uncertainty: 18 },
]

export const offsets: OffsetWell[] = [
  {
    id: 'SYN-NHK-01', name: 'SYN–Naharkatia 01', surfaceDistance: 0.9, targetDistance: 2.4,
    formation: 'Tipam Sandstone', relevance: 'MEDIUM', decision: 'PENALIZED',
    support: ['same formation', 'verified interval coverage'], penalties: ['2.4 km target separation', 'different mud system'],
    unknowns: ['structural domain unavailable'], x: 62, y: 29, event: 'Clean crossing', coverage: 'VERIFIED',
  },
  {
    id: 'SYN-MOR-03', name: 'SYN–Moran 03', surfaceDistance: 1.5, targetDistance: 0.35,
    formation: 'Tipam Sandstone', relevance: 'HIGH', decision: 'INCLUDED',
    support: ['same formation', '350 m target separation', 'same 8.5 in hole section'], penalties: ['ECD 0.04 SG lower'],
    unknowns: [], x: 72, y: 66, event: 'Partial mud loss', coverage: 'VERIFIED',
  },
  {
    id: 'SYN-BGJ-02', name: 'SYN–Borholla 02', surfaceDistance: 2.1, targetDistance: 0.8,
    formation: 'Tipam Sandstone', relevance: 'HIGH', decision: 'INCLUDED',
    support: ['same formation', 'compatible hole section', 'verified loss record'], penalties: ['older drilling programme'],
    unknowns: ['pressure context unavailable'], x: 28, y: 73, event: 'Severe mud loss', coverage: 'VERIFIED',
  },
  {
    id: 'SYN-DIK-04', name: 'SYN–Dikom 04', surfaceDistance: 2.8, targetDistance: 1.9,
    formation: 'Tipam Sandstone', relevance: 'LOW', decision: 'PENALIZED',
    support: ['same formation'], penalties: ['different hole section', 'low alignment confidence'],
    unknowns: ['interval report incomplete'], x: 21, y: 31, event: 'Unknown', coverage: 'UNKNOWN',
  },
  {
    id: 'SYN-LKW-07', name: 'SYN–Lakwa 07', surfaceDistance: 3.6, targetDistance: 2.7,
    formation: 'Barail', relevance: 'EXCLUDED', decision: 'EXCLUDED',
    support: [], penalties: ['formation mismatch', 'outside active look-ahead'],
    unknowns: [], x: 88, y: 22, event: 'Stuck pipe', coverage: 'VERIFIED',
  },
]

export const evidence: EvidenceItem[] = [
  {
    id: 'EV-1042', role: 'SUPPORT', well: 'SYN–Moran 03', formation: 'Tipam Sandstone',
    historicalDepth: '2,468 m MD', projectedInterval: '2,548–2,576 m MD',
    summary: 'Partial returns while drilling. A 20 m³ LCM pill restored stable returns.', source: 'DDR · 14 Mar 2024 · p. 18',
  },
  {
    id: 'EV-0931', role: 'SUPPORT', well: 'SYN–Borholla 02', formation: 'Tipam Sandstone',
    historicalDepth: '2,392 m MD', projectedInterval: '2,542–2,582 m MD',
    summary: 'Severe loss recorded after ECD increased to 1.23 SG.', source: 'WCR · Section 7.3 · p. 46',
  },
  {
    id: 'EV-0815', role: 'COUNTER', well: 'SYN–Naharkatia 01', formation: 'Tipam Sandstone',
    historicalDepth: '2,410–2,510 m MD', projectedInterval: '2,535–2,590 m MD',
    summary: 'Verified daily coverage across the interval with no recorded circulation loss.', source: 'DDR series · 08–11 Feb 2023',
  },
  {
    id: 'EV-UNK-12', role: 'UNKNOWN', well: 'SYN–Dikom 04', formation: 'Tipam Sandstone',
    historicalDepth: 'Not established', projectedInterval: '2,550–2,600 m MD',
    summary: 'The report set does not verify coverage across the comparable interval.', source: 'Coverage ledger · incomplete',
  },
]

export const documents: DocumentItem[] = [
  { id: 'DOC-2403', well: 'SYN–Moran 03', title: 'Daily drilling report — 14 March', type: 'DDR', pages: 22, scan: true, confidence: 0.88, status: 'NEEDS_REVIEW', coverage: '2,420–2,487 m MD' },
  { id: 'DOC-2311', well: 'SYN–Naharkatia 01', title: 'Well completion report', type: 'WCR', pages: 148, scan: false, confidence: 0.98, status: 'VERIFIED', coverage: '0–3,120 m MD' },
  { id: 'DOC-2207', well: 'SYN–Borholla 02', title: 'Well completion report', type: 'WCR', pages: 136, scan: true, confidence: 0.92, status: 'AUTO_ACCEPTED', coverage: '0–2,940 m MD' },
  { id: 'DOC-2410', well: 'SYN–Dikom 04', title: 'Daily drilling report set', type: 'DDR', pages: 38, scan: true, confidence: 0.61, status: 'QUARANTINED', coverage: 'Unknown' },
]

export const reviewItems: ReviewItem[] = [
  { id: 'REV-011', priority: 'HIGH', document: 'DOC-2403 · p. 18', field: 'event.depth_md_m', extracted: '2,468 m', excerpt: 'At 2468 m, observed partial returns while drilling ahead…', reason: 'Affects active look-ahead within 121 m' },
  { id: 'REV-014', priority: 'HIGH', document: 'DOC-2403 · p. 18', field: 'mitigation.quantity', extracted: '20 m³', excerpt: 'Pumped 20 m3 medium-grade LCM pill. Returns improved.', reason: 'Numeric value from OCR requires confirmation' },
  { id: 'REV-028', priority: 'MEDIUM', document: 'DOC-2410 · p. 7', field: 'formation.alias', extracted: 'TPM Sst.', excerpt: 'Entered TPM Sst. at reported depth…', reason: 'Formation alias is not yet verified' },
]

export const metrics = [
  { label: 'Alert precision', value: '0.78', note: '7 of 9 warnings overlap hidden events' },
  { label: 'Severe-event recall', value: '0.83', note: '5 of 6 severe events identified' },
  { label: 'Median lead distance', value: '74 m', note: 'Measured from interval entry' },
  { label: 'Alerts per 1,000 m', value: '2.4', note: 'Held-out replay set' },
]

export const navGroups = [
  { label: 'Start', items: [{ id: 'overview', label: 'Overview' }] },
  { label: 'Operations', items: [
    { id: 'brief', label: 'Next interval brief' }, { id: 'offsets', label: 'Offset wells' },
    { id: 'compare', label: 'Formation compare' }, { id: 'evidence', label: 'Evidence' }, { id: 'rig', label: 'Rig view' },
  ] },
  { label: 'Knowledge', items: [
    { id: 'documents', label: 'Documents' }, { id: 'review', label: 'Review queue' }, { id: 'ask', label: 'Ask NWIS' },
  ] },
  { label: 'System', items: [{ id: 'validation', label: 'Validation' }, { id: 'settings', label: 'Settings' }] },
] as const

