import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { API_BASE, request, type ApiDocument, type ApiEvent, type ApiOffset, type ApiProjection, type ApiReview, type ApiWell, type ApiAnalog, type ApiEvidence } from './api'
import type { PageId } from './types'
import LiveWorkspace from './LiveWorkspace'
import { EvidenceChain, ValidationWorkspace } from './WorkflowWorkspace'
import NormalizedCompare from './NormalizedCompare'
import AskWorkspace from './AskWorkspace'
import GeoBasemap from './GeoBasemap'
import useReplayMap from './useReplayMap'

const ACTIVE = 'SYN-ACTIVE-01'
const selectedActive=()=>localStorage.getItem('nwis-active-well-v1')||ACTIVE
const routeParams=()=>new URLSearchParams(window.location.hash.split('?')[1]||'')
const number = (value: number | null, digits = 0) => value === null ? 'Unknown' : value.toLocaleString(undefined, {maximumFractionDigits: digits})

function useResource<T>(path: string, revision = 0) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    let current = true
    setData(null)
    if (!path) { setLoading(false); return }
    setLoading(true); setError('')
    request<T>(path).then(value => { if (current) setData(value) }).catch(reason => { if (current) setError(reason instanceof Error ? reason.message : 'Request failed') }).finally(() => { if (current) setLoading(false) })
    return () => { current = false }
  }, [path, revision])
  return {data, error, loading}
}

function Section({id, title, children}: {id: string; title: string; children: ReactNode}) {
  return <section id={id} className="content-section"><h2>{title}</h2>{children}</section>
}

function ErrorMessage({message}: {message: string}) {
  return message ? <div role="alert" className="error-state"><strong>Could not load data</strong><p>{message}</p><p>API: <code>{API_BASE}</code>.</p></div> : null
}

function Loading() { return <div role="status" className="loading-state"><p>Loading stored records…</p><div className="skeleton-line" /></div> }
function Tag({children}: {children: ReactNode}) { return <span className="status-tag">{children}</span> }

export default function IntegratedPages({page}: {page: PageId}) {
  if (page === 'offsets') return <OffsetExplorer />
  if (page === 'compare') return <AlignmentExplorer />
  if (page === 'documents') return <DocumentExplorer />
  if (page === 'review') return <ReviewExplorer />
  if (page === 'validation') return <ValidationWorkspace />
  if (page === 'ask') return <AskWorkspace />
  if (page === 'evidence') return <EvidenceWorkspace brief={false} />
  if (page === 'brief' || page === 'rig') return <LiveWorkspace rig={page === 'rig'} />
  return null
}

export function IntegratedOverview() {
  const {data, loading, error} = useResource<{well_count:number;document_count:number;event_count:number;data_mode:string;record_sources:{wells:{synthetic:number;declared_non_synthetic:number;unclassified:number};documents:{synthetic:number;declared_non_synthetic:number;unclassified:number}}}>('/api/meta')
  const wells = useResource<ApiWell[]>('/api/wells')
  const documents = useResource<ApiDocument[]>('/api/documents')
  const gazetteer = useResource<{entries:{id:string;name:string;sources:{url:string;authority:string}[]}[]}>('/api/gazetteer')
  const activeId = selectedActive()
  const active = wells.data?.find(well=>well.id===activeId)
  const sources = data?.record_sources
  const nonSynthetic = (sources?.wells.declared_non_synthetic ?? 0) + (sources?.documents.declared_non_synthetic ?? 0)
  return <section className="content-section" id="data-inventory"><h2>Loaded data</h2>
    {loading ? <Loading /> : error ? <ErrorMessage message={error} /> : data && <>
      <p>The site reads these counts from the running API database: <strong>{data.well_count} wells</strong>, <strong>{data.document_count} current reports</strong>, and <strong>{data.event_count} extracted events</strong>. Current data mode: <strong>{data.data_mode.replaceAll('_',' ')}</strong>.</p>
      <div className="count-strip"><div><strong>{sources?.wells.synthetic ?? 0}</strong><span>synthetic wells</span></div><div><strong>{sources?.documents.synthetic ?? 0}</strong><span>synthetic reports</span></div><div><strong>{nonSynthetic}</strong><span>declared non-synthetic records</span></div></div>
      {nonSynthetic===0 && <p>No non-synthetic well or report records are loaded. The map markers, replay and risk examples are generated data; a geographic basemap and sourced formation names do not make them field observations.</p>}
      {nonSynthetic>0 && <p>“Non-synthetic” is the supplied record flag, not independent verification of field origin or quality.</p>}
      {active && <p>Selected active well: <strong>{active.name}</strong> ({active.id}). <a href="#offsets">Inspect stored geometry</a>.</p>}
      {documents.data && <p>Loaded reports: {documents.data.length ? documents.data.slice(0,5).map((doc,index)=><span key={doc.id}>{index>0?', ':''}<a href={`#documents?document=${encodeURIComponent(doc.id)}`}>{doc.title}</a></span>) : 'none'}{documents.data.length>5?'…':''}.</p>}
      {gazetteer.data && <><p>Reference catalogue: {gazetteer.data.entries.length} formation names with source references in the codebase. These are geological terminology, not well-event data.</p><details><summary>View formation-name catalogue</summary><ul>{gazetteer.data.entries.map(entry=><li key={entry.id}>{entry.name} ({entry.id}) · {entry.sources.map((source,index)=><span key={source.url}>{index>0?', ':''}<a href={source.url} target="_blank" rel="noreferrer">{source.authority}</a></span>)}</li>)}</ul></details></>}
    </>}
    {!loading && (wells.error || documents.error || gazetteer.error) && <p role="status">Some inventory details could not be loaded; the counts above come from the backend.</p>}
  </section>
}

