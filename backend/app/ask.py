"""Allowlisted, local, deterministic question answering. Document text is data only."""
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .store import repository
from .evidence import active_records, candidate, evaluate, transfer, snapshot
from .gazetteer import match_formation
from .domain.units import normalize

VERSION = "grounded-ask/1.0"
router = APIRouter(prefix="/api")
TOOLS = ("well_lookup", "formation_lookup", "event_filter", "offset_selection", "alignment", "evidence_retrieval", "mitigation_retrieval", "alert_lookup", "source_retrieval")
NUMBER = re.compile(r"(?<![\w.])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?(?![\w.])")
Intent = Literal["WELL", "FORMATION", "EVENTS", "OFFSETS", "ALIGNMENT", "EVIDENCE", "MITIGATIONS", "ALERTS", "UNSUPPORTED"]


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    question: str = Field(min_length=3, max_length=2000)
    active_well_id: str = "SYN-ACTIVE-01"
    session_id: str | None = None
    formation: str = "TIPAM"
    radius_km: float = Field(default=3, gt=0, le=100)


class QueryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Intent
    well_ids: list[str]
    active_well_id: str
    formation: str
    risk_type: str
    event_id: str | None = None
    md_interval_m: tuple[float, float] | None = None
    radius_km: float
    operation_state: str = "DRILLING"
    tools: list[str]
    assumptions: list[str]
    limitation: str | None = None


class AnswerClaim(BaseModel):
    text: str
    provenance_type: Literal["FACT", "COMPUTED", "INFERRED"]
    tool_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class GroundedAnswer(BaseModel):
    id: str
    status: Literal["ANSWERED", "LIMITED", "REFUSED"]
    question: str
    plan: QueryPlan
    facts: list[AnswerClaim]
    computed_pattern: list[AnswerClaim]
    interpretation: list[AnswerClaim]
    gaps: list[str]
    sources: list[dict]
    tool_calls: list[dict]
    numeric_verification: dict
    version: str
    model_version: Literal["NONE_DETERMINISTIC_RENDERER"]
    generated_at: str


def require(store, kind, key):
    value = store.get(kind, key)
    if value is None: raise ValueError(f"Unknown {kind}: {key}")
    return value


