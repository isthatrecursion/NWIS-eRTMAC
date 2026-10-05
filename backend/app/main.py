from datetime import date, datetime, timezone
from contextlib import asynccontextmanager
import asyncio
import math
import re
from typing import Literal
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from .config import get_settings
from .geometry import project_event, separation, trajectory
from .ingestion import ingest
from .store import repository
from .evidence import candidate, transfer, evaluate, snapshot
from .live_routes import router as live_router
from .gazetteer import ENTRIES, VERSION as GAZETTEER_VERSION
from .secondary import MATURITY
from .safety import source_path

settings = get_settings()


@asynccontextmanager
async def lifespan(application):
    # A process restart pauses persisted replays; it never fast-forwards unattended time.
    for session in repository().all("live_session"):
        if session.get("playing"):
            session["playing"] = False
            repository().put("live_session", session)
    yield
    from .live_routes import PLAYBACK_TASKS
    tasks = list(PLAYBACK_TASKS.values())
    for task in tasks: task.cancel()
    if tasks: await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title=settings.app_name, version="0.10.0", lifespan=lifespan, description="Grounded local questions, deterministic risk engines, blind synthetic validation and repeatable demonstrations")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["*"], allow_headers=["*"])
app.include_router(live_router)
from .workflow import router as workflow_router
app.include_router(workflow_router)
from .ask import router as ask_router
from .demo_routes import router as demo_router
from .independent_validation import router as independent_validation_router
app.include_router(ask_router)
app.include_router(demo_router)
app.include_router(independent_validation_router)
from .api_support import install
install(app)


def require(kind, key):
    value = repository().get(kind, key)
    if value is None: raise HTTPException(404, f"{kind} not found")
    return value


def public_document(doc):
    return {k: v for k, v in doc.items() if k not in ("path", "page_data")}


def well_path(well):
    path = trajectory(well["survey"], well["x_m"], well["y_m"])
    repository().put("trajectory", {"id": well["id"], "points": path, "crs": well["crs"], "datum": well["datum"]})
    repository().save_spatial_path(well, path)
    return path


@app.get("/health")
def health():
    return {"status": "ok", "phase": "10", "environment": settings.environment}


@app.get("/api/meta")
def metadata():
    wells = repository().all("well")
    documents = [d for d in repository().all("document") if not d.get("superseded_by")]
    current_document_ids = {document["id"] for document in documents}
    events = [event for event in repository().all("event") if event.get("document_id") in current_document_ids]
    def source_counts(rows):
        flags = [row.get("synthetic_flag", row.get("synthetic")) for row in rows]
        return {"synthetic": sum(flag is True for flag in flags),
                "declared_non_synthetic": sum(flag is False for flag in flags),
                "unclassified": sum(flag is None for flag in flags)}
    well_sources, document_sources = source_counts(wells), source_counts(documents)
    flagged_synthetic = well_sources["synthetic"] + document_sources["synthetic"]
    flagged_other = well_sources["declared_non_synthetic"] + document_sources["declared_non_synthetic"]
    unclassified = well_sources["unclassified"] + document_sources["unclassified"]
    data_mode = "MIXED" if flagged_synthetic and flagged_other else "NON_SYNTHETIC_DECLARED" if flagged_other else "SYNTHETIC" if flagged_synthetic and not unclassified else "UNCLASSIFIED"
    return {"project": "eRTMAC-NWIS", "phase": "10",
        "data_mode": data_mode,
        "well_count": len(wells), "document_count": len(documents), "event_count": len(events),
        "record_sources": {"wells": well_sources, "documents": document_sources},
        "capabilities": ["synthetic-field", "native-pdf", "local-ocr", "coverage-ledger", "human-review", "minimum-curvature", "formation-alignment", "analog-selection", "event-transferability", "coverage-aware-evidence", "replay-csv-manual-adapters", "canonical-current-context", "per-channel-freshness", "mud-loss-corroboration", "audited-alert-lifecycle"],
        "secondary_maturity": MATURITY,
        "workflow_capabilities": ["next-interval-brief", "depth-strip", "ranking-swap", "formation-compare", "evidence-chain", "source-viewer", "prioritized-review", "simplified-rig", "offline-validation"],
        "ask_mode": "LOCAL_DETERMINISTIC_PLANNER_AND_RENDERER", "demo_mode": settings.demo_mode,
        "deferred": ["real-rig-connectivity", "risk-calibration", "independent-human-gold-signoff", "field-accuracy-validation"]}