function OffsetExplorer() {
  const ACTIVE=selectedActive()
  const [radius, setRadius] = useState(3)
  const [formation, setFormation] = useState('TIPAM')
  const [selection, setSelection] = useState('SYN-NHK-02')
  const [rankingWell,setRankingWell]=useState(ACTIVE)
  const {data, loading, error} = useResource<ApiOffset[]>(`/api/wells/${ACTIVE}/offsets/at-depth?radius_km=${radius}&formation=${formation}`)
  const active=useResource<ApiWell>(`/api/wells/${ACTIVE}`).data
  const survey=useResource<{points:{md_m:number;x_m:number;y_m:number;tvd_m:number}[]}>(`/api/wells/${ACTIVE}/survey`).data
  const replay=useReplayMap(ACTIVE)
  const swap=useResource<{swap:{well_id:string;surface_rank:number;target_rank:number}[]|null;rows:{well_id:string;surface_rank:number;target_rank:number;decision:string}[]}>(`/api/wells/${rankingWell}/ranking-swap?radius_km=${radius}&formation=${formation}`).data
  const selected = data?.find(row => row.well.id === selection)
  useEffect(()=>{if(data?.length&&!data.some(row=>row.well.id===selection))setSelection(data[0].well.id)},[data,selection])
  const analogs = useResource<ApiAnalog[]>(`/api/wells/${ACTIVE}/analogs?radius_km=${radius}&formation=${formation}`)
  const analog = analogs.data?.find(row=>row.well_id === selection)
  return <>
    <Section id="map" title="Surface map">
      <div className="filters"><label>Surface radius<select value={radius} onChange={e=>setRadius(Number(e.target.value))}>{[1,2,3,5].map(n=><option key={n} value={n}>{n} km</option>)}</select></label><label>Formation<select value={formation} onChange={e=>setFormation(e.target.value)}>{['TIPAM','BARAIL','NAMSANG'].map(f=><option key={f}>{f}</option>)}</select></label></div>
      <ErrorMessage message={error} />{loading && <Loading />}
      {data && active && !loading && <><div className="map-replay-controls"><div><strong>Simulated live bit position</strong><span>{replay.snapshot?.context.bit_md_m == null ? replay.status : `${number(replay.snapshot.context.bit_md_m,1)} m MD · ${replay.snapshot.session.playing?'playing':'paused'} · frame ${replay.snapshot.session.cursor+1}/${replay.snapshot.session.frame_count}`}</span><small>{replay.status}</small></div>{replay.snapshot?.session.adapter==='REPLAY'&&<div><button className="button-secondary" disabled={replay.busy} onClick={()=>void replay.control(replay.snapshot!.session.playing?'pause':'play')}>{replay.snapshot.session.playing?'Pause':'Play at 20×'}</button><button className="button-secondary" disabled={replay.busy} onClick={()=>void replay.advance()}>Next frame</button><button className="button-secondary" disabled={replay.busy} onClick={()=>void replay.control('reset')}>Reset</button></div>}</div><GeoBasemap active={active} offsets={data} radiusKm={radius} selectedId={selection} onSelect={setSelection} survey={survey?.points} bitMd={replay.snapshot?.context.bit_md_m ?? null} bitQuality={replay.snapshot?.context.channels.bit_md_m?.quality_status} /><p className="figure-caption">Real OpenStreetMap geography around an approximate Upper Assam anchor. Every well marker and the moving bit projection are synthetic, not surveyed field locations. The bit follows the stored directional survey as the replay advances; it is a computed plan view, not a live GPS reading. Target separation uses local ENU coordinates and minimum-curvature surveys at 21 corresponding formation fractions. Map tiles need an internet connection.</p></>}
    </Section>
    <Section id="ranking" title="Calculated separation">
      {swap&&<details open><summary>Surface versus target-depth ranking</summary><p>Ranking demonstration well: {rankingWell}{rankingWell!==ACTIVE?" (separate example; active well unchanged)":""}.</p>{swap.swap?<p>Computed ranking swap: {swap.swap.map(r=>`${r.well_id}: surface #${r.surface_rank}, target #${r.target_rank}`).join(' versus ')}. Geometry ranking does not override transferability blockers.</p>:<p>No ranking swap exists in the selected radius and formation. <button className="button-text" onClick={()=>setRankingWell('SYN-ACTIVE-01')}>Inspect the original divergent-trajectory field</button></p>}<div className="table-scroll"><table><thead><tr><th>Well</th><th>Surface rank</th><th>Target rank</th><th>Relevance decision</th></tr></thead><tbody>{swap.rows.map(r=><tr key={r.well_id}><td>{r.well_id}</td><td>{r.surface_rank}</td><td>{r.target_rank}</td><td>{r.decision}</td></tr>)}</tbody></table></div></details>}
      {data && <div className="table-scroll"><table><thead><tr><th>Well</th><th className="numeric">Surface km</th><th className="numeric">At target km</th><th>Geometry / relevance</th></tr></thead><tbody>{data.map(row=><tr key={row.well.id}><td><button className="table-link" onClick={()=>setSelection(row.well.id)}>{row.well.id}</button></td><td className="numeric">{number(row.surface_distance_km, 3)}</td><td className="numeric">{number(row.target_distance_km, 3)}</td><td>{row.reason || 'Calculated'}<br/>{analogs.data?.find(a=>a.well_id===row.well.id)?.decision||'Unknown relevance'}</td></tr>)}</tbody></table></div>}
      {selected && <div className="detail-panel"><div><h3>{selected.well.id}</h3><p className="muted">Computed geometry</p></div><div><span className="eyebrow">Mean separation</span><p className="mono">{number(selected.target_distance_km, 3)} km</p></div><div><span className="eyebrow">Minimum separation</span><p className="mono">{number(selected.geometry?.minimum_distance_m??null)} m</p></div><div><span className="eyebrow">Samples</span><p className="mono">{selected.geometry?.samples??'Unavailable'}</p></div></div>}
    </Section>
    <Section id="method" title="Why this offset?">
      <ErrorMessage message={analogs.error} />
      {analog && <><p><Tag>{analog.decision}</Tag> <code>{analog.well_id}</code> · relevance <code>{analog.relevance.toFixed(3)}</code></p><ReasonList record={analog} /></>}
      <div className="callout"><strong>Geometry is not transferability</strong><div>Surface proximity selects candidates. Trusted structural mismatch can exclude a well. Event-specific context, alignment and source quality are evaluated separately in the Evidence explorer.</div></div>
    </Section>
  </>
}