def plan_question(request, store):
    q = request.question
    low = q.lower()
    well_ids = [w["id"] for w in store.all("well") if w["id"].lower() in low or w["name"].lower() in low]
    explicit_ids = re.findall(r"\bSYN-[A-Z0-9-]+", q.upper())
    unknown = [key for key in explicit_ids if key not in {w["id"] for w in store.all("well")}]
    named_well = re.search(r"\bwell\s+[\"']?([A-Za-z][A-Za-z0-9_.-]*)", q, re.I)
    context_words = {"context", "lookup", "name", "data", "history", "records", "evidence", "pressure", "formation", "is", "has", "in", "for", "within", "active", "offset"}
    if named_well and not well_ids and named_well.group(1).lower() not in context_words:
        unknown.append("Requested well name is not recognized; use a stored well name or identifier")
    active = request.active_well_id
    if request.session_id: active = require(store, "live_session", request.session_id)["well_id"]
    target = require(store, "well", active)
    formation = request.formation
    for f in target["formations"]:
        if re.search(rf"\b{re.escape(f['formation_id'])}\b", q, re.I): formation = f["formation_id"]
    named = re.search(r"formation\s+([A-Za-z]+)", q, re.I)
    if named and named.group(1).lower() not in {"top", "tops", "lookup", "context", "interval", "alignment", "evidence"}:
        match = match_formation(named.group(1))
        if match["formation_id"]: formation = match["formation_id"]
        elif match["requires_review"]: unknown.append("Unresolved formation alias")
    risk = next((risk for risk, pattern in [("STUCK_PIPE", r"stuck\s*pipe"), ("KICK", r"kick|influx|overpressure"), ("TORQUE_DYSFUNCTION", r"torque|dysfunction|stick.?slip"), ("CEMENTING_ISSUE", r"cement"), ("MUD_LOSS", r"mud.?loss|lost.?circulation") ] if re.search(pattern, low)), "MUD_LOSS")
    event_id = next((e["id"] for e in active_records(store, "event") if e["id"].lower() in low), None)
    intent = "UNSUPPORTED"
    for name, pattern in [("ALERTS", r"alert|warning|why.*(?:elevated|lesson)|current.*risk"), ("ALIGNMENT", r"align|project.*event"), ("MITIGATIONS", r"mitigat|remedial|outcome|historical.*response|lesson"), ("OFFSETS", r"offset|nearby|nearest|analog"), ("EVIDENCE", r"evidence|support|counter|risk.*ahead|look.ahead"), ("EVENTS", r"event|history|historical|occurred"), ("FORMATION", r"formation|top|stratigraph"), ("WELL", r"well|mud.weight|pressure.context|casing")]:
        if re.search(pattern, low): intent = name; break
    assumption = ["Local deterministic planner; no language model computes risk", "Formation and radius use explicit UI defaults unless specified", "Planning comparisons use DRILLING operation context, or CEMENTING for cement-job queries; live operational prediction is unavailable"]
    radius = request.radius_km
    radius_match = re.search(r"(?:within|radius)\s+(\d+(?:\.\d+)?)\s*km", low)
    if radius_match:
        radius = float(radius_match.group(1))
        if not 0 < radius <= 100: unknown.append("Radius outside supported range")
    interval = None
    match = re.search(r"(?<![\w.-])(\d+(?:\.\d+)?)\s*(?:m|ft)?\s*(?:to|–|-)\s*(\d+(?:\.\d+)?)\s*(m|ft)\s*(?:md)?", low)
    if match:
        interval = tuple(normalize(float(match.group(i)), match.group(3), "depth").value for i in (1,2))
        if not 0 <= interval[0] < interval[1] <= 15000: unknown.append("Invalid depth interval")
    if re.search(r"(?:execute|shell|delete|upload|email|http[s]?://|ignore.*instructions|pump.*(?:pressure|rate)|recommend.*(?:pressure|rate))", low): unknown.append("Only read-only historical and evidence queries are supported; operating instructions and external actions are unavailable")
    f = next((f for f in target["formations"] if f["formation_id"] == formation), None)
    if not f: unknown.append("Target formation is absent")
    if interval and f and not f["top_md_m"] <= interval[0] < interval[1] <= (f.get("base_md_m") or f["top_md_m"]): unknown.append("Interval must lie within a complete target formation")
    tool_map = {"WELL": ["well_lookup"], "FORMATION": ["well_lookup", "formation_lookup"], "EVENTS": ["event_filter", "source_retrieval"], "OFFSETS": ["offset_selection"], "ALIGNMENT": ["event_filter", "alignment", "source_retrieval"], "EVIDENCE": ["evidence_retrieval", "source_retrieval"], "MITIGATIONS": ["event_filter", "mitigation_retrieval", "source_retrieval"], "ALERTS": ["alert_lookup", "evidence_retrieval", "source_retrieval"], "UNSUPPORTED": []}
    limitation = "; ".join(unknown) if unknown else "No supported intent recognized. Ask about wells, formations, events, offsets, alignment, evidence, historical mitigation or alerts." if intent == "UNSUPPORTED" else None
    return QueryPlan(intent=intent, well_ids=well_ids, active_well_id=active, formation=formation, risk_type=risk, event_id=event_id, md_interval_m=interval, radius_km=radius, operation_state="CEMENTING" if risk == "CEMENTING_ISSUE" else "DRILLING", tools=tool_map[intent] if not limitation else [], assumptions=assumption, limitation=limitation)


