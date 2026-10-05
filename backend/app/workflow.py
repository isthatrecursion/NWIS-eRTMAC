"""Field/office integration. Runtime never reads held-out truth."""
from fastapi import APIRouter, HTTPException, Query
from .store import repository
from .live_routes import require, context_for, evaluate_session, LOCK
from .secondary import module, MATURITY
from .evidence import evaluate, active_records, candidate, clean_evidence
from .geometry import trajectory, separation
from .domain.runtime import SecondaryModule

router = APIRouter(prefix="/api")


@router.get("/replay/sessions/{session_id}/secondary")
def secondary_modules(session_id: str):
    with LOCK:
        session = require("live_session", session_id)
        context = context_for(session)
        well = require("well", session["well_id"])
        return {"session_id": session_id, "timestamp": context["timestamp"], "modules": [SecondaryModule.model_validate(module(repository(), well, session, context, risk)).model_dump(mode="json") for risk in MATURITY if risk != "MUD_LOSS"]}


@router.get("/replay/sessions/{session_id}/brief")
def brief(session_id: str):
    with LOCK:
        store = repository()
        session = require("live_session", session_id)
        live = evaluate_session(session)
        well = require("well", session["well_id"])
        context = live["context"]
        windows, summaries = [], []
        for formation in well["formations"]:
            if formation.get("base_md_m") is None or (context["bit_md_m"] is not None and formation["base_md_m"] < context["bit_md_m"]): continue
            if formation["formation_id"] not in {context["formation_id"], context["next_formation_id"], session["formation"]}: continue
            for risk in MATURITY:
                history = evaluate(store, well, formation["formation_id"], risk, [formation["top_md_m"], formation["base_md_m"]], session["radius_km"], "CEMENTING" if risk == "CEMENTING_ISSUE" else context["operation_state"])
                summaries.append({"risk_type": risk, "formation_id": formation["formation_id"], "state": history["state"], "sentence": history["sentence"], "support_count": history["support_count"], "counter_count": history["counter_count"], "unknown_count": history["unknown_count"], "evidence_snapshot_id": history["id"], "maturity": MATURITY[risk]})
                for row in history["rows"]:
                    for transfer in row["transfers"]:
                        bounds = (transfer.get("projection") or {}).get("projected_md_interval_m")
                        if transfer["decision"] != "INCLUDED" or not bounds or context["bit_md_m"] is not None and bounds[1] < context["bit_md_m"]: continue
                        windows.append({"risk_type": risk, "formation_id": formation["formation_id"], "md_interval_m": bounds,
                            "event_id": transfer["event_id"], "well_id": row["well_id"], "state": history["state"],
                            "distance_ahead_m": max(0, bounds[0]-context["bit_md_m"]) if context["bit_md_m"] is not None else None,
                            "evidence_snapshot_id": history["id"], "maturity": MATURITY[risk], "provenance_type": "INFERRED"})
        windows.sort(key=lambda row: row["distance_ahead_m"] if row["distance_ahead_m"] is not None else float("inf"))
        return {"session_id": session_id, "timestamp": context["timestamp"], "well": well, "context": context, "live": live,
                "risk_windows": windows, "risk_summaries": summaries, "formations": well["formations"], "casing_points": well["casing_program"],
                "active_alerts": [a for a in store.all("alert") if a["well_id"] == well["id"] and a["lifecycle"] != "RESOLVED"],
                "maturity": MATURITY, "simulation": True}


@router.get("/evidence/chain/{snapshot_id}/{event_id}")
def evidence_chain(snapshot_id: str, event_id: str):
    evidence = require("evidence_snapshot", snapshot_id)
    transfer = next((t for row in evidence["rows"] for t in row["transfers"] if t["event_id"] == event_id), None)
    if transfer is None: raise HTTPException(404, "Event is not part of this evidence snapshot")
    event = transfer["inputs"]["event"]
    span = transfer.get("source") or require("source_span", event["source_span_id"])
    doc = require("document", event["document_id"])
    page = doc["page_data"][span["page"]-1]
    return {"alerts": [{"id": a["id"], "state": a["evidence_state"]} for a in repository().all("alert") if a["evidence_snapshot_id"] == snapshot_id],
            "evidence": {"record": evidence, "provenance_type": "INFERRED"},
            "transfer": {"record": transfer, "provenance_type": "INFERRED"},
            "alignment": {"record": transfer["projection"], "provenance_type": "COMPUTED"},
            "event": {"record": event, "provenance_type": "FACT"}, "span": {"record": span, "provenance_type": "FACT"},
            "document": {"id": doc["id"], "title": doc["title"], "page": span["page"], "review_status": doc["review_status"], "classification": doc.get("classification", "PRIVATE"), "page_record": page, "provenance_type": "FACT"}}