function ReasonList({record}: {record: ApiAnalog}) {
  const value=(item:number|string|null)=>typeof item==='number'?number(item,3):item??'Unknown'
  return <><dl className="evidence-reasons">{(['support','penalties','unknowns','blockers'] as const).map(key=><div key={key}><dt>{key[0].toUpperCase()+key.slice(1)}</dt><dd>{record[key].length ? record[key].join('; ') : 'None'}</dd></div>)}</dl>{record.context_comparisons&&<details><summary>Context comparisons</summary><div className="table-scroll"><table><thead><tr><th>Context</th><th>Active</th><th>Historical</th><th>State</th><th>Factor</th></tr></thead><tbody>{record.context_comparisons.comparisons.map(item=><tr key={item.name}><td>{item.name.replaceAll('_',' ')}</td><td>{value(item.active_value)}</td><td>{value(item.offset_value)}</td><td>{item.status}</td><td>{number(item.factor,3)}</td></tr>)}</tbody></table></div>{record.context_comparisons.derived_inputs&&Object.keys(record.context_comparisons.derived_inputs).length>0&&<details><summary>Calculation inputs</summary><pre>{JSON.stringify(record.context_comparisons.derived_inputs,null,2)}</pre></details>}</details>}</>
}

function EvidenceWorkspace({brief}: {brief: boolean}) {
  const ACTIVE=selectedActive()
  const [snapshot,setSnapshot]=useState(routeParams().get('snapshot')||'')
  useEffect(()=>{const sync=()=>setSnapshot(routeParams().get('snapshot')||'');window.addEventListener('hashchange',sync);return()=>window.removeEventListener('hashchange',sync)},[])
  const [chain,setChain]=useState<{snapshot:string;event:string}|null>(null)
  const [risk, setRisk] = useState('MUD_LOSS')
  const [from, setFrom] = useState('2460')
  const [to, setTo] = useState('2580')
  const [operation, setOperation] = useState('DRILLING')
  const [radius, setRadius] = useState('3')
  const [query, setQuery] = useState('risk=MUD_LOSS&md_from_m=2460&md_to_m=2580&radius_km=3&operation_state=DRILLING')
  const [role, setRole] = useState('ALL')
  const [selected, setSelected] = useState('')
  const [revision, setRevision] = useState(0)
  const resource = useResource<ApiEvidence>(snapshot?`/api/evidence/snapshots/${snapshot}`:`/api/wells/${ACTIVE}/lookahead?${query}`, revision)
  const result = resource.data
  const rows = result?.rows.filter(row=>role === 'ALL' || row.role === role)
  const detail = result?.rows.find(row=>row.well_id === selected)||result?.rows.find(row=>row.transfers.some(t=>t.event_id===routeParams().get('event')))
  function submit(e: FormEvent) {
    e.preventDefault(); setSelected('');setSnapshot('');setChain(null)
    setRevision(value=>value+1)
    setQuery(new URLSearchParams({risk, md_from_m: from, md_to_m: to, radius_km: radius, operation_state: operation}).toString())
  }
  return <>
    <Section id={brief?'current':'summary'} title="Historical interval evaluation">
      <p>Inspect the exact evidence snapshot, or evaluate a new Tipam planning interval with explicit assumptions.</p>
      <form className="filters" onSubmit={submit}>
        <label>Risk<select value={risk} onChange={e=>setRisk(e.target.value)}>{['MUD_LOSS','STUCK_PIPE','KICK','TORQUE_DYSFUNCTION','CEMENTING_ISSUE'].map(value=><option key={value}>{value}</option>)}</select></label>
        <label>From MD (m)<input type="number" min="2200" max="2580" required value={from} onChange={e=>setFrom(e.target.value)} /></label>
        <label>To MD (m)<input type="number" min="2200" max="2580" required value={to} onChange={e=>setTo(e.target.value)} /></label>
        <label>Radius<select value={radius} onChange={e=>setRadius(e.target.value)}>{['1','2','3','5'].map(value=><option key={value} value={value}>{value} km</option>)}</select></label>
        <label>Operation<select value={operation} onChange={e=>setOperation(e.target.value)}>{['DRILLING','TRIPPING','TRIPPING_IN','TRIPPING_OUT','REAMING','CIRCULATING','CEMENTING','STATIC','UNKNOWN'].map(value=><option key={value}>{value}</option>)}</select></label>
        <button className="button-primary" type="submit" disabled={resource.loading}>Evaluate interval</button>
      </form>
      <ErrorMessage message={resource.error} />{resource.loading && <Loading />}
      {result && <><p className="muted">Evaluated <code>{result.risk}</code> · <code>{result.md_interval_m.join('–')} m MD</code> · {result.operation_state}</p><div className="callout"><strong><Tag>{result.state.replaceAll('_',' ')}</Tag></strong><div><p>{result.sentence}</p><p>Uncalibrated historical evidence policy. No live warning is permitted.</p></div></div></>}
    </Section>
    <Section id={brief?'population':'records'} title="Evidence population">
      <div className="filters"><label>Evidence role<select value={role} onChange={e=>setRole(e.target.value)}>{['ALL','SUPPORT','COUNTER','UNKNOWN','EXCLUDED'].map(value=><option key={value}>{value}</option>)}</select></label></div>
      {result && <><div className="count-strip evidence-counts"><div><strong>{result.support_count}</strong><span>supporting wells</span></div><div><strong>{result.counter_count}</strong><span>verified clean crossings</span></div><div><strong>{result.unknown_count}</strong><span>unknown records</span></div><div><strong>{result.excluded_count}</strong><span>excluded wells</span></div></div>
        <div className="table-scroll evidence-table" tabIndex={0} role="region" aria-label="Evidence records table"><table><thead><tr><th>Well</th><th>Role</th><th className="numeric">Weight</th><th>Reason</th></tr></thead><tbody>{rows?.map(row=><tr key={row.well_id}><td><button className="table-link" onClick={()=>setSelected(row.well_id)}>{row.well_id}</button></td><td><Tag>{row.role}</Tag></td><td className="numeric">{row.weight.toFixed(3)}</td><td>{row.reason.replaceAll('_',' ')}</td></tr>)}</tbody></table></div>
        {!rows?.length && <p>No wells match this role filter.</p>}
      </>}
      {detail && <div className="evidence-detail"><h3>{detail.well_id} · {detail.role}</h3><ReasonList record={detail.analog} />
        {detail.transfers.map(t=><div key={t.event_id} className="evidence-transfer"><h3><code>{t.event_id}</code> · {t.decision}</h3><p>Transfer weight <code>{t.weight.toFixed(3)}</code>. Projected MD: <code>{t.projection?.projected_md_interval_m?.map(v=>number(v,1)).join('–') || 'Blocked'}</code></p>{t.source && <blockquote>{t.source.text}</blockquote>}<ReasonList record={t} /><p><button className="button-secondary" onClick={()=>setChain({snapshot:result!.id,event:t.event_id})}>Trace to source page</button> <a href={`${API_BASE}/api/documents/${t.document_id}/source`} target="_blank" rel="noreferrer">Open original report</a> · source <code>{t.source_span_id}</code></p><details><summary>Computed factors</summary><pre>{JSON.stringify(t.factors,null,2)}</pre></details></div>)}
        {detail.clean_source && <div className="callout"><strong>Verified clean evidence</strong><div><p>{detail.clean_source.source_text}</p><p>Required source envelope: <code>{detail.clean_source.required_source_interval_m.map(v=>number(v,1)).join('–')} m MD</code></p><a href={`${API_BASE}/api/documents/${detail.clean_source.document_id}/source`} target="_blank" rel="noreferrer">Original report, page {detail.clean_source.page}</a></div></div>}
      </div>}
    </Section>
    {chain&&<EvidenceChain snapshot={chain.snapshot} event={chain.event}/>}
    <Section id={brief?'lookahead':'provenance'} title="Policy and provenance">
      <p>Each well contributes at most one weight. Unknown and excluded wells never enter the weighted statistic. Counter-evidence requires reviewed coverage of the complete source uncertainty envelope and an explicit no-event statement.</p>
      {result && <><p>Policy <code>{result.policy_version}</code>. Snapshot <code>{result.id}</code>.</p><details><summary>Internal prototype statistics — not event probability</summary><dl className="evidence-reasons"><div><dt>Shrunk weighted statistic (p_hat)</dt><dd className="mono">{result.internal_statistics.p_hat?.toFixed(4) ?? 'Not estimable'}</dd></div><div><dt>Effective well count (n_eff)</dt><dd className="mono">{result.internal_statistics.n_eff.toFixed(3)}</dd></div></dl><p>p_hat = (weighted support + 1) / (total usable weight + 2). n_eff = sum(weights)² / sum(weights²).</p></details></>}
      <div className="callout"><strong>State boundary</strong><p>LESSON requires supporting history. ELEVATED requires at least two supporting wells, effective count ≥ 3 and internal statistic ≥ 0.45. These are uncalibrated demo thresholds. Empty or counter-only populations are not labeled safe. Simulated live corroboration and alert lifecycle are available in Next interval brief.</p></div>
    </Section>
    {brief && <Section id="signals" title="Live signals"><p>No live channels are connected. This page evaluates historical evidence only.</p></Section>}
  </>
}

