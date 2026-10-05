import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { documents, evidence, formations, metrics, navGroups, offsets, reviewItems } from './data'
import type { DataMode, EvidenceState, PageId } from './types'
import IntegratedPages, { IntegratedOverview } from './IntegratedPages'
import { request } from './api'
import FeatureTooltips, { pageHelp, sectionHelp } from './FeatureTooltips'
type TocItem = { id: string; label: string }
const pageMeta: Record<PageId, { title: string; description: string; crumb: string; toc: TocItem[] }> = {
  overview: {
    title: 'Nearby Wells Intelligence System',
    description: 'A source-grounded look-ahead for applying historical offset-well experience before the bit reaches a comparable interval.',
    crumb: 'Introduction',
    toc: [{ id: 'data-inventory', label: 'Loaded data' }, { id: 'purpose', label: 'Purpose' }, { id: 'model', label: 'Evidence model' }, { id: 'flow', label: 'Operational flow' }],
  },
  brief: {
    title: 'Next interval brief',
    description: 'Review the active interval, the evidence ahead of the bit, and the state of live corroboration.',
    crumb: 'Operations',
    toc: [{ id: 'current', label: 'Current context' }, { id: 'lookahead', label: 'Look-ahead' }, { id: 'population', label: 'Alert lifecycle' }, { id: 'depth-strip', label: 'Depth strip' }, { id: 'secondary', label: 'Secondary support' }, { id: 'signals', label: 'Channel freshness' }],
  },
  offsets: {
    title: 'Offset wells',
    description: 'Filter nearby wells at surface, then compare their geometry and relevance at the target formation.',
    crumb: 'Operations',
    toc: [{ id: 'map', label: 'Map' }, { id: 'ranking', label: 'Candidate ranking' }, { id: 'method', label: 'Selection method' }],
  },
  compare: {
    title: 'Formation compare',
    description: 'Align well histories by formation position instead of treating equal measured depths as equivalent.',
    crumb: 'Operations',
    toc: [{ id: 'alignment', label: 'Alignment' }, { id: 'tracks', label: 'Well tracks' }, { id: 'uncertainty', label: 'Uncertainty' }],
  },
  evidence: {
    title: 'Evidence explorer',
    description: 'Inspect supporting, counter, and unknown evidence behind the active look-ahead state.',
    crumb: 'Operations',
    toc: [{ id: 'summary', label: 'Summary' }, { id: 'records', label: 'Evidence records' }, { id: 'provenance', label: 'Provenance chain' }],
  },
  documents: {
    title: 'Historical documents',
    description: 'Inspect source reports, coverage intervals, extraction confidence, and review state.',
    crumb: 'Knowledge',
    toc: [{ id: 'library', label: 'Document library' }, { id: 'preview', label: 'Source preview' }, { id: 'coverage', label: 'Coverage rules' }],
  },
  review: {
    title: 'Review queue',
    description: 'Resolve uncertain extractions that can affect the active look-ahead.',
    crumb: 'Knowledge',
    toc: [{ id: 'queue', label: 'Queue' }, { id: 'review-detail', label: 'Review detail' }, { id: 'policy', label: 'Review policy' }],
  },
  ask: {
    title: 'Ask NWIS',
    description: 'Query structured well data and source evidence without delegating risk logic to the language model.',
    crumb: 'Knowledge',
    toc: [{ id: 'question', label: 'Question' }, { id: 'plan', label: 'Query plan' }, { id: 'gaps', label: 'Uncertainty' }, { id: 'sources', label: 'Sources' }],
  },
  validation: {
    title: 'Validation',
    description: 'Compare held-out replay results with simple baselines and inspect known failure cases.',
    crumb: 'System',
    toc: [{ id: 'blind', label: 'Blind benchmark' }, { id: 'gold', label: 'Extraction reference' }, { id: 'assurance', label: 'Engineering & safety' }, { id: 'validation-results', label: 'Earlier held-out replay' }],
  },
  rig: {
    title: 'Rig view',
    description: 'A reduced interface for the current interval, one active advisory, and its supporting evidence.',
    crumb: 'Operations',
    toc: [{ id: 'rig-current', label: 'Current interval' }, { id: 'advisory', label: 'Advisory' }, { id: 'acknowledge', label: 'Acknowledge' }],
  },
  settings: {
    title: 'Settings',
    description: 'Configure prototype data sources, display units, and evidence policies.',
    crumb: 'System',
    toc: [{ id: 'environment', label: 'Environment' }, { id: 'units', label: 'Units' }, { id: 'policies', label: 'Policies' }],
  },
}
const pageOrder = Object.keys(pageMeta) as PageId[]
function App() {
  const [page, setPage] = useState<PageId>(() => pageFromHash())
  const [searchOpen, setSearchOpen] = useState(false)
  const [mobileNav, setMobileNav] = useState(false)
  const [mode, setMode] = useState<DataMode>('SYNTHETIC')
  const [storedDataMode, setStoredDataMode] = useState<string>('')
  const [depth, setDepth] = useState(2435)
  const [playing, setPlaying] = useState(false)
  const [staleFlow, setStaleFlow] = useState(false)
  const [acknowledged, setAcknowledged] = useState(false)
  useEffect(() => {
    const onHash = () => setPage(pageFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setSearchOpen(true)
      }
      if (event.key === 'Escape') {
        setSearchOpen(false)
        setMobileNav(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  useEffect(() => {
    if (!playing) return
    const timer = window.setInterval(() => setDepth((value) => Math.min(2585, value + 4)), 700)
    return () => window.clearInterval(timer)
  }, [playing])
  useEffect(() => {
    if (depth >= 2585) setPlaying(false)
  }, [depth])
  useEffect(() => {
    if (mode === 'MOCK') return
    let current = true
    request<{data_mode:string}>('/api/meta').then(value=>{if(current)setStoredDataMode(value.data_mode)}).catch(()=>{if(current)setStoredDataMode('')})
    return ()=>{current=false}
  }, [page, mode])
  const evidenceState: EvidenceState = depth >= 2550 && !staleFlow ? 'WARNING' : depth >= 2480 ? 'ELEVATED' : 'LESSON'
  const navigate = (id: PageId) => {
    window.location.hash = id
    setPage(id)
    setMobileNav(false)
    window.scrollTo({ top: 0, behavior: 'auto' })
  }
  const replay = { depth, playing, staleFlow, acknowledged, evidenceState, setDepth, setPlaying, setStaleFlow, setAcknowledged }
  return (
    <div className="app-shell">
      <TopBar onSearch={() => setSearchOpen(true)} onMenu={() => setMobileNav((value) => !value)} mode={mode} storedDataMode={storedDataMode} />
      <Sidebar page={page} navigate={navigate} open={mobileNav} mode={mode} storedDataMode={storedDataMode} />
      <main id="main-content" className="main-area">
        <PageRenderer page={page} navigate={navigate} mode={mode} setMode={setMode} replay={replay} />
      </main>
      <FeatureTooltips page={page} />
      {searchOpen && <SearchDialog close={() => setSearchOpen(false)} navigate={navigate} />}
    </div>
  )
}
function pageFromHash(): PageId {
  const value = window.location.hash.replace('#', '').split('?')[0] as PageId
  return value in pageMeta ? value : 'brief'
}
function TopBar({ onSearch, onMenu, mode, storedDataMode }: { onSearch: () => void; onMenu: () => void; mode: DataMode; storedDataMode: string }) {
  return (
    <header className="topbar">
      <button className="menu-button" onClick={onMenu} aria-label="Toggle navigation">Menu</button>
      <a className="wordmark" href="#overview" aria-label="NWIS home">
        <span className="wordmark-mark">N</span><span>NWIS</span>
      </a>
      <button className="search-trigger" onClick={onSearch} aria-label="Search NWIS">
        <span>Search the system</span><kbd>⌘K</kbd>
      </button>
      <nav className="top-links" aria-label="Utility navigation">
        <a href="#validation" data-feature-help={pageHelp.validation}>Validation</a>
        <a href="#settings">Settings</a>
        <span className="mode-label">{mode === 'MOCK' ? 'MOCK' : storedDataMode || 'DATA UNKNOWN'}</span>
      </nav>
    </header>
  )
}
function Sidebar({ page, navigate, open, mode, storedDataMode }: { page: PageId; navigate: (id: PageId) => void; open: boolean; mode: DataMode; storedDataMode: string }) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})
  return (
    <aside className={`sidebar ${open ? 'sidebar-open' : ''}`} aria-label="Primary navigation">
      <div className="sidebar-notice">
        <span className="status-tag">PHASE 10</span>
        <p>{mode==='MOCK'?'Browser-local mock data.':storedDataMode==='SYNTHETIC'?'Synthetic demonstration data. Not OIL field data.':storedDataMode==='MIXED'||storedDataMode==='NON_SYNTHETIC_DECLARED'?'Database contains declared non-synthetic records; field origin is unverified.':'Data source classification unavailable.'}</p>
      </div>
      {navGroups.map((group) => (
        <section className="nav-group" key={group.label}>
          <button className="nav-group-label" onClick={() => setCollapsed((value) => ({ ...value, [group.label]: !value[group.label] }))} aria-expanded={!collapsed[group.label]}>
            <span>{group.label}</span><span aria-hidden="true">{collapsed[group.label] ? '+' : '−'}</span>
          </button>
          {!collapsed[group.label] && (
            <ul>
              {group.items.map((item) => (
                <li key={item.id}>
                  <button className={page === item.id ? 'nav-active' : ''} data-feature-help={pageHelp[item.id as PageId]} onClick={() => navigate(item.id as PageId)}>{item.label}</button>
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
      <div className="sidebar-footer">Build <code>0.10.0</code><br />Contract schema <code>v1</code></div>
    </aside>
  )
}
function PageRenderer({ page, navigate, mode, setMode, replay }: {
  page: PageId
  navigate: (id: PageId) => void
  mode: DataMode
  setMode: (mode: DataMode) => void
  replay: ReplayProps
}) {
  const content: Record<PageId, ReactNode> = {
    overview: <OverviewPage />,
    brief: <BriefPage replay={replay} />,
    offsets: <OffsetsPage />,
    compare: <ComparePage replay={replay} />,
    evidence: <EvidencePage state={replay.evidenceState} />,
    documents: <DocumentsPage />,
    review: <ReviewPage />,
    ask: <AskPage />,
    validation: <ValidationPage replay={replay} />,
    rig: <RigPage replay={replay} />,
    settings: <SettingsPage mode={mode} setMode={setMode} />,
  }
  const connected = mode !== 'MOCK' && ['offsets', 'compare', 'documents', 'review', 'evidence', 'brief', 'rig', 'validation', 'ask'].includes(page)
  return <PageFrame page={page} navigate={navigate}>
    {mode !== 'MOCK' && page === 'overview' && <IntegratedOverview />}
    {mode !== 'MOCK' && !connected && page !== 'overview' && page !== 'settings' && <Callout label="Workflow preview">This page still uses Phase 0.5 fixtures. Historical evidence, simulated replay, freshness and mud-loss alerts are connected. Validation shows published offline results; Ask NWIS uses a local deterministic planner and cited records.</Callout>}
    {connected ? <IntegratedPages key={page} page={page} /> : content[page]}
  </PageFrame>
}
function PageFrame({ page, navigate, children }: { page: PageId; navigate: (id: PageId) => void; children: ReactNode }) {
  const meta = pageMeta[page]
  const [activeSection, setActiveSection] = useState(meta.toc[0]?.id ?? '')
  const index = pageOrder.indexOf(page)
  useEffect(() => {
    setActiveSection(meta.toc[0]?.id ?? '')
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
      if (visible[0]) setActiveSection(visible[0].target.id)
    }, { rootMargin: '-96px 0px -65% 0px', threshold: [0, 1] })
    meta.toc.forEach((item) => {
      const node = document.getElementById(item.id)
      if (node) observer.observe(node)
    })
    return () => observer.disconnect()
  }, [page, meta])
  return (
    <div className="page-grid">
      <article className="content-column">
        <div className="breadcrumb"><a href="#overview">NWIS</a><span>/</span><span>{meta.crumb}</span></div>
        <header className="page-header">
          <h1>{meta.title}</h1>
          <p>{meta.description}</p>
        </header>
        {children}
        <nav className="page-pagination" aria-label="Page navigation">
          <div>{index > 0 && <><span>Previous</span><button onClick={() => navigate(pageOrder[index - 1])}>{pageMeta[pageOrder[index - 1]].title}</button></>}</div>
          <div className="pagination-next">{index < pageOrder.length - 1 && <><span>Next</span><button onClick={() => navigate(pageOrder[index + 1])}>{pageMeta[pageOrder[index + 1]].title}</button></>}</div>
        </nav>
      </article>
      <aside className="toc" aria-label="On this page">
        <p>On this page</p>
        <ul>{meta.toc.map((item) => <li key={item.id}><a className={activeSection === item.id ? 'toc-active' : ''} data-feature-help={sectionHelp[page]?.[item.id]} href={`#${page}`} onClick={(event) => { event.preventDefault(); document.getElementById(item.id)?.scrollIntoView({ behavior: 'auto' }) }}>{item.label}</a></li>)}</ul>
      </aside>
    </div>
  )
}
function OverviewPage() {
  return (
    <>
      <Callout label="Prototype boundary">This interface uses synthetic fixtures and uploaded records. It demonstrates contracts and product behavior, not calibrated Oil India risk prediction.</Callout>
      <Section id="purpose" title="Purpose">
        <p>NWIS indexes historical experience by the geological interval ahead of the bit. It retrieves relevant offset events, separates verified clean crossings from missing records, and keeps every conclusion linked to source evidence.</p>
        <div className="definition-grid">
          <Definition term="FACT" text="A value directly supported by a document or database record." />
          <Definition term="COMPUTED" text="A deterministic result with versioned inputs and algorithm." />
          <Definition term="INFERRED" text="A relevance or risk interpretation with explicit uncertainty." />
        </div>
      </Section>
      <Section id="model" title="Evidence model">
        <p>The evidence population is divided before aggregation. An absent report never becomes evidence for a clean crossing.</p>
        <FieldTable rows={[
          ['support', 'EvidenceRole', 'Transferable analog where the event is documented.'],
          ['counter', 'EvidenceRole', 'Transferable analog with verified coverage and no event.'],
          ['unknown', 'EvidenceRole', 'Coverage is insufficient to determine what occurred.'],
        ]} />
      </Section>
      <Section id="flow" title="Operational flow">
        <Steps items={[
          ['Structure the history', 'Extract events, mitigations, outcomes, depths, and source spans from historical records.'],
          ['Align the interval', 'Compare formation position and downhole geometry instead of raw measured depth alone.'],
          ['Assess transferability', 'Apply event-specific blockers, penalties, record quality, and missing-data rules.'],
          ['Corroborate live', 'Escalate only when the active well approaches the interval and fresh operational signals agree.'],
        ]} />
      </Section>
    </>
  )
}
type ReplayProps = {
  depth: number
  playing: boolean
  staleFlow: boolean
  acknowledged: boolean
  evidenceState: EvidenceState
  setDepth: (value: number | ((current: number) => number)) => void
  setPlaying: (value: boolean) => void
  setStaleFlow: (value: boolean) => void
  setAcknowledged: (value: boolean) => void
}
function BriefPage({ replay }: { replay: ReplayProps }) {
  const distance = Math.max(0, 2548 - replay.depth)
  return (
    <>
      <div className="toolbar">
        <button className="button-primary" onClick={() => replay.setPlaying(!replay.playing)}>{replay.playing ? 'Pause replay' : 'Start replay'}</button>
        <button className="button-secondary" onClick={() => { replay.setDepth(2435); replay.setPlaying(false); replay.setStaleFlow(false); replay.setAcknowledged(false) }}>Reset</button>
        <button className="button-text" onClick={() => replay.setStaleFlow(!replay.staleFlow)}>{replay.staleFlow ? 'Restore flow-out' : 'Make flow-out stale'}</button>
      </div>
      <Section id="current" title="Current context">
        <div className="metric-row">
          <Metric label="Bit depth" value={`${replay.depth.toLocaleString()} m`} note="Measured depth" />
          <Metric label="Formation" value="Tipam" note="Top uncertainty ±12 m" />
          <Metric label="Operation" value="Drilling" note="8.5 in hole section" />
        </div>
        <DepthProgress depth={replay.depth} />
      </Section>
      <Section id="lookahead" title="Look-ahead">
        <div className="advisory">
          <div className="advisory-heading"><StatusTag value={replay.evidenceState} accent={replay.evidenceState === 'WARNING'} /><span className="mono">RISK-ML-024</span></div>
          <h3>Historical mud-loss evidence in lower Tipam</h3>
          <p>Two transferable offsets recorded losses in the projected interval. One comparable well has a verified clean crossing.</p>
          <dl className="inline-facts">
            <div><dt>Projected interval</dt><dd>2,548–2,582 m MD</dd></div>
            <div><dt>Distance ahead</dt><dd>{distance} m</dd></div>
            <div><dt>Uncertainty</dt><dd>±18 m</dd></div>
          </dl>
        </div>
        {replay.staleFlow && <Callout label="Live corroboration incomplete">Flow-out is stale. The historical state remains visible, but the system will not escalate the advisory to Warning.</Callout>}
      </Section>
      <Section id="population" title="Evidence population">
        <div className="count-strip">
          <div><strong>2</strong><span>supporting events</span></div>
          <div><strong>1</strong><span>verified clean crossing</span></div>
          <div><strong>1</strong><span>unknown record</span></div>
        </div>
        <p className="muted">Three additional wells are excluded by formation mismatch or insufficient transferability.</p>
      </Section>
      <Section id="signals" title="Live signals">
        <DataTable headers={['Channel', 'Value', 'Freshness', 'Source']} rows={[
          ['Flow in', '950 L/min', <StatusTag value="FRESH" />, 'Replay adapter'],
          ['Flow out', replay.depth >= 2550 ? '902 L/min' : '930 L/min', <StatusTag value={replay.staleFlow ? 'STALE' : 'FRESH'} accent={replay.staleFlow} />, 'Replay adapter'],
          ['Pit volume', replay.depth >= 2550 ? '407.4 m³' : '410.0 m³', <StatusTag value="FRESH" />, 'Replay adapter'],
          ['ECD', '1.19 SG', <StatusTag value="FRESH" />, 'Computed'],
        ]} numericColumns={[1]} />
      </Section>
    </>
  )
}
function OffsetsPage() {
  const [radius, setRadius] = useState(3)
  const [selected, setSelected] = useState(offsets[1].id)
  const visible = offsets.filter((well) => well.surfaceDistance <= radius)
  return (
    <>
      <Section id="map" title="Map">
        <div className="filters">
          <label>Surface radius<select value={radius} onChange={(event) => setRadius(Number(event.target.value))}><option value={1}>1 km</option><option value={2}>2 km</option><option value={3}>3 km</option><option value={5}>5 km</option></select></label>
          <label>Target formation<select><option>Tipam Sandstone</option><option>Barail</option></select></label>
        </div>
        <div className="well-map" role="img" aria-label="Synthetic offset well map">
          <div className="map-grid-lines" />
          <div className="radius-ring" />
          <button className="well-point active-point" style={{ left: '49%', top: '49%' }} title="Active well"><span>A</span><small>Active</small></button>
          {visible.map((well, index) => <button key={well.id} className={`well-point ${selected === well.id ? 'selected-point' : ''}`} style={{ left: `${well.x}%`, top: `${well.y}%` }} onClick={() => setSelected(well.id)} title={well.name}><span>{index + 1}</span><small>{well.name.replace('SYN–', '')}</small></button>)}
          <div className="map-scale">1 km</div>
        </div>
        <p className="figure-caption">Surface positions are schematic. Geometry values are deterministic Phase 0.5 fixtures.</p>
      </Section>
      <Section id="ranking" title="Candidate ranking">
        <DataTable headers={['Well', 'Surface', 'At target', 'Formation', 'Decision']} rows={visible.map((well) => [
          <button className="table-link" onClick={() => setSelected(well.id)}>{well.name}</button>,
          `${well.surfaceDistance.toFixed(1)} km`, `${well.targetDistance.toFixed(2)} km`, well.formation, <StatusTag value={well.decision} accent={well.decision === 'EXCLUDED'} />,
        ])} numericColumns={[1, 2]} />
        {(() => { const well = offsets.find((item) => item.id === selected) ?? offsets[0]; return <div className="detail-panel"><div><span className="eyebrow">Why this offset</span><h3>{well.name}</h3></div><ReasonList label="Support" values={well.support} /><ReasonList label="Penalties" values={well.penalties} /><ReasonList label="Unknown" values={well.unknowns} /></div> })()}
      </Section>
      <Section id="method" title="Selection method">
        <Callout label="Important">The radius filter creates the candidate population. Final relevance uses formation availability and target-interval geometry.</Callout>
        <CodeBlock language="POLICY" code={'surface radius\n→ formation availability\n→ target-interval separation\n→ operational context\n→ source quality'} />
      </Section>
    </>
  )
}
function ComparePage({ replay }: { replay: ReplayProps }) {
  return (
    <>
      <Section id="alignment" title="Formation alignment">
        <p>The same event is expressed as a fractional position through the source formation, then projected into the active well with the source and target uncertainty retained.</p>
        <CodeBlock language="FORMULA" code={'fraction = (event depth − formation top) / formation thickness\nprojected depth = active top + fraction × active thickness'} />
      </Section>
      <Section id="tracks" title="Well tracks">
        <div className="track-grid">
          <WellTrack name="SYN–Moran 03" top={2218} base={2520} eventTop={2428} eventBottom={2468} current={null} />
          <WellTrack name="SYN–Active A1" top={2210} base={2580} eventTop={2548} eventBottom={2582} current={replay.depth} />
          <WellTrack name="SYN–Borholla 02" top={2160} base={2494} eventTop={2370} eventBottom={2418} current={null} />
        </div>
      </Section>
      <Section id="uncertainty" title="Uncertainty">
        <FieldTable rows={[
          ['formation_top', '±12 m', 'Reviewed synthetic top for the active well.'],
          ['formation_base', '±18 m', 'Base uncertainty dominates the projected lower interval.'],
          ['alignment', 'moderate', 'Two source wells agree on the lower-formation position.'],
        ]} />
      </Section>
    </>
  )
}
function EvidencePage({ state }: { state: EvidenceState }) {
  const [role, setRole] = useState('ALL')
  const shown = role === 'ALL' ? evidence : evidence.filter((item) => item.role === role)
  return (
    <>
      <Section id="summary" title="Summary">
        <div className="advisory compact-advisory"><div className="advisory-heading"><StatusTag value={state} accent={state === 'WARNING'} /><span className="mono">RISK-ML-024</span></div><p>Two historical losses, one verified clean crossing, and one unknown record support the current state.</p></div>
      </Section>
      <Section id="records" title="Evidence records">
        <div className="segmented" aria-label="Filter evidence">
          {['ALL', 'SUPPORT', 'COUNTER', 'UNKNOWN'].map((item) => <button key={item} className={role === item ? 'segment-active' : ''} onClick={() => setRole(item)}>{item}</button>)}
        </div>
        <div className="evidence-list">
          {shown.map((item) => <article className="evidence-record" key={item.id}>
            <div className="evidence-record-head"><StatusTag value={item.role} accent={item.role === 'SUPPORT'} /><code>{item.id}</code></div>
            <h3>{item.well}</h3><p>{item.summary}</p>
            <dl><div><dt>Historical depth</dt><dd>{item.historicalDepth}</dd></div><div><dt>Projected interval</dt><dd>{item.projectedInterval}</dd></div><div><dt>Source</dt><dd><a href="#documents">{item.source}</a></dd></div></dl>
          </article>)}
        </div>
      </Section>
      <Section id="provenance" title="Provenance chain">
        <div className="provenance-chain">
          {['Alert RISK-ML-024', 'Evidence set ES-190', 'Transfer assessment TA-044', 'Historical event EV-1042', 'Source span · p. 18'].map((item, index) => <div key={item}><span>{index + 1}</span><div><code>{index < 2 ? 'INFERRED' : index < 4 ? 'COMPUTED' : 'FACT'}</code><p>{item}</p></div></div>)}
        </div>
      </Section>
    </>
  )
}
function DocumentsPage() {
  const [selected, setSelected] = useState(documents[0])
  return (
    <>
      <Section id="library" title="Document library">
        <div className="filters"><label>Document type<select><option>All types</option><option>WCR</option><option>DDR</option></select></label><label>Review state<select><option>All states</option><option>Needs review</option><option>Verified</option></select></label></div>
        <DataTable headers={['Document', 'Well', 'Pages', 'OCR', 'Status']} rows={documents.map((doc) => [<button className="table-link" onClick={() => setSelected(doc)}>{doc.title}</button>, doc.well, String(doc.pages), `${Math.round(doc.confidence * 100)}%`, <StatusTag value={doc.status} accent={doc.status === 'QUARANTINED'} />])} numericColumns={[2, 3]} />
      </Section>
      <Section id="preview" title="Source preview">
        <div className="document-preview">
          <div className="document-meta"><code>{selected.id}</code><h3>{selected.title}</h3><p>{selected.well} · {selected.pages} pages · {selected.scan ? 'Scanned PDF' : 'Native PDF'}</p><dl><div><dt>Coverage</dt><dd>{selected.coverage}</dd></div><div><dt>OCR confidence</dt><dd>{Math.round(selected.confidence * 100)}%</dd></div></dl></div>
          <div className="paper-page"><div className="paper-header">DAILY DRILLING REPORT</div><p>Operations continued drilling the 8.5 in section in Tipam Sandstone.</p><p className="source-highlight">At 2468 m, observed partial returns while drilling ahead. Pumped 20 m³ medium-grade LCM pill. Returns improved.</p><p>Circulated bottoms-up and monitored active pit volume before resuming.</p><span>Page 18</span></div>
        </div>
      </Section>
      <Section id="coverage" title="Coverage rules"><Callout label="Coverage invariant">A missing or unreadable interval remains unknown. It cannot be counted as a clean crossing.</Callout></Section>
    </>
  )
}
function ReviewPage() {
  const [items, setItems] = useState(reviewItems)
  const [selected, setSelected] = useState(reviewItems[0])
  const resolve = (id: string) => { const remaining = items.filter((item) => item.id !== id); setItems(remaining); setSelected(remaining[0] ?? reviewItems[0]) }
  return (
    <>
      <Section id="queue" title="Queue">
        {items.length ? <DataTable headers={['Priority', 'Field', 'Extracted value', 'Reason']} rows={items.map((item) => [<StatusTag value={item.priority} accent={item.priority === 'HIGH'} />, <button className="table-link" onClick={() => setSelected(item)}>{item.field}</button>, item.extracted, item.reason])} /> : <EmptyState title="Review queue is clear" text="No unresolved extraction currently affects the active look-ahead." />}
      </Section>
      {items.length > 0 && <Section id="review-detail" title="Review detail">
        <div className="review-detail"><div><span className="eyebrow">{selected.document}</span><h3><code>{selected.field}</code></h3><blockquote>{selected.excerpt}</blockquote></div><div className="review-value"><label>Extracted value<input defaultValue={selected.extracted} /></label><p>{selected.reason}</p><div className="toolbar"><button className="button-primary" onClick={() => resolve(selected.id)}>Accept</button><button className="button-secondary" onClick={() => resolve(selected.id)}>Correct</button><button className="button-text" onClick={() => resolve(selected.id)}>Quarantine</button></div></div></div>
      </Section>}
      <Section id="policy" title="Review policy"><p>Items are prioritized by extraction uncertainty, event severity, relevance to the active well, and distance ahead of the bit. Low-impact errors remain visible but appear later in the queue.</p></Section>
    </>
  )
}
function AskPage() {
  const [question, setQuestion] = useState('What happened in comparable wells when they entered lower Tipam?')
  const [submitted, setSubmitted] = useState(true)
  const [loading, setLoading] = useState(false)
  const submit = (event: FormEvent) => {
    event.preventDefault()
    setSubmitted(false)
    setLoading(true)
    window.setTimeout(() => { setLoading(false); setSubmitted(true) }, 450)
  }
  return (
    <>
      <Section id="question" title="Question">
        <form className="ask-form" onSubmit={submit}><label htmlFor="question-input">Ask about wells, formations, events, or mitigations</label><textarea id="question-input" value={question} onChange={(event) => { setQuestion(event.target.value); setSubmitted(false) }} /><button className="button-primary">Run grounded query</button></form>
      </Section>
      <Section id="answer" title="Grounded answer">
        {loading ? <LoadingState /> : submitted ? <div className="answer-block"><h3>Facts</h3><p>Two comparable wells recorded mud losses in the lower Tipam interval. SYN–Moran 03 reported partial returns at 2,468 m MD. SYN–Borholla 02 recorded severe losses at 2,392 m MD.</p><h3>Computed pattern</h3><p>The events project to 2,542–2,582 m MD in the active well. One comparable well has verified clean coverage across the projected interval.</p><h3>Interpretation</h3><p>The historical state is Elevated. Review the recorded mitigations before entering the interval.</p><h3>Gaps</h3><p>One potentially relevant well has incomplete interval coverage. Structural-domain labels are unavailable.</p><ol className="citations"><li><a href="#documents">SYN–Moran 03 DDR, 14 March, page 18</a></li><li><a href="#documents">SYN–Borholla 02 WCR, section 7.3, page 46</a></li></ol></div> : <EmptyState title="Run the query" text="Answers use structured records first, then attach exact source evidence." />}
      </Section>
      <Section id="limits" title="Response limits"><Callout label="Grounding rule">NWIS does not use the language model to calculate transferability, projected depths, or evidence states. It formats verified tool results and refuses unsupported numerical claims.</Callout></Section>
    </>
  )
}
function ValidationPage({ replay }: { replay: ReplayProps }) {
  return (
    <>
      <Section id="scorecard" title="Held-out scorecard"><div className="metric-row">{metrics.map((metric) => <Metric key={metric.label} {...metric} />)}</div><p className="figure-caption">Illustrative synthetic replay metrics. These values do not measure Oil India field accuracy.</p></Section>
      <Section id="baseline" title="Baselines">
        <DataTable headers={['Method', 'Precision', 'Recall', 'Median lead', 'Result']} rows={[
          ['Surface-nearest wells', '0.42', '0.67', '38 m', 'Misses downhole geometry'],
          ['Same formation', '0.55', '0.75', '51 m', 'Ignores operation context'],
          ['Fixed similarity', '0.68', '0.79', '63 m', 'Better candidate order'],
          ['NWIS evidence policy', '0.78', '0.83', '74 m', 'Includes coverage and blockers'],
        ]} numericColumns={[1, 2, 3]} />
      </Section>
      <Section id="replay" title="Held-out replay"><div className="timeline"><div className="timeline-line" /><span style={{ left: '15%' }}>2,435<br /><small>Start</small></span><span style={{ left: '50%' }}>2,498<br /><small>Elevated</small></span><span className="timeline-accent" style={{ left: '73%' }}>2,550<br /><small>Warning</small></span><span style={{ left: '90%' }}>2,576<br /><small>Hidden event</small></span></div></Section>
      <Section id="failure" title="Controlled failure"><p>Set flow-out to stale during replay. The historical evidence remains visible, but the state cannot escalate to Warning.</p><button className="button-secondary" onClick={() => replay.setStaleFlow(!replay.staleFlow)}>{replay.staleFlow ? 'Restore channel' : 'Inject stale flow-out'}</button><p className="result-line">Current result: <StatusTag value={replay.staleFlow ? 'ESCALATION BLOCKED' : 'CHANNEL FRESH'} accent={replay.staleFlow} /></p></Section>
    </>
  )
}
function RigPage({ replay }: { replay: ReplayProps }) {
  return (
    <>
      <Section id="rig-current" title="Current interval"><div className="rig-strip"><div><span>BIT DEPTH</span><strong>{replay.depth.toLocaleString()} m</strong></div><div><span>FORMATION</span><strong>TIPAM</strong></div><div><span>OPERATION</span><strong>DRILLING</strong></div><div><span>DATA</span><strong>{replay.staleFlow ? 'INCOMPLETE' : 'FRESH'}</strong></div></div></Section>
      <Section id="advisory" title="Active advisory"><div className="rig-advisory"><StatusTag value={replay.evidenceState} accent={replay.evidenceState === 'WARNING'} /><h2>Mud-loss evidence ahead</h2><p>Two comparable offsets recorded losses in the projected interval at 2,548–2,582 m MD.</p><div className="rig-signal"><span>Flow return</span><strong>{replay.staleFlow ? 'Stale' : replay.depth >= 2550 ? '−48 L/min' : '−20 L/min'}</strong></div><div className="rig-signal"><span>Pit trend</span><strong>{replay.depth >= 2550 ? 'Falling' : 'Stable'}</strong></div></div></Section>
      <Section id="acknowledge" title="Acknowledge"><div className="toolbar"><button className="button-primary" disabled={replay.acknowledged} onClick={() => replay.setAcknowledged(true)}>{replay.acknowledged ? 'Acknowledged' : 'Acknowledge advisory'}</button><a className="button-secondary link-button" href="#evidence">Open evidence</a></div><p className="muted">Acknowledgement records review. It does not change operational equipment or parameters.</p></Section>
    </>
  )
}
function SettingsPage({ mode, setMode }: { mode: DataMode; setMode: (mode: DataMode) => void }) {
  const [apiStatus, setApiStatus] = useState('')
  const [meta, setMeta] = useState<{data_mode:string;well_count:number;document_count:number;record_sources:{wells:{synthetic:number;declared_non_synthetic:number};documents:{synthetic:number;declared_non_synthetic:number}}}|null>(null)
  useEffect(() => {
    if (mode === 'MOCK') { setApiStatus('Browser-local fixtures'); return }
    request<typeof meta>('/api/meta').then(data => {if(!data)return;setMeta(data);setApiStatus(`${data.well_count} wells · ${data.document_count} reports · ${data.data_mode.replaceAll('_',' ')} records`)}).catch(() => setApiStatus('Backend unavailable'))
  }, [mode])
  return (
    <>
      <Section id="environment" title="Environment"><FieldTable rows={[["build", 'string', '0.10.0 — Phases 1 through 10'], ['schema', 'string', 'Canonical contracts v1'], ['loaded data', 'API record flags', meta ? `${meta.record_sources.wells.synthetic} synthetic wells; ${meta.record_sources.documents.synthetic} synthetic reports; ${meta.record_sources.wells.declared_non_synthetic + meta.record_sources.documents.declared_non_synthetic} declared non-synthetic records` : 'Unavailable']]} /><fieldset className="radio-group"><legend>Data provider</legend>{(['MOCK', 'SYNTHETIC', 'API'] as DataMode[]).map((item) => <label key={item}><input type="radio" name="mode" checked={mode === item} onChange={() => setMode(item)} /><span><code>{item}</code><small>{item === 'MOCK' ? 'Browser-local workflow fixtures' : item === 'API' ? 'Configured backend; uses the same stored records as SYNTHETIC' : 'Stored API records, currently synthetic in the demo database'}</small></span></label>)}</fieldset><p role="status">{apiStatus}</p><p className="muted">The API option does not fetch external field data. Replay, freshness and mud-loss warnings are connected simulations, not a real rig feed. Validation shows published offline results; Ask NWIS uses a local deterministic planner and cited records.</p></Section>
      <Section id="units" title="Units"><DataTable headers={['Quantity', 'Canonical unit', 'Display unit']} rows={[["Depth", 'm', 'm'], ['Mud density', 'SG', 'SG'], ['Flow', 'L/min', 'L/min'], ['Pressure', 'kPa', 'psi'], ['Coordinates', 'Declared CRS', 'Local grid']]} /></Section>
      <Section id="policies" title="Policies"><div className="setting-row"><div><strong>Unknown coverage stays unknown</strong><p>Never convert missing documentation into a clean crossing.</p></div><StatusTag value="REQUIRED" /></div><div className="setting-row"><div><strong>Freshness gate</strong><p>Stale corroborating channels cannot strengthen an advisory.</p></div><StatusTag value="REQUIRED" /></div><div className="setting-row"><div><strong>Rig write-back</strong><p>The prototype has no control path to operational equipment.</p></div><StatusTag value="DISABLED" /></div></Section>
    </>
  )
}
function SearchDialog({ close, navigate }: { close: () => void; navigate: (id: PageId) => void }) {
  const [query, setQuery] = useState('')
  const input = useRef<HTMLInputElement>(null)
  useEffect(() => input.current?.focus(), [])
  const results = useMemo(() => pageOrder.filter((id) => `${pageMeta[id].title} ${pageMeta[id].description}`.toLowerCase().includes(query.toLowerCase())), [query])
  return (
    <div className="dialog-backdrop" onMouseDown={close} role="presentation">
      <div className="search-dialog" role="dialog" aria-modal="true" aria-label="Search NWIS" onMouseDown={(event) => event.stopPropagation()}>
        <div className="dialog-input"><label htmlFor="global-search">Search</label><input ref={input} id="global-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search pages and concepts" /><kbd>ESC</kbd></div>
        <div className="search-results">{results.length ? results.map((id) => <button key={id} onClick={() => { navigate(id); close() }}><strong>{pageMeta[id].title}</strong><span>{pageMeta[id].description}</span></button>) : <EmptyState title="No results" text="Try a well name, evidence, validation, or review." />}</div>
      </div>
    </div>
  )
}
function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return <section className="content-section" id={id}><h2>{title}</h2>{children}</section>
}
function Callout({ label, children }: { label: string; children: ReactNode }) {
  return <aside className="callout"><strong>{label}</strong><div>{children}</div></aside>
}
function Definition({ term, text }: { term: string; text: string }) {
  return <div className="definition"><code>{term}</code><p>{text}</p></div>
}
function FieldTable({ rows }: { rows: [string, string, string][] }) {
  return <div className="field-table">{rows.map(([name, type, description]) => <div className="field-row" key={name}><div><code>{name}</code><span>{type}</span></div><p>{description}</p></div>)}</div>
}
function Steps({ items }: { items: [string, string][] }) {
  return <ol className="steps">{items.map(([title, text], index) => <li key={title}><span>{index + 1}</span><div><strong>{title}</strong><p>{text}</p></div></li>)}</ol>
}
function CodeBlock({ code, language }: { code: string; language: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => { await navigator.clipboard.writeText(code); setCopied(true); window.setTimeout(() => setCopied(false), 1200) }
  return <div className="code-block"><div className="code-head"><span>{language}</span><button onClick={copy}>{copied ? 'Copied' : 'Copy'}</button></div><pre><code>{code}</code></pre></div>
}
function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong><small>{note}</small></div>
}
function StatusTag({ value, accent = false }: { value: string; accent?: boolean }) {
  return <span className={`status-tag ${accent ? 'status-accent' : ''}`}>{value.replaceAll('_', ' ')}</span>
}
function DataTable({ headers, rows, numericColumns = [] }: { headers: string[]; rows: ReactNode[][]; numericColumns?: number[] }) {
  return <div className="table-scroll"><table><thead><tr>{headers.map((header, index) => <th key={header} className={numericColumns.includes(index) ? 'numeric' : ''}>{header}</th>)}</tr></thead><tbody>{rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, index) => <td key={index} className={numericColumns.includes(index) ? 'numeric' : ''}>{cell}</td>)}</tr>)}</tbody></table></div>
}
function DepthProgress({ depth }: { depth: number }) {
  const progress = Math.max(0, Math.min(100, ((depth - 2210) / (2580 - 2210)) * 100))
  return <div className="depth-progress"><div className="depth-labels"><span>Tipam top · 2,210 m</span><span>Barail top · 2,580 m</span></div><div className="depth-line"><span className="risk-window" /><span className="bit-marker" style={{ left: `${progress}%` }}><i />{depth.toLocaleString()}</span></div></div>
}
function ReasonList({ label, values }: { label: string; values: string[] }) {
  return <div><span className="eyebrow">{label}</span>{values.length ? <ul>{values.map((value) => <li key={value}>{value}</li>)}</ul> : <p className="muted">None recorded</p>}</div>
}
function WellTrack({ name, top, base, eventTop, eventBottom, current }: { name: string; top: number; base: number; eventTop: number; eventBottom: number; current: number | null }) {
  const eventStart = ((eventTop - top) / (base - top)) * 100
  const eventHeight = ((eventBottom - eventTop) / (base - top)) * 100
  const currentPos = current ? ((current - top) / (base - top)) * 100 : null
  return <div className="well-track"><h3>{name}</h3><div className="track-scale"><span>{top.toLocaleString()}</span><span>{base.toLocaleString()}</span></div><div className="track-body"><div className="track-event" style={{ top: `${eventStart}%`, height: `${eventHeight}%` }}>loss interval</div>{currentPos !== null && <div className="track-bit" style={{ top: `${currentPos}%` }}>bit</div>}</div><p>Tipam Sandstone</p></div>
}
function EmptyState({ title, text }: { title: string; text: string }) {
  return <div className="empty-state"><strong>{title}</strong><p>{text}</p><span /></div>
}
function LoadingState() {
  return <div className="loading-state" role="status"><p>Retrieving structured evidence…</p><div className="skeleton-line" /><div className="skeleton-line short" /></div>
}
function ErrorState({ title, text }: { title: string; text: string }) {
  return <div className="error-state" role="alert"><strong>{title}</strong><p>{text}</p></div>
}
export default App