@app.get("/api/wells/{well_id}/analogs")
def analogs(well_id: str, formation: str = "TIPAM", radius_km: float = Query(3, gt=0, le=100, allow_inf_nan=False)):
    active = require("well", well_id)
    rows = [candidate(active, w, formation, radius_km) for w in repository().all("well") if w["id"] != well_id and not w.get("held_out")]
    return sorted(rows, key=lambda r: -r["relevance"])


@app.get("/api/evidence/snapshots/{snapshot_id}")
def evidence_snapshot(snapshot_id: str):
    return require("evidence_snapshot", snapshot_id)


class TransferRequest(BaseModel):
    active_well_id: str
    event_id: str
    radius_km: float = Field(default=3, gt=0, le=100, allow_inf_nan=False)
    operation_state: Literal["DRILLING", "TRIPPING", "TRIPPING_IN", "TRIPPING_OUT", "REAMING", "CIRCULATING", "CEMENTING", "STATIC", "UNKNOWN"] = "DRILLING"


@app.post("/api/transferability/event")
def transfer_event(request: TransferRequest):
    event = require("event", request.event_id)
    doc = require("document", event["document_id"])
    if doc.get("superseded_by"): raise HTTPException(422, "Document superseded; select its current record")
    if doc.get("review_status") == "QUARANTINED" or (not doc.get("well_identity_confirmed") and any(not row["matches_associated_well"] for row in doc.get("well_identity", []))):
        raise HTTPException(422, "Document identity requires review or source is quarantined")
    active, offset = require("well", request.active_well_id), require("well", event["well_id"])
    if active["id"] == offset["id"] or offset.get("held_out"): raise HTTPException(422, "Historical analog must be a distinct non-held-out well")
    return snapshot(repository(), "transferability", {**transfer(active, offset, event, request.radius_km, request.operation_state),
                "source": require("source_span", event["source_span_id"])})


@app.get("/api/wells/{well_id}/lookahead")
def lookahead(well_id: str, formation: str = "TIPAM", risk: Literal["MUD_LOSS", "STUCK_PIPE", "KICK", "TORQUE_DYSFUNCTION", "CEMENTING_ISSUE"] = "MUD_LOSS",
              md_from_m: float = Query(2460, ge=0, le=15000, allow_inf_nan=False),
              md_to_m: float = Query(2580, ge=0, le=15000, allow_inf_nan=False),
              radius_km: float = Query(3, gt=0, le=100, allow_inf_nan=False),
              operation_state: Literal["DRILLING", "TRIPPING", "TRIPPING_IN", "TRIPPING_OUT", "REAMING", "CIRCULATING", "CEMENTING", "STATIC", "UNKNOWN"] = "DRILLING"):
    active = require("well", well_id)
    target = next((f for f in active["formations"] if f["formation_id"] == formation), None)
    if not target: raise HTTPException(422, "Target formation absent")
    if md_to_m <= md_from_m: raise HTTPException(422, "Interval must have increasing MD bounds")
    if md_from_m < target["top_md_m"] or md_to_m > (target.get("base_md_m") or target["top_md_m"]+target.get("approx_thickness_m", 0)):
        raise HTTPException(422, "Requested interval must lie within the target formation")
    return evaluate(repository(), active, formation, risk, [md_from_m, md_to_m], radius_km, operation_state)


@app.get("/api/wells")
def list_wells():
    return [{k: v for k, v in well.items() if k != "survey"} for well in repository().all("well")]


@app.get("/api/wells/{well_id}")
def get_well(well_id: str):
    return require("well", well_id)


@app.get("/api/wells/{well_id}/survey")
def get_survey(well_id: str):
    well = require("well", well_id)
    points = well_path(well)
    return {"well_id": well_id, "crs": well["crs"], "datum": well["datum"], "points": points,
        "diagnostics": {"max_dogleg_severity_deg_per_30m": max(point["dogleg_severity_deg_per_30m"] for point in points),
                        "dogleg_units": "degrees/30 m", "survey_station_count": len(points)}}


@app.get("/api/wells/{well_id}/formations")
def get_formations(well_id: str):
    return require("well", well_id)["formations"]


@app.get("/api/wells/{well_id}/events")
def get_events(well_id: str):
    require("well", well_id)
    return [event for event in repository().all("event") if event["well_id"] == well_id and not require("document", event["document_id"]).get("superseded_by")]


@app.get("/api/wells/{well_id}/coverage")
def get_coverage(well_id: str):
    require("well", well_id)
    return [item for item in repository().all("coverage") if item["well_id"] == well_id and not require("document", item["document_id"]).get("superseded_by")]