function AlignmentExplorer() {
  const ACTIVE=selectedActive()
  const {data: docs, error: docError} = useResource<ApiDocument[]>('/api/documents')
  const [docId, setDocId] = useState('')
  const [eventId, setEventId] = useState('')
  const [targetId, setTargetId] = useState(ACTIVE)
  const [result, setResult] = useState<ApiProjection|null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const {data: wells} = useResource<ApiWell[]>('/api/wells')
  const selectedDoc = docId || docs?.find(doc=>doc.event_ids.length && !doc.is_scan)?.id || docs?.[0]?.id
  const {data: events} = useResource<ApiEvent[]>(selectedDoc ? `/api/documents/${selectedDoc}/events` : '')
  const event = events?.find(item=>item.id===eventId) || events?.[0]
  const source = wells?.find(well=>well.id===event?.well_id)
  const target = wells?.find(well=>well.id===targetId)
  const {data:survey} = useResource<{diagnostics:{max_dogleg_severity_deg_per_30m:number}}>(target?`/api/wells/${target.id}/survey`:'')
  useEffect(()=>{setResult(null)}, [docId, eventId, targetId])
  const calculate = async () => {
    if (!event) return
    setBusy(true);setError('')
    try { setResult(await request<ApiProjection>('/api/alignment/project-event', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({active_well_id:targetId,event_id:event.id})})) }
    catch(reason){setError(reason instanceof Error ? reason.message : 'Projection failed')}
    finally{setBusy(false)}
  }
  return <>
    <NormalizedCompare active={targetId}/>
    <Section id="alignment" title="Project a historical event">
      <div className="filters"><label>Source document<select value={selectedDoc||''} onChange={e=>{setDocId(e.target.value);setEventId('')}}>{docs?.filter(doc=>doc.event_ids.length).map(doc=><option key={doc.id} value={doc.id}>{doc.well_id} · {doc.is_scan?'OCR':'native'}</option>)}</select></label><label>Target well<select value={targetId} onChange={e=>setTargetId(e.target.value)}>{wells?.map(w=><option key={w.id}>{w.id}</option>)}</select></label></div>
      {events?.length ? <label>Event<select value={event?.id||''} onChange={e=>setEventId(e.target.value)}>{events.map(item=><option key={item.id} value={item.id}>{item.event_type} · {number(item.md_from_m,1)} m MD · {item.review_status}</option>)}</select></label> : <p>No extracted events in this document.</p>}
      <div className="toolbar" style={{marginTop:16}}><button className="button-primary" disabled={!event || busy} onClick={calculate}>{busy?'Calculating…':'Project event'}</button></div><ErrorMessage message={error||docError} />
      {result && <div className="advisory"><Tag>{result.decision}</Tag><h3>{result.projected_md_interval_m ? `${number(result.projected_md_interval_m[0],1)}–${number(result.projected_md_interval_m[1],1)} m MD` : result.reason?.replaceAll('_',' ')}</h3><p>{result.method?.replaceAll('_',' ')} · {result.alignment_confidence || 'blocked'}</p>{result.strat_fraction!==undefined && <p>Formation fraction: <code>{result.strat_fraction.toFixed(5)}</code></p>}<p className="muted">Algorithm <code>{result.algorithm_version || 'formation guard'}</code></p></div>}
    </Section>
    <Section id="tracks" title="Source and target intervals"><div className="track-grid"><FormationTrack well={source} eventDepth={event?.md_from_m??null} projected={null} /><FormationTrack well={target} eventDepth={null} projected={result?.projected_md_interval_m??null} /></div></Section>
    <Section id="uncertainty" title="Uncertainty and fallback"><p>The envelope includes formation, configured datum and event-depth uncertainty. Missing bases use estimated thickness with a wider interval. Absent formations and mismatched datums block projection.</p>{survey&&<p>Target survey maximum dogleg severity: {number(survey.diagnostics.max_dogleg_severity_deg_per_30m,3)} degrees / 30 m.</p>}{result?.uncertainty_components&&<p>Datum margin: {number(result.uncertainty_components.datum_margin_m,1)} m · event-depth margin: {number(result.uncertainty_components.event_depth_margin_m,1)} m · datum bounds: {result.uncertainty_components.datum_uncertainty_status.toLowerCase()}.</p>}{result?.inputs&&<details><summary>Retained alignment inputs</summary><pre>{JSON.stringify(result.inputs,null,2)}</pre></details>}<p>Select SYN-NHK-20 to inspect the pinch-out case or SYN-NHK-21 to inspect the estimated-thickness fallback.</p></Section>
  </>
}

