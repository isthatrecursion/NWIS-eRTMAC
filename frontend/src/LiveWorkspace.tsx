import { useEffect, useRef, useState, type FormEvent } from 'react'
import { API_BASE, request, type ApiEvidence } from './api'
import type { ChannelValue, RuntimeAlert } from './generated-contracts'
import { PlanningIntegration } from './WorkflowWorkspace'

type LiveChannel = Required<Pick<ChannelValue, 'value' | 'unit' | 'timestamp' | 'source' | 'quality_status' | 'age_s' | 'freshness_threshold_s'>>
type LiveAlert = Pick<RuntimeAlert, 'id' | 'lifecycle' | 'evidence_state' | 'peak_state' | 'snoozed_until' | 'notification_count' | 'history'>
interface LiveResponse {
  session: {well_id: string; playing: boolean; speed: number; id: string; adapter: string; cursor: number; frame_count: number; md_interval_m: number[]; formation: string}
  context: {timestamp: string; clock: string; source: string; bit_md_m: number | null; hole_md_m: number | null; tvd_m: number | null;
    formation_id: string | null; next_formation_id: string | null; distance_to_next_top_m: number | null; formation_uncertainty: {status: string; candidate_formation_ids: string[]}; operation_state: string; context_conflict: boolean;
    conflicts: string[]; missing: string[]; channels: Record<string, LiveChannel>; field_sources: Record<string,string>}
  assessment: {historical: ApiEvidence; corroboration: {state: string; gates: Record<string, boolean>; summary: string;
    flow_deficit_l_min: number | null; pit_drop_m3: number | null; ecd_sg: number | null; ecd_change_sg: number | null;
    mud_weight_sg: number | null; mud_weight_change_sg: number | null; activation: {stage: string; distance_to_event_m: number | null}; policy: Record<string, number | string>; aligned_windows_m: number[][]; missing_or_invalid_channels: string[]}; recommendation: string;
    lessons: {severity: string; event_md_interval_m: number[] | null; mud_context: Record<string,number|string>; well_id: string; event_id: string; mitigation: string | null; outcome: string | null; document_id: string;
      source: {text: string; page: number} | null; language: string}[]}
  alert: LiveAlert | null
}

const savedRun = 'nwis-replay-run-v1'
const display = (value: number | string | null | undefined, digits=1) => value == null ? 'Unknown' : typeof value === 'number' ? value.toLocaleString(undefined,{maximumFractionDigits:digits}) : value
const names: Record<string,string> = {bit_md_m:'Bit MD',hole_md_m:'Hole MD',flow_in_l_min:'Flow in',flow_out_l_min:'Flow out',pit_volume_m3:'Pit volume',ecd_sg:'ECD',tvd_m:'Observed TVD',inclination_deg:'Observed inclination',hole_section_in:'Observed hole section',operation_state:'Operation',mud_weight_sg:'Mud weight',wob_kn:'WOB',rpm:'RPM',torque_kn_m:'Torque',hookload_kn:'Hookload',standpipe_pressure_kpa:'SPP',gas_pct:'Gas',rop_m_h:'ROP'}