@app.get("/api/wells/{well_id}/offsets")
@app.get("/api/wells/{well_id}/offsets/at-depth")
def get_offsets(well_id: str, radius_km: float = 3, formation: str = "TIPAM"):
    if not math.isfinite(radius_km) or not 0 < radius_km <= 100: raise HTTPException(422, "Radius must be within 0–100 km")
    active = require("well", well_id)
    target = next((f for f in active["formations"] if f["formation_id"] == formation), None)
    path = well_path(active)
    rows = []
    for well in repository().all("well"):
        if well["id"] == well_id: continue
        surface = math.hypot(well["x_m"]-active["x_m"], well["y_m"]-active["y_m"])
        if surface > radius_km*1000: continue
        source = next((f for f in well["formations"] if f["formation_id"] == formation), None)
        geometry = None
        reason = None
        if source is None or target is None: reason = "formation_absent"
        elif well["crs"] != active["crs"] or well["datum"] != active["datum"]: reason = "coordinate_reference_mismatch"
        elif not source.get("base_md_m") or not target.get("base_md_m"): reason = "incomplete_formation_interval"
        else:
            try: geometry = separation(path, well_path(well), [target["top_md_m"], target["base_md_m"]], [source["top_md_m"], source["base_md_m"]],
                active.get("datum_uncertainty_m", 0)+well.get("datum_uncertainty_m", 0)+target.get("datum_uncertainty_m", 0)+source.get("datum_uncertainty_m", 0))
            except ValueError as exc: reason = str(exc)
        rows.append({"well": {k: v for k, v in well.items() if k != "survey"}, "surface_distance_km": round(surface/1000, 4),
            "target_distance_km": geometry["target_distance_m"]/1000 if geometry else None, "geometry": geometry,
            "reason": reason, "formation": formation, "provenance_type": "COMPUTED"})
    return sorted(rows, key=lambda row: row["target_distance_km"] if row["target_distance_km"] is not None else float("inf"))


class ProjectionRequest(BaseModel):
    active_well_id: str
    event_id: str


@app.post("/api/alignment/project-event")
def project(request: ProjectionRequest):
    event = require("event", request.event_id)
    if event["md_from_m"] is None: raise HTTPException(422, "Event requires a confirmed MD depth")
    active = require("well", request.active_well_id); offset = require("well", event["well_id"])
    source = next((f for f in offset["formations"] if f["formation_id"] == event["formation_id"]), None)
    target = next((f for f in active["formations"] if f["formation_id"] == event["formation_id"]), None)
    if source is None: return {"decision": "BLOCKED", "reason": "source_formation_unknown", "projected_md_interval_m": None}
    if event.get("datum") != source.get("datum"):
        return {"decision": "BLOCKED", "reason": "event_datum_unknown_or_mismatched", "projected_md_interval_m": None}
    try: result = project_event(event, source, target, well_path(offset), well_path(active))
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    result.update({"id": f"ALIGN-{request.active_well_id}-{request.event_id}", "event_id": event["id"],
        "active_well_id": active["id"], "formation": event["formation_id"], "source_span_id": event["source_span_id"],
        "provenance_type": "COMPUTED", "computed_at": datetime.now(timezone.utc).isoformat()})
    repository().put("alignment", result)
    return result


@app.get("/api/documents")
def list_documents():
    return [public_document(doc) for doc in repository().all("document") if not doc.get("superseded_by")]


@app.get("/api/gazetteer")
def gazetteer():
    return {"version": GAZETTEER_VERSION, "basin": "ASSAM_ARAKAN", "entries": ENTRIES}


@app.post("/api/documents/ingest")
def upload(file: UploadFile = File(...), well_id: str = Form(...), synthetic: bool = Form(False),
           classification: Literal["PUBLIC", "PRIVATE"] = Form("PRIVATE"),
           doc_type: Literal["AUTO", "DDR", "WCR", "MUD_LOG", "CEMENT_REPORT"] = Form("AUTO")):
    content = file.file.read(20*1024*1024+1)
    try: return public_document(ingest(repository(), content, file.filename or "upload.pdf", well_id, synthetic,
        classification=classification, doc_type=None if doc_type == "AUTO" else doc_type))
    except Exception as exc:
        if isinstance(exc, ValueError): raise HTTPException(422, str(exc)) from exc
        raise HTTPException(422, "Document could not be parsed. Upload an unlocked PDF or UTF-8 text file.") from exc


@app.get("/api/documents/{document_id}")
def document_detail(document_id: str):
    return public_document(require("document", document_id))