function FormationTrack({well,eventDepth,projected}: {well: ApiWell|undefined;eventDepth: number|null;projected:[number,number]|null}) {
  const formation=well?.formations.find(f=>f.formation_id==='TIPAM')
  const low=2100, high=2800
  const top=formation?.top_md_m??low, base=formation?.base_md_m??high
  return <div className="well-track"><h3>{well?.id||'Select a well'}</h3><div className="track-body"><div className="formation-band" style={{top:`${(top-low)/(high-low)*100}%`,height:`${(base-top)/(high-low)*100}%`}}>{formation?'TIPAM':'Formation absent'}<small>{number(top)}–{number(formation?.base_md_m??null)} m MD</small></div>{eventDepth!==null && <div className="track-bit" style={{top:`${(eventDepth-low)/(high-low)*100}%`}}>event {number(eventDepth,1)}</div>}{projected && <div className="track-event" style={{top:`${(projected[0]-low)/(high-low)*100}%`,height:`${(projected[1]-projected[0])/(high-low)*100}%`}}>projected interval</div>}</div><p>Common MD scale: {low}–{high} m</p></div>
}

function DocumentExplorer() {
  const [revision, setRevision] = useState(0)
  const {data: docs, loading, error} = useResource<ApiDocument[]>('/api/documents',revision)
  const {data: wells} = useResource<ApiWell[]>('/api/wells')
  const [selection, setSelection] = useState(routeParams().get('document')||'')
  const [wellId, setWellId] = useState('SYN-NHK-02')
  const [uploadError, setUploadError] = useState('')
  const [busy, setBusy] = useState(false)
  const [pageNumber, setPageNumber] = useState(Number(routeParams().get('page'))||1)
  useEffect(()=>{const sync=()=>{if(!window.location.hash.startsWith('#documents'))return;setSelection(routeParams().get('document')||'');setPageNumber(Number(routeParams().get('page'))||1);setRevision(v=>v+1)};window.addEventListener('hashchange',sync);return()=>window.removeEventListener('hashchange',sync)},[])
  const [classification, setClassification] = useState('PRIVATE')
  const [docType, setDocType] = useState('AUTO')
  const selected = docs?.find(doc=>doc.id===selection) || docs?.[0]
  const {data: events} = useResource<ApiEvent[]>(selected ? `/api/documents/${selected.id}/events` : '',revision)
  const upload = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();setBusy(true);setUploadError('')
    const form = new FormData(e.currentTarget)
    form.set('classification', classification)
    form.set('doc_type', docType)
    try { const doc = await request<ApiDocument>('/api/documents/ingest',{method:'POST',body:form});setSelection(doc.id);setPageNumber(1);setRevision(n=>n+1) }
    catch(reason){setUploadError(reason instanceof Error?reason.message:'Upload failed')}
    finally{setBusy(false)}
  }
  return <>
    <Section id="library" title="Document library"><form className="upload-form" onSubmit={upload}><div className="filters"><label>Associate with well<select name="well_id" value={wellId} onChange={e=>setWellId(e.target.value)}>{wells?.filter(w=>!w.held_out).map(w=><option key={w.id}>{w.id}</option>)}</select></label><label>PDF or text report<input type="file" name="file" accept=".pdf,.txt,.md" required /></label><label>Classification<select value={classification} onChange={e=>setClassification(e.target.value)}><option>PRIVATE</option><option>PUBLIC</option></select></label><label>Report type<select value={docType} onChange={e=>setDocType(e.target.value)}>{['AUTO','DDR','WCR','MUD_LOG','CEMENT_REPORT'].map(kind=><option key={kind} value={kind}>{kind==='AUTO'?'Detect from content':kind}</option>)}</select></label></div><label className="inline-checkbox"><input type="checkbox" name="synthetic" value="true" defaultChecked />Synthetic document</label><button className="button-primary" disabled={busy}>{busy?'Extracting document…':'Upload and extract'}</button><ErrorMessage message={uploadError} /></form><ErrorMessage message={error} />{loading && <Loading />}
      {docs && <div className="table-scroll"><table><thead><tr><th>Report</th><th>Type / classification</th><th>Text source</th><th className="numeric">Confidence</th><th>Review</th></tr></thead><tbody>{docs.map(doc=><tr key={doc.id}><td><button className="table-link" onClick={()=>{setSelection(doc.id);setPageNumber(1)}}>{doc.title}</button><br/><code>{doc.well_id}</code></td><td>{doc.doc_type||'UNKNOWN'} / {doc.classification||'PRIVATE'}</td><td>{doc.is_scan?'OCR':'Native'}</td><td className="numeric">{number(doc.ocr_confidence*100,1)}%</td><td><Tag>{doc.review_status}</Tag></td></tr>)}</tbody></table></div>}
    </Section>
    <Section id="preview" title="Original page and extracted events">
      {selected && <><div className="toolbar"><a href={`${API_BASE}/api/documents/${selected.id}/source`} target="_blank" rel="noreferrer">Open original report</a><label>Page<select value={pageNumber} onChange={e=>setPageNumber(Number(e.target.value))}>{Array.from({length:selected.pages},(_,i)=><option key={i} value={i+1}>{i+1}</option>)}</select></label></div>{selected.title.toLowerCase().endsWith('.pdf') ? <SourceImage document={selected.id} page={pageNumber} events={events||[]} /> : <TextSource document={selected.id} page={pageNumber} events={events||[]}/>}
      {events?.some(event=>event.source.page===pageNumber) ? events.filter(event=>event.source.page===pageNumber).map(event=><article key={event.id} className="evidence-record"><div className="evidence-record-head"><Tag>{event.review_status}</Tag><code>{event.event_type}</code></div><h3>{number(event.md_from_m,1)} m MD · {event.formation_id||'Unverified formation'}</h3><blockquote>{event.source.text}</blockquote><p>FACT extraction · confidence {event.extraction_confidence||'Unknown'}</p><p>Symptom: {event.symptom||'Unspecified'}<br/>Mitigation: {event.mitigation||'Unspecified'}<br/>Outcome: {event.outcome||'Unspecified'}</p><details><summary>Extracted numerical fields</summary>{Object.entries(event.numerical_fields||{}).map(([name,field])=><p key={name}>{name.replaceAll("_"," ")}: {number(field.value,3)} {field.measurement.unit} · original {field.measurement.original_value} {field.measurement.original_unit}<br/>Source: {field.source.text}</p>)}</details><p className="muted">Page {event.source.page} · original depth {event.original_value} {event.original_unit} · <a href="#review">Review extraction</a></p></article>) : <p>No positive event extracted. Check interval coverage before interpreting a clean crossing.</p>}</>}
    </Section>
    <Section id="coverage" title="Coverage ledger">{selected && <CoverageLedger well={selected.well_id} revision={revision} />}</Section>
  </>
}