@router.get("/wells/{well_id}/compare")
def compare(well_id: str, formation: str = "TIPAM", radius_km: float = Query(3, gt=0, le=100, allow_inf_nan=False)):
    store = repository()
    active = require("well", well_id)
    target = next((f for f in active["formations"] if f["formation_id"] == formation), None)
    if not target or target.get("base_md_m") is None: raise HTTPException(422, "A complete target formation is required")
    result = []
    for well in store.all("well"):
        assessment = candidate(active, well, formation, radius_km)
        if well["id"] != well_id and (well.get("held_out") or assessment["surface_distance_km"] > radius_km): continue
        interval = next((f for f in well["formations"] if f["formation_id"] == formation), None)
        if not interval or interval.get("base_md_m") is None: continue
        thickness = interval["base_md_m"]-interval["top_md_m"]
        events = [{"event_id": e["id"], "risk_type": e["event_type"], "formation_fraction": (e["md_from_m"]-interval["top_md_m"])/thickness,
                   "md_m": e["md_from_m"], "document_id": e["document_id"], "review_status": e["review_status"]} for e in active_records(store, "event") if e["well_id"] == well["id"] and e.get("formation_id") == formation and e.get("md_from_m") is not None]
        clean = [{"id": c["id"], "from_fraction": (c["md_interval"][0]-interval["top_md_m"])/thickness, "to_fraction": (c["md_interval"][1]-interval["top_md_m"])/thickness, "document_id": c["document_id"], "label": "VERIFIED COVERAGE; inspect explicit risk negation"} for c in active_records(store, "coverage") if c["well_id"] == well["id"] and c["coverage_status"] == "VERIFIED" and c.get("md_interval")]
        crossings = []
        # Evaluate actual covered intersections; full-formation uncertainty envelopes
        # often exceed the available report interval. Never equate coverage with clean.
        for coverage in active_records(store, "coverage"):
            bounds = coverage.get("md_interval")
            if coverage["well_id"] != well["id"] or not bounds or coverage["coverage_status"] != "VERIFIED": continue
            margin = 4*interval["uncertainty_m"]+1
            lo, hi = max(bounds[0], interval["top_md_m"])+margin, min(bounds[1], interval["base_md_m"])-margin
            if lo >= hi: continue
            for risk in MATURITY:
                if any(e["risk_type"] == risk for e in events): continue
                source = clean_evidence(store, well, well, formation, risk, [lo, hi], radius_km, "CEMENTING" if risk == "CEMENTING_ISSUE" else "DRILLING")
                if source: crossings.append({"risk_type": risk, "from_fraction": (lo-interval["top_md_m"])/thickness, "to_fraction": (hi-interval["top_md_m"])/thickness, "source": source, "provenance_type": "INFERRED"})
        result.append({"well_id": well["id"], "is_active": well["id"] == well_id, "formation": interval, "events": events, "verified_coverage": clean,
                       "clean_crossings": crossings,
                       "mud_context": well["mud_program"], "casing_program": well["casing_program"], "relevance": assessment, "provenance_type": "COMPUTED"})
    return {"formation": formation, "alignment": "normalized formation fraction (top=0, base=1)", "wells": result}


@router.get("/wells/{well_id}/ranking-swap")
def ranking_swap(well_id: str, formation: str = "TIPAM", radius_km: float = Query(3, gt=0, le=100, allow_inf_nan=False)):
    active = require("well", well_id)
    target = next((f for f in active["formations"] if f["formation_id"] == formation), None)
    if not target or target.get("base_md_m") is None: raise HTTPException(422, "Complete formation required")
    rows = []
    for well in repository().all("well"):
        if well["id"] == well_id or well.get("held_out"): continue
        assessment = candidate(active, well, formation, radius_km)
        interval = next((f for f in well["formations"] if f["formation_id"] == formation), None)
        if assessment["surface_distance_km"] > radius_km or not interval or not interval.get("base_md_m") or well["datum"] != active["datum"] or well["crs"] != active["crs"]: continue
        try: geometry = separation(trajectory(active["survey"], active["x_m"], active["y_m"]), trajectory(well["survey"], well["x_m"], well["y_m"]), [target["top_md_m"], target["base_md_m"]], [interval["top_md_m"], interval["base_md_m"]])
        except ValueError: continue
        if not geometry: continue
        rows.append({"well_id": well["id"], "surface_distance_km": assessment["surface_distance_km"], "target_distance_km": geometry["target_distance_m"]/1000, "relevance": assessment["relevance"], "decision": assessment["decision"]})
    by_surface = sorted(rows, key=lambda r: r["surface_distance_km"])
    by_depth = sorted(rows, key=lambda r: r["target_distance_km"])
    for row in rows:
        row["surface_rank"] = by_surface.index(row)+1
        row["target_rank"] = by_depth.index(row)+1
    pair = next(([a, b] for a in by_surface for b in by_surface if a["surface_rank"] < b["surface_rank"] and a["target_rank"] > b["target_rank"]), None)
    return {"rows": by_surface, "swap": pair, "provenance_type": "COMPUTED", "explanation": "A nearer surface well can be farther away at the target formation because trajectories diverge"}


@router.get("/validation/results")
def validation_results():
    # Only published aggregate evaluation output is served. Truth is offline-only.
    reports = sorted(repository().all("validation_report"), key=lambda row: row["generated_at"], reverse=True)
    return {"status": "AVAILABLE" if reports else "NOT_RUN", "reports": reports,
            "scope": "Held-out synthetic replay evaluation; not measured field accuracy", "offline_command": "python -m app.validate_replay"}


@router.get("/validation/hardening")
def hardening_reports():
    return {kind: sorted(repository().all(kind), key=lambda row:row["generated_at"], reverse=True)[:3] for kind in ("benchmark_report", "extraction_report", "engineering_report", "safety_report")}