class DeterministicTools:
    def __init__(self, store, plan): self.store, self.plan, self.calls = store, plan, []

    def call(self, name, inputs):
        if name not in TOOLS or name not in self.plan.tools: raise ValueError("Tool is not allowlisted in the question plan")
        if len(self.calls) >= 8: raise ValueError("Query tool budget exceeded")
        p, store = self.plan, self.store
        active = require(store, "well", p.active_well_id)
        if name == "well_lookup": output = [require(store, "well", key) for key in p.well_ids or [p.active_well_id]]
        elif name == "formation_lookup": output = [f for w in (p.well_ids or [p.active_well_id]) for f in require(store, "well", w)["formations"] if f["formation_id"] == p.formation]
        elif name in ("event_filter", "mitigation_retrieval"):
            # Future/held-out active events and quarantined/superseded observations cannot leak.
            output = [e for e in active_records(store, "event") if not require(store, "well", e["well_id"]).get("held_out") and e["well_id"] != p.active_well_id and e["event_type"] == p.risk_type and e.get("formation_id") == p.formation and (not p.well_ids or e["well_id"] in p.well_ids) and (not p.event_id or e["id"] == p.event_id)][:50]
        elif name == "offset_selection": output = sorted([candidate(active, w, p.formation, p.radius_km) for w in store.all("well") if w["id"] != active["id"] and not w.get("held_out") and candidate(active, w, p.formation, p.radius_km)["surface_distance_km"] <= p.radius_km], key=lambda w: -w["relevance"])
        elif name == "alignment":
            events = inputs["events"]
            output = [snapshot(store, "transferability", transfer(active, require(store, "well", e["well_id"]), e, p.radius_km, p.operation_state)) for e in events[:10]]
        elif name == "alert_lookup": output = sorted([a for a in store.all("alert") if a["well_id"] == p.active_well_id and a["risk_type"] == p.risk_type and a["formation"] == p.formation], key=lambda a:a.get("updated_at", ""))
        elif name == "evidence_retrieval":
            if inputs.get("snapshot_id"):
                output = require(store, "evidence_snapshot", inputs["snapshot_id"])
                if output["active_well_id"] != p.active_well_id: raise ValueError("Evidence snapshot belongs to another well")
            else:
                f = next(f for f in active["formations"] if f["formation_id"] == p.formation)
                bounds = p.md_interval_m or ([2460,2520] if f["top_md_m"] <= 2460 < 2520 <= (f.get("base_md_m") or 0) else [f["top_md_m"], f.get("base_md_m")])
                if bounds[1] is None: raise ValueError("Formation base is missing; explicit reviewed interval needed")
                output = evaluate(store, active, p.formation, p.risk_type, bounds, p.radius_km, p.operation_state)
        else:
            output = []
            for event in inputs.get("events", [])[:20]:
                span = require(store, "source_span", event["source_span_id"])
                doc = require(store, "document", event["document_id"])
                output.append({"id": span["id"], "document_id": doc["id"], "page": span["page"], "text": span["text"], "title": doc["title"], "review_status": event["review_status"], "content_sha256": hashlib.sha256(doc["page_data"][span["page"]-1]["text"].encode()).hexdigest()})
        call_id = "TOOL-"+str(len(self.calls)+1)
        self.calls.append({"id": call_id, "name": name, "inputs": inputs, "output": output, "version": VERSION})
        return output, call_id


def numeric_tokens(value):
    if isinstance(value, dict): return set().union(*(numeric_tokens(v) for v in value.values())) if value else set()
    if isinstance(value, list): return set().union(*(numeric_tokens(v) for v in value)) if value else set()
    return set(NUMBER.findall(str(value))) if value is not None and not isinstance(value, bool) else set()


def verify_claims(claims, calls, sources):
    output = {c["id"]: c["output"] for c in calls}
    passages = {s["id"]: s["text"] for s in sources}
    rejected = []
    for claim in claims:
        allowed = set()
        if any(key not in output for key in claim.tool_ids) or any(key not in passages for key in claim.source_ids): rejected.append("Unknown citation")
        for key in claim.tool_ids: allowed.update(numeric_tokens(output.get(key)))
        for key in claim.source_ids: allowed.update(numeric_tokens(passages.get(key)))
        # Spelled-out quantities are unsupported in free-form drafts as well.
        if re.search(r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|hundred|thousand|million|billion)\b", claim.text, re.I): rejected.append("Write quantities as tool-returned numerals")
        missing = numeric_tokens(claim.text)-allowed
        if missing: rejected.append("Unsupported numeric tokens: "+", ".join(sorted(missing)))
    return {"verified": not rejected, "rejections": rejected, "policy": "Every numeric token must occur in an explicitly cited deterministic output or source passage"}