export default function LiveWorkspace({rig=false}: {rig?: boolean}) {
  const [data, setData] = useState<LiveResponse|null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const playing = data?.session.playing ?? false
  const [streamStatus, setStreamStatus] = useState('Disconnected')
  const lock = useRef(false)
  const alive = useRef(true)
  const [adapter, setAdapter] = useState('REPLAY')
  const [from, setFrom] = useState('2460')
  const [to, setTo] = useState('2580')
  const [datasetId, setDatasetId] = useState('')
  const [uploaded, setUploaded] = useState('')
  const [failureChannel, setFailureChannel] = useState('flow_out_l_min')
  const [quality, setQuality] = useState('STALE')
  const [actor, setActor] = useState('')
  const [manual, setManual] = useState<Record<string,string>>({bit_md_m:'2400',hole_md_m:'2600',flow_in_l_min:'950',flow_out_l_min:'945',pit_volume_m3:'410',ecd_sg:'1.19',mud_weight_sg:'1.16',wob_kn:'90',rpm:'120',torque_kn_m:'12',hookload_kn:'1200',standpipe_pressure_kpa:'18000',gas_pct:'0.5',rop_m_h:'20',hole_section_in:'8.5',operation_state:'DRILLING'})

  useEffect(()=>{
    alive.current = true
    const controller = new AbortController()
    lock.current=true;setBusy(true)
    const restore=async()=>{
      let run=localStorage.getItem(savedRun)
      let value:LiveResponse|null=null
      const packaged=await request<{enabled:boolean;session_id:string|null}>('/api/demo/session',{signal:controller.signal})
      if(packaged.enabled&&packaged.session_id&&localStorage.getItem('nwis-demo-seed-session-v1')!==packaged.session_id){run=packaged.session_id;localStorage.setItem('nwis-demo-seed-session-v1',packaged.session_id)}
      if(run){try{value=await request<LiveResponse>(`/api/replay/sessions/${encodeURIComponent(run)}/evaluate`,{method:'POST',signal:controller.signal})}catch{if(!controller.signal.aborted)localStorage.removeItem(savedRun)}}
      if(!value&&!controller.signal.aborted){run=packaged.enabled?packaged.session_id:null;if(run)value=await request<LiveResponse>(`/api/replay/sessions/${run}/evaluate`,{method:'POST',signal:controller.signal})}
      if(value&&alive.current){setData(value);setAdapter(value.session.adapter);localStorage.setItem(savedRun,value.session.id);localStorage.setItem('nwis-active-well-v1',value.session.well_id)}
    }
    void restore().catch(reason=>{if(alive.current&&!controller.signal.aborted)setError(reason instanceof Error?reason.message:'Session unavailable')}).finally(()=>{if(!controller.signal.aborted){lock.current=false;if(alive.current)setBusy(false)}})
    return ()=>{alive.current=false;controller.abort()}
  },[])

  async function perform(path: string, body?: unknown) {
    if(lock.current)return
    lock.current=true;setBusy(true);setError('')
    try {
      const value = await request<LiveResponse>(path,{method:'POST',headers:{'Content-Type':'application/json'},body:body === undefined ? undefined : JSON.stringify(body)})
      if(alive.current){setData(value);localStorage.setItem(savedRun,value.session.id);localStorage.setItem('nwis-active-well-v1',value.session.well_id);}
    } catch(reason) { if(alive.current){setError(reason instanceof Error ? reason.message : 'Evaluation failed');setData(null)} }
    finally{lock.current=false;if(alive.current)setBusy(false)}
  }

  useEffect(()=>{
    if(!data || data.session.adapter!=='REPLAY')return
    const run = data.session.id
    const base = new URL(API_BASE)
    base.protocol = base.protocol === 'https:' ? 'wss:' : 'ws:'
    const socket = new WebSocket(`${base.toString().replace(/\/$/,'')}/api/v1/replay/sessions/${run}/stream`)
    socket.onopen = ()=>setStreamStatus('Connected')
    socket.onmessage = event=>{try{const value=JSON.parse(event.data) as LiveResponse;if(alive.current)setData(value)}catch{setStreamStatus('Invalid stream frame')}}
    socket.onerror = ()=>setStreamStatus('Stream unavailable; use Refresh')
    socket.onclose = ()=>setStreamStatus('Disconnected; use Refresh')
    return ()=>socket.close()
  },[data?.session.id,data?.session.adapter])

  useEffect(()=>{
    if(!data || data.session.adapter!=='MANUAL')return
    const run=data.session.id
    const timer=window.setInterval(()=>void perform(`/api/replay/sessions/${run}/evaluate`),5000)
    return ()=>window.clearInterval(timer)
  },[data?.session.id,data?.session.adapter])

  function create(e: FormEvent) {
    e.preventDefault()
    void perform('/api/replay/sessions',{well_id:'SYN-ACTIVE-01',formation:'TIPAM',md_interval_m:[Number(from),Number(to)],adapter,dataset_id:adapter==='REPLAY' && datasetId ? datasetId : null})
  }

  async function upload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();if(lock.current)return
    lock.current=true;setBusy(true);setError('')
    try {
      const uploadedData=await request<{id:string;frame_count:number}>('/api/replay/datasets',{method:'POST',body:new FormData(e.currentTarget)})
      const value=await request<LiveResponse>('/api/replay/sessions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({well_id:'SYN-ACTIVE-01',formation:'TIPAM',md_interval_m:[Number(from),Number(to)],radius_km:3,adapter:'REPLAY',dataset_id:uploadedData.id})})
      if(alive.current){
        setDatasetId(uploadedData.id);setAdapter('REPLAY');setData(value)
        setUploaded(`${uploadedData.frame_count} CSV frames validated. Replay session ${value.session.id} is ready at frame 1.`)
        localStorage.setItem(savedRun,value.session.id);localStorage.setItem('nwis-active-well-v1',value.session.well_id)
      }
    }catch(reason){if(alive.current)setError(reason instanceof Error ? reason.message : 'CSV upload failed')}
    finally{lock.current=false;if(alive.current)setBusy(false)}
  }

  async function action(kind: string) {
    if(!data?.alert || lock.current || !actor.trim())return
    lock.current=true;setBusy(true);setError('')
    try {
      const alert=await request<LiveAlert>(`/api/alerts/${data.alert.id}/transition`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:kind,actor,snooze_seconds:60})})
      if(alive.current)setData(previous=>previous?{...previous,alert}:null)
    }catch(reason){if(alive.current)setError(reason instanceof Error ? reason.message : 'Alert action failed')}
    finally{lock.current=false;if(alive.current)setBusy(false)}
  }

  const context=data?.context, history=data?.assessment.historical, live=data?.assessment.corroboration
  if(rig)return <section className="content-section rig-simple" id="rig-current"><h2>Rig brief</h2><p className="muted">Simulation only · {data?.session.well_id||'No selected well'}</p>{error&&<p role="alert">{error}</p>}{!data?<p><a href="#brief">Start or load a replay in Next Interval Brief</a>.</p>:<><dl className="live-context-grid"><div><dt>Current / next formation</dt><dd>{context?.formation_id||'Unknown'} / {context?.next_formation_id||'Unknown'}</dd></div><div><dt>Depth / distance to next top</dt><dd>{display(context?.bit_md_m)} m / {display(context?.distance_to_next_top_m)} m</dd></div></dl><div className="important-alert"><h3>Mud loss · {live?.state==='NO_EVIDENCE'?'No activated advisory':live?.state.replaceAll('_',' ')||'Unknown'}</h3><p>Historical {history?.state.replaceAll("_"," ")} · {history?.sentence}</p><p>Projected event {display(live?.activation.distance_to_event_m)} m ahead.</p><p>{data.alert?.lifecycle||'No active alert'}</p><a href={`#evidence?snapshot=${history?.id}`}>Why?</a></div><div className="live-context-grid">{['flow_in_l_min','flow_out_l_min','pit_volume_m3','mud_weight_sg','ecd_sg','gas_pct'].map(k=><div key={k}><strong>{names[k]}</strong><p>{display(context?.channels[k]?.value,3)} {context?.channels[k]?.unit}</p><small>{context?.channels[k]?.quality_status||'MISSING'}</small></div>)}</div><label>Operator name<input value={actor} onChange={e=>setActor(e.target.value)}/></label><button className="button-primary" disabled={!actor.trim()||busy||!data.alert||data.alert.lifecycle==='RESOLVED'} onClick={()=>void action('acknowledge')}>Acknowledge</button><details><summary>Why this advisory? Source controls</summary><p>{data.assessment.recommendation}</p>{data.assessment.lessons.map(l=><p key={l.event_id}><a href={`#documents?document=${l.document_id}&page=${l.source?.page||1}`}>{l.well_id} source page</a> · {l.mitigation||'Response not recorded'}</p>)}</details></>}</section>
  return <>
    <section id={rig?'rig-current':'current'} className="content-section"><h2>Current well context</h2>
      <div className="callout"><strong>Simulation only</strong><div>Label-free CSV replay or manually entered samples. No real rig feed and no equipment write-back. Replay pauses its simulation clock; manual timestamps use UTC.</div></div>
      {!rig && <details open={!data}><summary>Replay setup and data source</summary><form className="filters" onSubmit={create}>
        <label>Adapter<select value={adapter} onChange={e=>setAdapter(e.target.value)}><option value="REPLAY">CSV replay</option><option value="MANUAL">Manual samples</option></select></label>
        <label>Monitor from MD (m)<input type="number" min="2200" max="2580" value={from} required onChange={e=>setFrom(e.target.value)} /></label>
        <label>Monitor to MD (m)<input type="number" min="2200" max="2580" value={to} required onChange={e=>setTo(e.target.value)} /></label>
        <button className="button-primary" disabled={busy}>Start new run</button><button type="button" className="button-secondary" disabled={busy} onClick={()=>void perform('/api/replay/demo')}>Load full mud-loss demo</button>
      </form><details><summary>Use another label-free CSV</summary><p>Columns: elapsed_s, bit_md_m, operation_state, flow_in_l_min, flow_out_l_min, pit_volume_m3, ecd_sg. Units are seconds, metres, L/min, m³ and SG. Optional channels: rop_m_h (m/h), mud_weight_sg (SG), wob_kn (kN), rpm, torque_kn_m (kN·m), hookload_kn (kN), standpipe_pressure_kpa (kPa), gas_pct (%), hole_md_m (m). Maximum 1 MB. A valid upload immediately creates a replay session for the interval selected above.</p><form className="upload-form" onSubmit={upload}><label>Replay CSV<input type="file" name="file" accept=".csv,text/csv" required /></label><button className="button-secondary" disabled={busy}>{busy?'Processing…':'Validate and start replay'}</button></form><p role="status">{uploaded}</p>{datasetId&&<button className="button-text" onClick={()=>{setDatasetId('');setUploaded('Generated fixture selected for the next run.')}}>Use generated fixture</button>}</details></details>}
      {error&&<div className="error-state" role="alert"><strong>Current assessment unavailable</strong><p>{error}</p></div>}
      {busy&&<div role="status"><p>Evaluating the simulation… Last displayed values are a previous snapshot.</p><div className="skeleton-line" /></div>}
      {!data&&!busy&&<p>No active session. Start a run in Next interval brief.</p>}
      {data&&context&&<><dl className="live-context-grid">
        {[['Well',data.session.well_id],['Bit MD',`${display(context.bit_md_m)} m`],['TVD',`${display(context.tvd_m)} m`],['Formation',context.formation_id||'Unknown'],['Next formation',context.next_formation_id||'Unknown'],['Distance to next top',`${display(context.distance_to_next_top_m)} m`],['Formation uncertainty',context.formation_uncertainty.status],['Operation',context.operation_state]].map(([name,value])=><div key={name}><dt>{name}</dt><dd className="mono">{value}</dd></div>)}
      </dl><div className="important-alert"><h3>Mud-loss look-ahead · {live?.state.replaceAll('_',' ')}</h3><p>{history?.sentence} · Alert {data.alert?.lifecycle||'not activated'}.</p><a href={`#evidence?snapshot=${history?.id}`}>Why? Inspect risk evidence and sources</a> · <a href="#rig">Simplified rig view</a></div><p>Live freshness: {Object.values(context.channels).filter(c=>c.quality_status==="FRESH").length} / {Object.keys(context.channels).length} channels fresh. Required warning channels: {live?.gates.required_channels_fresh?"fresh":"unavailable or stale"}.</p><p className="muted">{context.source} · {context.clock} · <code>{context.timestamp}</code></p>
      {data.session.adapter==='REPLAY'&&<><div className="toolbar"><button className="button-primary" disabled={!playing&&(busy||data.session.cursor>=data.session.frame_count-1)} onClick={()=>void perform(`/api/replay/sessions/${data.session.id}/control`,{action:playing?'pause':'play',speed:data.session.speed})}>{playing?'Pause replay':'Play replay'}</button><button className="button-secondary" disabled={busy||playing||data.session.cursor>=data.session.frame_count-1} onClick={()=>void perform(`/api/replay/sessions/${data.session.id}/advance`,{frames:1})}>Advance one frame</button><button className="button-secondary" disabled={busy||playing||data.session.cursor>=data.session.frame_count-1} onClick={()=>void perform(`/api/replay/sessions/${data.session.id}/advance`,{frames:10})}>Advance 10 frames</button><button className="button-secondary" disabled={busy} onClick={()=>void perform(`/api/replay/sessions/${data.session.id}/control`,{action:'reset'})}>Reset same run</button><label>Speed<select value={data.session.speed} onChange={e=>void perform(`/api/replay/sessions/${data.session.id}/control`,{action:'speed',speed:Number(e.target.value)})}>{[1,5,10,20,50,100].map(v=><option key={v} value={v}>{v}×</option>)}</select></label><label>Seek frame<input type="range" min="0" max={data.session.frame_count-1} value={data.session.cursor} disabled={busy||playing} onChange={e=>void perform(`/api/replay/sessions/${data.session.id}/control`,{action:'seek',cursor:Number(e.target.value)})}/></label></div><p className="muted">Frame <code>{data.session.cursor+1}/{data.session.frame_count}</code>. Backend playback follows recorded elapsed time at the selected speed. Stream: {streamStatus}. Reset and seek restart the shared simulation episode and retain the audit trail.</p></>}
      <button className="button-text" disabled={busy} onClick={()=>void perform(`/api/replay/sessions/${data.session.id}/evaluate`)}>Refresh context and evidence</button>
      {context.conflicts.length>0&&<div className="callout"><strong>Context conflict</strong><div>{context.conflicts.join('; ')}. Warning escalation is blocked.</div></div>}
      {context.missing.length>0&&<p className="muted">{context.missing.join('; ')}.</p>}
      </>}
    </section>
    {data?.session.adapter==='MANUAL'&&!rig&&<section className="content-section"><h2>Manual samples</h2><p>Submit observation values with the current UTC timestamp. Repeated values alone do not prove a sustained trend.</p><form onSubmit={e=>{e.preventDefault();void perform(`/api/replay/sessions/${data.session.id}/manual`,{samples:Object.fromEntries(Object.entries(manual).map(([key,value])=>[key,{value:value===''?null:key==='operation_state'?value:Number(value),timestamp:new Date().toISOString(),quality_status:'VALID'}]))})}}><div className="filters">{Object.entries(manual).map(([key,value])=><label key={key}>{names[key]}{key==='operation_state'?<select value={value} onChange={e=>setManual(v=>({...v,[key]:e.target.value}))}>{['DRILLING','TRIPPING','CIRCULATING','CEMENTING','UNKNOWN'].map(op=><option key={op}>{op}</option>)}</select>:<input type="number" step="any" value={value} onChange={e=>setManual(v=>({...v,[key]:e.target.value}))}/>}</label>)}</div><button className="button-primary" disabled={busy}>Submit timestamped samples</button></form></section>}
    <section id={rig?'advisory':'lookahead'} className="content-section"><h2>Mud-loss look-ahead</h2>
      {data&&history&&live&&<><p><span className="status-tag">{busy?'ASSESSMENT PENDING':live.state}</span> · historical state <code>{history.state}</code></p><p>{history.sentence}</p><p>Monitoring <code>{data.session.md_interval_m.join('–')} m MD</code> in {data.session.formation}. Activation: {live.activation.stage}; distance to event {display(live.activation.distance_to_event_m)} m. Individual aligned event envelopes: <code>{live.aligned_windows_m.map(v=>v.map(n=>n.toFixed(1)).join('–')).join('; ')||'None transferable'}</code>.</p>
      <dl className="live-context-grid"><div><dt>Return-flow deficit</dt><dd className="mono">{display(live.flow_deficit_l_min)} L/min</dd></div><div><dt>Pit drop over trend window</dt><dd className="mono">{display(live.pit_drop_m3,2)} m³</dd></div><div><dt>ECD / change</dt><dd className="mono">{display(live.ecd_sg,3)} / {display(live.ecd_change_sg,3)} SG</dd></div><div><dt>Mud weight / change</dt><dd className="mono">{display(live.mud_weight_sg,3)} / {display(live.mud_weight_change_sg,3)} SG</dd></div></dl>
      <p>{live.summary}. <a href="#evidence">Open planning evidence explorer</a>.</p><details><summary>Evidence behind this simulation snapshot</summary><p>Historical snapshot <code>{history.id}</code>. <a href={`${API_BASE}/api/evidence/snapshots/${history.id}`} target="_blank" rel="noreferrer">Open exact snapshot JSON</a>.</p><div className="table-scroll"><table><thead><tr><th>Well</th><th>Role</th><th className="numeric">Weight</th><th>Reason</th></tr></thead><tbody>{history.rows.map(row=><tr key={row.well_id}><td>{row.well_id}</td><td>{row.role}</td><td className="numeric">{row.weight.toFixed(3)}</td><td>{row.reason.replaceAll('_',' ')}<details><summary>Why / why not</summary><p>{[...row.analog.support,...row.analog.penalties,...row.analog.unknowns,...row.analog.blockers].join('; ')||'No additional factors'}</p>{row.transfers.map(t=><div key={t.event_id}><p><code>{t.event_id}</code> · {t.decision} · weight {t.weight.toFixed(3)}</p><p>{[...t.support,...t.penalties,...t.unknowns,...t.blockers].join('; ')}</p>{t.source&&<blockquote>{t.source.text}</blockquote>}<a href={`${API_BASE}/api/documents/${t.document_id}/source`} target="_blank" rel="noreferrer">Original event source report</a></div>)}{row.clean_source&&<><blockquote>{row.clean_source.source_text}</blockquote><a href={`${API_BASE}/api/documents/${row.clean_source.document_id}/source`} target="_blank" rel="noreferrer">Verified clean source report</a></>}</details></td></tr>)}</tbody></table></div></details><div className="table-scroll"><table><thead><tr><th>Warning gate</th><th>Result</th></tr></thead><tbody>{Object.entries(live.gates).map(([key,value])=><tr key={key}><td>{key.replaceAll('_',' ')}</td><td><span className="status-tag">{value?'PASS':'BLOCKED'}</span></td></tr>)}</tbody></table></div>
      <div className="callout"><strong>Verify and review</strong><div>{data.assessment.recommendation}</div></div><p className="muted">Configured thresholds: sustained deficit ≥ max({live.policy.flow_deficit_min_l_min} L/min, {Number(live.policy.flow_deficit_fraction)*100}%) for {live.policy.flow_sustained_min_s} s and {live.policy.flow_sustained_min_samples} measurements; pit drop ≥ {live.policy.pit_drop_min_m3} m³ over {live.policy.trend_min_s}–{live.policy.trend_max_s} s. All required samples must be fresh and time-coherent. Not a calibrated field warning.</p></>}
    </section>
    <section id={rig?'acknowledge':'population'} className="content-section"><h2>Alert lifecycle</h2>
      {data?.alert?<><p><code>{data.alert.id}</code> · <span className="status-tag">{data.alert.lifecycle}</span></p><p>{data.alert.lifecycle==='RESOLVED'?'Evidence at resolution':'Current evidence'} <code>{data.alert.evidence_state}</code>; peak observed <code>{data.alert.peak_state}</code>. {data.alert.notification_count} recorded notification events. Notifications are an in-app audit ledger, not email or SMS.</p>{data.alert.snoozed_until&&<p>Snoozed until <code>{data.alert.snoozed_until}</code> on the context clock.</p>}
      <label>Operator name<input value={actor} maxLength={120} onChange={e=>setActor(e.target.value)} /></label><div className="toolbar"><button className="button-primary" disabled={busy||playing||!actor.trim()||data.alert.lifecycle==='RESOLVED'} onClick={()=>void action('acknowledge')}>Acknowledge</button><button className="button-secondary" disabled={busy||playing||!actor.trim()||data.alert.lifecycle==='RESOLVED'} onClick={()=>void action('snooze')}>Snooze 60 seconds</button><button className="button-secondary" disabled={busy||playing||!actor.trim()||data.alert.lifecycle==='RESOLVED'} onClick={()=>void action('resolve')}>Resolve</button></div>
      <details><summary>Alert audit trail</summary><div className="table-scroll"><table><thead><tr><th>Event</th><th>Actor</th><th>Notification</th></tr></thead><tbody>{data.alert.history.map(event=><tr key={event.id}><td>{event.event}</td><td>{event.actor}</td><td>{event.notified?'Recorded':'None'}</td></tr>)}</tbody></table></div></details></>:<p>No alert exists for this simulation interval. Live signals alone cannot create a historical mud-loss warning.</p>}
      <p className="muted">One shared alert per well, risk and fixed stratigraphic monitoring interval across runs. Acknowledgement does not clear signals. Resolution remains latched until an explicit reset or seek restarts the simulated episode.</p>
      {data?.assessment.lessons.map(lesson=><div className="evidence-transfer" key={lesson.event_id}><h3>Historical response · {lesson.well_id}</h3><p>Severity: {lesson.severity||'UNKNOWN'} · event MD interval: {lesson.event_md_interval_m?.join('–')||'Single reported depth'}. Extracted mud weight: {display(lesson.mud_context.mud_weight_sg,3)} SG; ECD: {display(lesson.mud_context.ecd_sg,3)} SG.</p><p>Mitigation: {lesson.mitigation||'Not documented'} Outcome: {lesson.outcome||'Not documented'}</p><p>{lesson.language}</p>{lesson.source&&<blockquote>{lesson.source.text}</blockquote>}<a href={`${API_BASE}/api/documents/${lesson.document_id}/source`} target="_blank" rel="noreferrer">Open original source report</a></div>)}
    </section>
    {data?.session.well_id==='SYN-DEMO-ACTIVE'&&<section className="content-section" id="demo-failure"><h2>Controlled failure demonstration</h2><p>Each step resets the isolated demo and follows a deterministic sequence. Stale flow-out must block escalation while replay depth continues.</p><div className="toolbar">{[['RESET','Reset demonstration'],['ELEVATED','Historical Elevated'],['STALE_FLOW','Stale flow-out: continue replay'],['RECOVER','Restore flow-out: corroborate'],['PASSED','Pass interval: resolve']].map(([scenario,label])=><button className="button-secondary" key={scenario} disabled={busy} onClick={()=>void perform('/api/demo/scenario',{session_id:data.session.id,scenario})}>{label}</button>)}</div></section>}
    {data&&<PlanningIntegration sessionId={data.session.id} revision={data.session.adapter==='MANUAL'?Date.parse(data.context.timestamp):data.session.playing?Math.floor(data.session.cursor/5):data.session.cursor}/>}
    <section id="signals" className="content-section"><h2>Per-channel freshness</h2>
      {context&&<div className="table-scroll" tabIndex={0} role="region" aria-label="Channel quality table"><table><thead><tr><th>Channel</th><th className="numeric">Value</th><th>Quality</th><th className="numeric">Age (s)</th><th className="numeric">Freshness limit (s)</th><th>Source timestamp</th></tr></thead><tbody>{Object.entries(context.channels).map(([key,c])=><tr key={key}><td>{names[key]||key}<br/><small>{c.source}</small></td><td className="numeric">{display(c.value,3)} {c.unit}</td><td><span className="status-tag">{c.quality_status}</span></td><td className="numeric">{display(c.age_s)}</td><td className="numeric">{display(c.freshness_threshold_s)}</td><td className="mono">{c.timestamp||'No sample'}</td></tr>)}</tbody></table></div>}
      {!rig&&data?.session.adapter==='REPLAY'&&<form className="filters" onSubmit={e=>{e.preventDefault();void perform(`/api/replay/sessions/${data.session.id}/quality`,{channel:failureChannel,quality})}}><label>Failure channel<select value={failureChannel} onChange={e=>setFailureChannel(e.target.value)}>{Object.keys(names).map(key=><option key={key} value={key}>{names[key]}</option>)}</select></label><label>Quality injection<select value={quality} onChange={e=>setQuality(e.target.value)}>{['STALE','MISSING','SUSPECT','FRESH'].map(value=><option key={value}>{value}</option>)}</select></label><button className="button-secondary" disabled={busy||playing}>Apply simulated quality</button></form>}
      <p>Freshness limits are configured separately per channel and displayed above. Future timestamps and invalid values are suspect. Missing fields are not silently replaced with fresh sensor values.</p>
      {context&&<details><summary>Computed context and fallback provenance</summary><dl className="evidence-reasons">{Object.entries(context.field_sources).map(([field,source])=><div key={field}><dt>{field}</dt><dd>{source}</dd></div>)}</dl></details>}
    </section>
  </>
}