function TextSource({document,page,events}:{document:string;page:number;events:ApiEvent[]}) {
  const {data}=useResource<{text:string}>(`/api/documents/${document}/pages/${page}`)
  const selected=events.find(e=>e.source.page===page&&(!routeParams().get('span')||routeParams().get('span')===e.source_span_id))
  const offset=data&&selected?data.text.indexOf(selected.source.text):-1
  return <pre className="text-source">{offset>=0&&data&&selected?<>{data.text.slice(0,offset)}<mark>{selected.source.text}</mark>{data.text.slice(offset+selected.source.text.length)}</>:data?.text||'Loading original page…'}</pre>
}

function SourceImage({document,page,events}: {document:string;page:number;events:ApiEvent[]}) {
  const {data} = useResource<{page:number;lines:{bbox:number[]|null}[]}> (`/api/documents/${document}/pages/${page}`)
  // PDF page coordinates are mapped to the generated A4 fixture; arbitrary PDFs use actual image dimensions below.
  const [dimensions,setDimensions]=useState({width:595,height:842})
  return <div className="source-image"><img src={`${API_BASE}/api/documents/${document}/pages/${page}/image`} alt={`Original report page ${page}`} onLoad={e=>setDimensions({width:e.currentTarget.naturalWidth/1.5,height:e.currentTarget.naturalHeight/1.5})} />{data && events.filter(event=>event.source.page===page&&event.source.bbox).map(event=>{const box=event.source.bbox!;return <span className="source-box" key={event.id} style={{left:`${box[0]/dimensions.width*100}%`,top:`${box[1]/dimensions.height*100}%`,width:`${(box[2]-box[0])/dimensions.width*100}%`,height:`${(box[3]-box[1])/dimensions.height*100}%`}} />})}</div>
}