def answer(request, store):
    plan = plan_question(request, store)
    tools = DeterministicTools(store, plan)
    facts, computed, interpretations, gaps, sources, events = [], [], [], list(plan.assumptions), [], []
    def claim(text, provenance, call_id, source_ids=None): return AnswerClaim(text=text, provenance_type=provenance, tool_ids=[call_id], source_ids=source_ids or [])
    if plan.limitation: gaps.append(plan.limitation)
    else:
        for name in plan.tools:
            inputs = {"events": events} if name in ("alignment", "mitigation_retrieval", "source_retrieval") else {}
            if name == "evidence_retrieval" and plan.intent == "ALERTS" and tools.calls[-1]["output"]: inputs = {"snapshot_id": tools.calls[-1]["output"][-1]["evidence_snapshot_id"]}
            output, call_id = tools.call(name, inputs)
            if name == "well_lookup":
                for well in output:
                    mud = well['mud_program']
                    facts.append(claim(f"Well {well['id']}: {well['name']}; status {well['status']}; datum {well['datum']}; CRS {well['crs']}. Stored programme: mud system {mud.get('mud_system', 'unknown')}; mud weight {mud.get('mud_weight_sg', 'unknown')} SG; ECD {mud.get('ecd_sg', 'unknown')} SG; hole section {mud.get('hole_section_in', 'unknown')} in.", "FACT", call_id))
            elif name == "formation_lookup":
                for f in output: facts.append(claim(f"{f['formation_id']} top {f['top_md_m']} m MD; base {f['base_md_m']} m MD; configured uncertainty {f['uncertainty_m']} m.", "FACT", call_id))
            elif name == "event_filter":
                events = output
                for e in events[:10]: facts.append(claim(f"{e['well_id']} records {e['event_type']} at {e['md_from_m']} m MD; formation {e['formation_id']}; review {e['review_status']}; severity {e['severity']}.", "FACT", call_id, [e["source_span_id"]]))
                if not events: gaps.append("No eligible historical event records match; future active-well events are excluded")
            elif name == "mitigation_retrieval":
                for e in output[:10]: facts.append(claim(f"Historical response in {e['well_id']}: {e.get('mitigation') or 'not documented'}. Outcome: {e.get('outcome') or 'not documented'}.", "FACT", call_id, [e["source_span_id"]]))
                interpretations.append(claim("Historical responses require review against the approved programme; they are not operating instructions.", "INFERRED", call_id))
            elif name == "offset_selection":
                for row in output[:10]: computed.append(claim(f"{row['well_id']}: surface distance {row['surface_distance_km']} km; relevance {row['relevance']}; {row['decision']}. Blockers: {'; '.join(row['blockers']) or 'none recorded'}.", "COMPUTED", call_id))
            elif name == "alignment":
                for row in output: computed.append(claim(f"Event {row['event_id']}: {row['decision']}; projected MD interval {json.dumps((row.get('projection') or {}).get('projected_md_interval_m'))} m; transfer weight {row['weight']}.", "COMPUTED", call_id))
            elif name == "alert_lookup":
                for a in output: facts.append(claim(f"Alert {a['id']}: {a['evidence_state']}, lifecycle {a['lifecycle']}; peak state {a['peak_state']}; notifications {a['notification_count']}.", "FACT", call_id))
                if not output: gaps.append("No persisted alert exists for the requested well, risk and formation")
            elif name == "evidence_retrieval":
                computed.append(claim(f"Historical {output['risk']} state {output['state']}: {output['support_count']} supporting wells, {output['counter_count']} verified clean crossings, {output['unknown_count']} unknown wells. Interval {json.dumps(output['md_interval_m'])} m MD. Snapshot {output['id']}.", "COMPUTED", call_id))
                interpretations.append(claim("This is an uncalibrated historical evidence state, not event probability or a live warning.", "INFERRED", call_id))
                events = [t["inputs"]["event"] for row in output["rows"] for t in row["transfers"] if t["event_id"] == row.get("selected_event_id")]
                if not output["support_count"]: gaps.append("Insufficient transferable supporting history; a risk prediction cannot be supplied")
                if output["unknown_count"]: gaps.append("Unknown wells need reviewed interval coverage and event-specific context")
            elif name == "source_retrieval": sources = output
    verification = verify_claims(facts+computed+interpretations, tools.calls, sources)
    if not verification["verified"]:
        facts, computed, interpretations = [], [], []
        gaps.extend(verification["rejections"])
    status = "REFUSED" if plan.limitation or not verification["verified"] else "LIMITED" if len(gaps) > len(plan.assumptions) or not facts+computed else "ANSWERED"
    result = GroundedAnswer(id="ASK-"+hashlib.sha256((request.question+datetime.now(timezone.utc).isoformat()).encode()).hexdigest()[:20], status=status, question=request.question, plan=plan, facts=facts, computed_pattern=computed, interpretation=interpretations, gaps=gaps, sources=sources, tool_calls=tools.calls, numeric_verification=verification, version=VERSION, model_version="NONE_DETERMINISTIC_RENDERER", generated_at=datetime.now(timezone.utc).isoformat()).model_dump(mode="json")
    store.put("ask_run", result)
    return result


@router.post("/ask")
def ask(request: AskRequest):
    try: return answer(request, repository())
    except (ValueError, StopIteration) as exc: raise HTTPException(422, str(exc) or "Requested context is unavailable") from exc


@router.post("/ask/plan")
def planner(request: AskRequest):
    try: return plan_question(request, repository()).model_dump(mode="json")
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc


class VerifyDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ask_run_id: str
    claims: list[AnswerClaim] = Field(max_length=30)


@router.post("/ask/verify")
def verify_draft(request: VerifyDraft):
    run = repository().get("ask_run", request.ask_run_id)
    if not run: raise HTTPException(404, "Ask run not found")
    return verify_claims(request.claims, run["tool_calls"], run["sources"])
