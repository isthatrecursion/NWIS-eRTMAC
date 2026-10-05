"""Offline-only blind benchmark: freeze predictions before opening truth."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from .store import Store, repository
from .generator import build_field
from .replay_demo import install_demo
from .live import ReplayAdapter
from .mud_loss import assess, sync_alert, VERSION as MUD_VERSION
from .evidence import VERSION as EVIDENCE_VERSION, active_records
from .paths import DATA_ROOT

VERSION = "blind-synthetic-benchmark/1.0"
METHODS = ("nwis_warning", "surface_nearest", "same_formation_equal", "fixed_similarity", "keyword_document")


def digest(value): return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def prepare(root):
    """Author a deterministic challenge fixture, not a calibrated field population."""
    runtime, hidden = root/"runtime", root/"evaluation"
    runtime.mkdir(parents=True, exist_ok=True); hidden.mkdir(parents=True, exist_ok=True)
    setup = Store("sqlite+pysqlite:///:memory:")
    field, _ = build_field()
    for well in field["wells"]: setup.put("well", well)
    active, dataset = install_demo(setup)
    cases, truth = [], []
    variants = ("loss", "loss", "negative", "transient", "sensor_fault", "similar_signals_negative", "loss_stale", "quiet_negative")
    for index, variant in enumerate(variants):
        well = deepcopy(active)
        well.update(id=f"SYN-BLIND-{index+1:02}", name=f"Synthetic blind well {index+1}", held_out=True, x_m=active["x_m"]+index*10)
        frames = deepcopy(dataset["frames"])
        for cursor, frame in enumerate(frames):
            values = frame["values"]
            if variant in ("negative", "quiet_negative"):
                values.update(flow_out_l_min=945, pit_volume_m3=410)
            if variant == "transient":
                values.update(flow_out_l_min=870 if cursor == 9 else 945, pit_volume_m3=409 if cursor == 9 else 410)
            if variant in ("sensor_fault", "loss_stale") and cursor >= 7:
                frame["quality_overrides"] = {"flow_out_l_min": "STALE"}
        cases.append({"id": well["id"], "well": well, "frames": frames, "monitoring_md_interval_m": [2460,2520]})
        truth.append({"well_id": well["id"], "events": [{"md_interval_m": [2490,2500], "severity": "SEVERE"}] if variant in ("loss", "loss_stale") else [], "case_kind": variant})
    (runtime/"blind_cases.json").write_text(json.dumps({"version": VERSION, "cases": cases}, indent=2), encoding="utf-8")
    (hidden/"blind_truth.json").write_text(json.dumps({"version": VERSION, "truth": truth}, indent=2), encoding="utf-8")
    # Offset documents remain separate from both runtime cases and hidden labels.
    return setup


def overlap(a, b):
    intersection = max(0, min(a[1],b[1])-max(a[0],b[0]))
    union = max(a[1],b[1])-min(a[0],b[0])
    return intersection/union if union else 0


def fixed_similarity(active, offset):
    a, b = active["mud_program"], offset["mud_program"]
    return (.4*any(f["formation_id"] == "TIPAM" for f in offset["formations"])
        + .25*(a.get("hole_section_in") is not None and a.get("hole_section_in") == b.get("hole_section_in"))
        + .2*(a.get("mud_system") is not None and a.get("mud_system") == b.get("mud_system"))
        + .15*(a.get("ecd_sg") is not None and b.get("ecd_sg") is not None and abs(a["ecd_sg"]-b["ecd_sg"]) <= .05))


def metrics(predictions, truth, drilled_m):
    alerts = [a for row in predictions for a in row["alerts"]]
    hits, severe_hits, total, severe, leads, ious, false = 0,0,0,0,[],[],0
    for row in predictions:
        expected = next(t["events"] for t in truth if t["well_id"] == row["well_id"])
        total += len(expected); severe += sum(e["severity"] in ("SEVERE", "TOTAL") for e in expected)
        matched = set()
        for alert in sorted(row["alerts"], key=lambda a:a["bit_md_m"]):
            selected = next((i for i,e in enumerate(expected) if i not in matched and alert["bit_md_m"] <= e["md_interval_m"][1] and overlap(alert["window"], e["md_interval_m"]) > 0), None)
            if selected is None: false += 1; continue
            matched.add(selected);hits += 1
            event = expected[selected]
            severe_hits += event["severity"] in ("SEVERE", "TOTAL")
            leads.append(event["md_interval_m"][0]-alert["bit_md_m"])
            ious.append(overlap(alert["window"], event["md_interval_m"]))
    return {"alert_count": len(alerts), "hits": hits, "misses": total-hits, "false_negatives": total-hits, "false_alerts": false,
            "alert_precision": hits/len(alerts) if alerts else None, "severe_event_recall": severe_hits/severe if severe else None,
            "lead_distance_m": leads, "alerts_per_1000_m": len(alerts)*1000/drilled_m if drilled_m else None,
            "projected_interval_overlap_iou": sum(ious)/len(ious) if ious else None, "expected_event_count": total}


def predict(store, cases):
    predictions, visual, sufficient, samples = {m: [] for m in METHODS}, [], 0, 0
    events = [e for e in active_records(store, "event") if e["event_type"] == "MUD_LOSS" and e["review_status"] == "VERIFIED" and not store.get("well", e["well_id"]).get("held_out")]
    docs = [d for d in store.all("document") if not store.get("well", d["well_id"]).get("held_out")]
    for case in cases:
        well, frames = case["well"], case["frames"]
        store.put("well", well)
        session = {"id": "EVAL-"+well["id"], "well_id": well["id"], "formation": "TIPAM", "md_interval_m": case["monitoring_md_interval_m"], "radius_km": 3, "adapter": "REPLAY", "simulation": True}
        rows = {m: [] for m in METHODS}
        nearest_ids = {e["well_id"] for e in sorted(events, key=lambda e:math.hypot(store.get("well", e["well_id"])["x_m"]-well["x_m"],store.get("well", e["well_id"])["y_m"]-well["y_m"]))[:2]}
        fixed_weights = {w["id"]:fixed_similarity(well,w) for w in store.all("well") if not w.get("held_out")}
        for cursor, frame in enumerate(frames):
            replay = {"cursor": cursor, "epoch": "2026-01-15T00:00:00+00:00", "failures": frame.get("quality_overrides", {})}
            context = ReplayAdapter(well, frames, replay).context_at()
            assessment = assess(store, well, session, context)
            alert = sync_alert(store, session, assessment)
            historical, live = assessment["historical"], assessment["corroboration"]
            depth = context["bit_md_m"]
            samples += 1; sufficient += historical["state"] == "ELEVATED"
            source_windows = [t["projection"]["projected_md_interval_m"] for row in historical["rows"] if row["role"] == "SUPPORT" for t in row["transfers"] if t["event_id"] == row["selected_event_id"]]
            near = next((w for w in source_windows if w[0]-100 <= depth <= w[1]), None)
            if live["warning_allowed"] and not rows["nwis_warning"]:
                rows["nwis_warning"].append({"bit_md_m": depth, "window": source_windows[0], "alert_id": alert["id"], "evidence_snapshot_id": historical["id"]})
            equal = historical["support_count"]/(historical["support_count"]+historical["counter_count"]) if historical["support_count"]+historical["counter_count"] else 0
            fixed_total = sum(fixed_weights.get(row["well_id"],0) for row in historical["rows"] if row["role"] in ("SUPPORT","COUNTER"))
            fixed = sum(fixed_weights.get(row["well_id"],0) for row in historical["rows"] if row["role"] == "SUPPORT")/fixed_total if fixed_total else 0
            for method, enabled in (("same_formation_equal", equal >= .5), ("fixed_similarity", fixed >= .45)):
                if enabled and near and not rows[method]: rows[method].append({"bit_md_m": depth, "window": near})
            raw = next(([e["md_from_m"]-50,e["md_from_m"]+50] for e in events if e["well_id"] in nearest_ids and e.get("md_from_m") is not None and e["md_from_m"]-150 <= depth <= e["md_from_m"]+50), None)
            if raw and not rows["surface_nearest"]: rows["surface_nearest"].append({"bit_md_m": depth, "window": raw})
            if any("mud loss" in p["text"].lower() for d in docs for p in d["page_data"]) and 2200-100 <= depth <= 2580 and not rows["keyword_document"]:
                rows["keyword_document"].append({"bit_md_m": depth, "window": [2200,2580]})
            if case == cases[0]: visual.append({"bit_md_m": depth, "timestamp": context["timestamp"], "state": live["state"], "historical_state": historical["state"], "flow_quality": context["channels"]["flow_out_l_min"]["quality_status"], "warning_allowed": live["warning_allowed"], "evidence_snapshot_id": historical["id"]})
        for method in METHODS: predictions[method].append({"well_id": well["id"], "alerts": rows[method]})
    return predictions, visual, sufficient/samples if samples else None


def run(root=DATA_ROOT/"benchmark", publish_store=None):
    store = prepare(root)
    cases = json.loads((root/"runtime/blind_cases.json").read_text(encoding="utf-8"))["cases"]
    predictions, visual, sufficiency = predict(store, cases)
    frozen_hash = digest(predictions)
    # Persist the complete pre-reveal artifact before reading any hidden truth.
    (root/"evaluation/frozen_predictions.json").write_text(json.dumps(predictions, indent=2), encoding="utf-8")
    truth = json.loads((root/"evaluation/blind_truth.json").read_text(encoding="utf-8"))["truth"]
    drilled_m = sum(c["frames"][-1]["values"]["bit_md_m"]-c["frames"][0]["values"]["bit_md_m"] for c in cases)
    result = {"id": "BENCHMARK-"+frozen_hash[:20], "version": VERSION, "generated_at": datetime.now(timezone.utc).isoformat(), "synthetic_flag": True,
        "case_count": len(cases), "positive_cases": sum(bool(t["events"]) for t in truth), "negative_cases": sum(not t["events"] for t in truth),
        "drilled_m": drilled_m, "prediction_sha256": frozen_hash, "truth_sha256": digest(truth), "predictions_frozen_before_reveal": True,
        "metrics": {m: metrics(rows, truth, drilled_m) for m,rows in predictions.items()}, "evidence_sufficiency_fraction": sufficiency,
        "source_coverage": {"verified_offset_documents": len(store.all("document")), "offset_wells": 4}, "visual_case": {"well_id": cases[0]["id"], "trace": visual, "revealed_truth": truth[0]["events"]},
        "rules": {"mud_loss": MUD_VERSION, "evidence": EVIDENCE_VERSION, "baselines": {"surface_nearest": "Nearest reviewed event wells, raw MD +/-50 m, 100 m approach", "same_formation_equal": "Support fraction >=0.5, projected window within 100 m", "fixed_similarity": "Static formation/hole/mud/ECD feature weights 0.4/0.25/0.2/0.15; weighted support fraction >=0.45, projected window within 100 m", "keyword_document": "Literal mud-loss passage match; coverage interval, ignores negation"}},
        "limitations": ["Authored synthetic challenge cases, not independent field validation", "Shared offset history and trajectories limit generalization", "Baselines emit historical advisories; NWIS scoring counts corroborated Warnings", "No secondary-risk predictor accuracy is claimed", "Missing/stale sensors can create false negatives by design"]}
    (publish_store or repository()).put("benchmark_report", result)
    (root/"evaluation/results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    result = run()
    print(json.dumps({"id": result["id"], "metrics": result["metrics"]}, indent=2))