function CoverageLedger({well,revision}: {well:string;revision:number}) {
  const {data,error}=useResource<{id:string;md_interval:number[]|null;coverage_status:string;reviewer:string|null;source_text:string}[]>(`/api/wells/${well}/coverage`,revision)
  return <><ErrorMessage message={error} /><div className="table-scroll"><table><thead><tr><th>Interval MD</th><th>Status</th><th>Reviewed by</th></tr></thead><tbody>{data?.map(row=><tr key={row.id}><td className="mono">{row.md_interval?row.md_interval.map(n=>number(n,1)).join('–')+' m':'Unknown'}</td><td><Tag>{row.coverage_status}</Tag></td><td>{row.reviewer||'Pending'}</td></tr>)}</tbody></table></div><p className="muted">Probable coverage requires review. Missing coverage remains unknown.</p></>
}

function ReviewExplorer() {
  const [revision,setRevision]=useState(0)
  const selectedRun=localStorage.getItem('nwis-replay-run-v1')
  const {data:queue,error,loading}=useResource<ApiReview[]>(selectedRun?`/api/review?session_id=${selectedRun}`:'/api/review',revision)
  const [selection,setSelection]=useState('')
  const [reviewer,setReviewer]=useState('Prototype engineer')
  const [depth,setDepth]=useState('')
  const [depthUnit,setDepthUnit]=useState('m')
  const [depthTo,setDepthTo]=useState('')
  const [severity,setSeverity]=useState('UNKNOWN')
  const [formation,setFormation]=useState('TIPAM')
  const [status,setStatus]=useState('')
  const [busy,setBusy]=useState(false)
  const [confirmIdentity,setConfirmIdentity]=useState(false)
  const [dateFrom,setDateFrom]=useState('')
  const [dateTo,setDateTo]=useState('')
  const [reviewDocType,setReviewDocType]=useState('UNKNOWN')
  const [reviewClassification,setReviewClassification]=useState('PRIVATE')
  const {data:gazetteer}=useResource<{entries:{id:string;name:string}[]}>('/api/gazetteer')
  const selected=queue?.find(item=>item.id===selection)||queue?.[0]
  useEffect(()=>{setConfirmIdentity(false);setDateFrom(selected?.record.date_from||'');setDateTo(selected?.record.date_to||'');setReviewDocType(selected?.record.doc_type||'UNKNOWN');setReviewClassification(selected?.record.classification||'PRIVATE')},[selected?.id])
  const {data:events}=useResource<ApiEvent[]>(selected?`/api/documents/${selected.document_id}/events`:'',revision)
  const event=events?.find(item=>item.id===selected?.entity_id)
  useEffect(()=>{setDepthUnit('m');setDepth(event?.md_from_m?.toString()||'');setDepthTo(event?.md_to_m?.toString()||'');setSeverity(event?.severity||'UNKNOWN');setFormation(event?.formation_id||'TIPAM')},[event?.id])
  const resolve=async(action:string)=>{
    if(!selected)return
    setBusy(true);setStatus('')
    try{await request(`/api/review/${selected.id}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reviewer,action,confirm_well_identity:confirmIdentity,...(selected.kind==='document'?{doc_type:reviewDocType,classification:reviewClassification}:{}),...(selected.kind==='coverage'&&action==='correct'?{date_from:dateFrom||null,date_to:dateTo||null}:{}),...(selected.kind==='event'&&action==='correct'?{depth_value:depth?Number(depth):null,depth_unit:depthUnit,md_to_m:depthTo?Number(depthTo):null,severity,formation_id:formation}:{})})});setRevision(n=>n+1);setSelection('');setConfirmIdentity(false);setStatus('Review saved to the audit log.')}
    catch(reason){setStatus(reason instanceof Error?reason.message:'Review failed')}
    finally{setBusy(false)}
  }
  return <>
    <Section id="queue" title="Pending review"><ErrorMessage message={error} />{loading&&<Loading />}{queue&&<div className="table-scroll"><table><thead><tr><th>Type</th><th>Source</th><th>Reason</th></tr></thead><tbody>{queue.map(item=><tr key={item.id}><td><button className="table-link" onClick={()=>setSelection(item.id)}>{item.kind}</button></td><td><a href="#documents">{item.document_id.slice(0,12)}</a></td><td>{item.affects_active_lookahead&&<strong>Active look-ahead priority · </strong>}{item.reason}<small>{item.impact_reason}</small></td></tr>)}</tbody></table></div>}{queue?.length===0&&<p>No pending extraction or coverage reviews.</p>}</Section>
    <Section id="review-detail" title="Review detail">
      {selected&&<><Tag>{selected.kind}</Tag><p>{selected.reason}</p>
        {selected.kind==='document'&&<><div className="filters"><label>Report type<select value={reviewDocType} onChange={e=>setReviewDocType(e.target.value)}>{['UNKNOWN','DDR','WCR','MUD_LOG','CEMENT_REPORT'].map(kind=><option key={kind}>{kind}</option>)}</select></label><label>Classification<select value={reviewClassification} onChange={e=>setReviewClassification(e.target.value)}><option>PRIVATE</option><option>PUBLIC</option></select></label></div><label className="inline-checkbox"><input type="checkbox" checked={confirmIdentity} onChange={e=>setConfirmIdentity(e.target.checked)} />I confirm this report belongs to the associated well.</label></>}
        {selected.kind==='coverage'&&<><blockquote>{selected.record.source_text}<br/>{selected.record.date_source?.text}<br/>Confirm the interval and date interpretation before accepting.</blockquote>{selected.record.date_from&&<div className="filters"><label>Coverage from<input type="date" value={dateFrom} onChange={e=>setDateFrom(e.target.value)} /></label><label>Coverage to<input type="date" value={dateTo} onChange={e=>setDateTo(e.target.value)} /></label></div>}</>}
        {event&&<><blockquote>{event.source.text}</blockquote><div className="filters"><label>Corrected MD value<input type="number" min="0" max={depthUnit==='ft'?49212:15000} value={depth} onChange={e=>setDepth(e.target.value)} /></label><label>Depth units<select value={depthUnit} onChange={e=>setDepthUnit(e.target.value)}><option value="m">Metres</option><option value="ft">Feet</option></select></label><label>Event end MD, metres (optional)<input type="number" min="0" max="15000" value={depthTo} onChange={e=>setDepthTo(e.target.value)} /></label><label>Severity<select value={severity} onChange={e=>setSeverity(e.target.value)}>{['UNKNOWN','MINOR','PARTIAL','MODERATE','SEVERE','TOTAL'].map(v=><option key={v}>{v}</option>)}</select></label><label>Formation<select value={formation} onChange={e=>setFormation(e.target.value)}>{(gazetteer?.entries||[{id:'TIPAM',name:'Tipam'},{id:'BARAIL',name:'Barail'},{id:'NAMSANG',name:'Namsang'}]).map(f=><option key={f.id} value={f.id}>{f.name}</option>)}</select></label></div>{event.numerical_fields&&Object.keys(event.numerical_fields).length>0&&<details><summary>Grounded numerical fields</summary>{Object.entries(event.numerical_fields).map(([name,field])=><p key={name}><strong>{name.replaceAll('_',' ')}</strong>: {number(field.value,3)} {field.measurement.unit}<br/>Original: {field.measurement.original_value} {field.measurement.original_unit} · page {field.source.page}<br/>{field.source.text}</p>)}</details>}</>}
        <label>Reviewer<input value={reviewer} onChange={e=>setReviewer(e.target.value)} /></label><div className="toolbar" style={{marginTop:16}}><button className="button-primary" disabled={busy||!reviewer} onClick={()=>resolve('accept')}>Accept</button>{(selected.kind==='event'||selected.kind==='coverage'&&selected.record.date_from)&&<button className="button-secondary" disabled={busy||!reviewer} onClick={()=>resolve('correct')}>Save correction</button>}<button className="button-text" disabled={busy||!reviewer} onClick={()=>resolve('quarantine')}>Quarantine</button></div>
      </>}{status&&<p role="status">{status}</p>}
    </Section>
    <Section id="policy" title="Review policy"><p>Accept confirms the current extraction. A correction preserves the original source and stores the changed value with the reviewer. Coverage only becomes verified through an explicit review action.</p></Section>
  </>
}