@app.get("/api/documents/{document_id}/events")
def document_events(document_id: str):
    doc = require("document", document_id)
    return [{**require("event", key), "source": require("source_span", require("event", key)["source_span_id"])} for key in doc["event_ids"]]


@app.get("/api/documents/{document_id}/source")
def document_source(document_id: str):
    doc = require("document", document_id)
    return FileResponse(source_path(doc), filename=doc["title"])


@app.get("/api/documents/{document_id}/pages/{page_number}")
def page_source(document_id: str, page_number: int):
    doc = require("document", document_id)
    if not 1 <= page_number <= doc["pages"]: raise HTTPException(404, "Page not found")
    return doc["page_data"][page_number-1]


@app.get("/api/documents/{document_id}/pages/{page_number}/image")
def page_image(document_id: str, page_number: int):
    doc = require("document", document_id)
    if not doc["path"].endswith(".pdf"): raise HTTPException(422, "Text documents have no rendered PDF page")
    if not 1 <= page_number <= doc["pages"]: raise HTTPException(404, "Page not found")
    import fitz
    with fitz.open(source_path(doc)) as pdf:
        image = pdf[page_number-1].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        return Response(image.tobytes("png"), media_type="image/png")


@app.get("/api/review")
def review_queue(session_id: str | None = None):
    result = []
    for item in repository().all("review"):
        if item["status"] != "PENDING": continue
        if require("document", item["document_id"]).get("superseded_by"): continue
        record = require(item["kind"], item["entity_id"])
        result.append({**item, "record": record,
            "source": require("source_span", record["source_span_id"]) if item["kind"] == "event" else None})
    if session_id:
        session = require("live_session", session_id)
        active = require("well", session["well_id"])
        for task in result:
            record = task["record"]
            doc = require("document", task["document_id"])
            source = require("well", doc["well_id"])
            analog = candidate(active, source, session["formation"], session["radius_km"])
            task["affects_active_lookahead"] = analog["surface_distance_km"] <= session["radius_km"] and record.get("formation_id", session["formation"]) in (None, session["formation"]) and "formation_absent" not in analog["blockers"]
            task["impact_reason"] = "Potential active-formation evidence; resolve source ambiguity" if task["affects_active_lookahead"] else "Outside current look-ahead context"
        result.sort(key=lambda task: (not task["affects_active_lookahead"], {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[task["priority"]], task["id"]))
    return result


class ReviewRequest(BaseModel):
    reviewer: str = Field(min_length=1, max_length=120)
    action: Literal["accept", "correct", "quarantine"] = "accept"
    md_from_m: float | None = Field(default=None, ge=0, le=15000)
    md_to_m: float | None = Field(default=None, ge=0, le=15000)
    severity: Literal["UNKNOWN", "MINOR", "PARTIAL", "MODERATE", "SEVERE", "TOTAL"] | None = None
    formation_id: str | None = None
    doc_type: Literal["DDR", "WCR", "MUD_LOG", "CEMENT_REPORT", "UNKNOWN"] | None = None
    classification: Literal["PUBLIC", "PRIVATE"] | None = None
    confirm_well_identity: bool = False
    date_from: date | None = None
    date_to: date | None = None
    depth_value: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    depth_unit: Literal["m", "ft"] | None = None


@app.post("/api/review/{review_id}")
def review(review_id: str, request: ReviewRequest):
    store = repository(); task = require("review", review_id)
    item = require(task["kind"], task["entity_id"])
    before = dict(item)
    if task["kind"] == "event":
        if request.action == "correct":
            if request.depth_value is not None:
                if not request.depth_unit: raise HTTPException(422, "Depth correction requires original units")
                from .domain.units import normalize
                corrected = normalize(request.depth_value, request.depth_unit, "depth", item["datum"], "MD", "HUMAN_REVIEWED")
                if corrected.value > 15000: raise HTTPException(422, "Corrected depth exceeds physical range")
                if request.md_from_m is not None and abs(request.md_from_m-corrected.value) > .001: raise HTTPException(422, "Metres and original-unit corrections conflict")
                item["md_from_m"] = corrected.value
                item["reviewed_depth_measurement"] = corrected.model_dump()
            if request.md_from_m is not None: item["md_from_m"] = request.md_from_m
            if request.severity is not None: item["severity"] = request.severity
            if "md_to_m" in request.model_fields_set:
                item["md_to_m"] = request.md_to_m
                if request.md_to_m is None: item["event_md_interval_m"] = None
            if item.get("md_to_m") is not None:
                if item["md_from_m"] is None or item["md_to_m"] < item["md_from_m"]:
                    raise HTTPException(422, "Event interval end must be at or below its start depth")
                item["event_md_interval_m"] = [item["md_from_m"], item["md_to_m"]]
            if request.formation_id is not None:
                if request.formation_id not in {entry["id"] for entry in ENTRIES}:
                    raise HTTPException(422, "Unknown gazetteer formation")
                item["formation_id"] = request.formation_id
            item["correction_kind"] = "HUMAN_REVIEWED"
        if request.action != "quarantine" and (item["md_from_m"] is None or item["formation_id"] is None):
            raise HTTPException(422, "Confirm MD depth and formation before accepting")
        item["review_status"] = "QUARANTINED" if request.action == "quarantine" else "VERIFIED"
    elif task["kind"] == "coverage":
        if request.action == "correct":
            if request.date_from: item["date_from"] = request.date_from.isoformat()
            if request.date_to: item["date_to"] = request.date_to.isoformat()
            if not item.get("date_from") or not item.get("date_to") or item["date_from"] > item["date_to"]:
                raise HTTPException(422, "Date coverage requires valid increasing date bounds")
        item["coverage_status"] = "UNKNOWN" if request.action == "quarantine" else "VERIFIED"
        if not item.get("md_interval"): item["coverage_status"] = "UNKNOWN"
        item["date_coverage_status"] = "VERIFIED" if request.action != "quarantine" and item.get("date_from") and item.get("date_to") else "UNKNOWN"
        if item["date_coverage_status"] == "VERIFIED": item["date_reviewer"] = request.reviewer
    else:
        if request.action != "quarantine" and any(not identity["matches_associated_well"] for identity in item.get("well_identity", [])) and not request.confirm_well_identity:
            raise HTTPException(422, "Explicitly confirm the document belongs to the associated well")
        if request.doc_type: item["doc_type"] = request.doc_type; item["doc_type_source"] = "DECLARED"
        if request.classification:
            if request.classification == "PUBLIC" and any(re.search(r"\b(?:PRIVATE|CONFIDENTIAL|RESTRICTED)\b", page["text"], re.I) for page in item["page_data"]):
                raise HTTPException(422, "Private source markings prevent public classification")
            item["classification"] = request.classification
        item["well_identity_confirmed"] = request.confirm_well_identity
        item["review_status"] = "QUARANTINED" if request.action == "quarantine" else "VERIFIED"
    item["reviewer"] = request.reviewer
    store.put(task["kind"], item)
    task["status"] = "RESOLVED"; store.put("review", task)
    stamp = datetime.now(timezone.utc).isoformat()
    store.put("audit", {"id": f"AUDIT-{stamp}", "timestamp": stamp, "reviewer": request.reviewer,
        "action": request.action, "entity_id": item["id"], "before": before, "after": item})
    doc = require("document", task["document_id"])
    if task["kind"] == "coverage" and doc.get("date_coverage") and item["page"] == doc["date_coverage"]["source"]["page"]:
        doc["date_coverage"]["status"] = item["date_coverage_status"]
        doc["date_coverage"]["date_from"], doc["date_coverage"]["date_to"] = item["date_from"], item["date_to"]
        for interval in doc.get("date_coverages", []):
            if interval["source"]["page"] == item["page"]:
                interval["status"] = item["date_coverage_status"]
                interval["date_from"], interval["date_to"] = item["date_from"], item["date_to"]
    pending = any(row["status"] == "PENDING" and row["document_id"] == doc["id"] for row in store.all("review"))
    quarantined = any(require("event", key)["review_status"] == "QUARANTINED" for key in doc["event_ids"])
    doc["review_status"] = "NEEDS_REVIEW" if pending else "QUARANTINED" if quarantined or doc.get("review_status") == "QUARANTINED" else "VERIFIED"
    store.put("document", doc)
    return item


# v1 is the stable public prefix. Legacy /api routes remain compatibility aliases.
from fastapi.routing import APIRoute
from .live_routes import stream as replay_stream
app.add_api_websocket_route("/api/v1/replay/sessions/{session_id}/stream", replay_stream)
for route in list(app.routes):
    if isinstance(route, APIRoute) and route.path.startswith("/api/"):
        app.add_api_route(route.path.replace("/api/", "/api/v1/", 1), route.endpoint,
                          methods=list(route.methods), response_model=route.response_model,
                          name="v1_"+route.name)

if settings.serve_frontend:
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[2]/"frontend/dist", html=True), name="dashboard")
