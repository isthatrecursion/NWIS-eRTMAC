"""Offline held-out scoring. Only aggregate results are published to the runtime store."""
import hashlib
import json
from datetime import datetime, timezone
from copy import deepcopy
from .paths import DATA_ROOT
from .store import repository
from .live import parse_csv, ReplayAdapter
from .evidence import active_records, evaluate
from .mud_loss import corroborate
from .config import get_settings

VERSION = "held-out-replay-evaluation/1.0"


def score(alerts, expected, frames):
    matched = []
    for interval in expected:
        before = [a for a in alerts if a["bit_md_m"] <= interval[1] and a["window"][0] <= interval[1] and a["window"][1] >= interval[0]]
        if before: matched.append(interval[0]-min(a["bit_md_m"] for a in before))
    false = sum(not any(a["window"][0] <= b and a["window"][1] >= a0 for a0, b in expected) for a in alerts)
    return {"alert_count": len(alerts), "hits": len(matched), "misses": len(expected)-len(matched),
            "false_alerts": false, "lead_distance_m": matched, "evaluated_frames": len(frames),
            "negative_case_count": 0, "specificity": None, "accuracy": None}


def run(store, root=DATA_ROOT):
    metadata = json.loads((root/"evaluation/generator_metadata.json").read_text())
    held = json.loads((root/"evaluation/held_out_events.json").read_text())
    intervals = json.loads((root/"evaluation/expected_intervals.json").read_text())
    frames = parse_csv((root/"runtime/replay.csv").read_bytes())
    results = []
    for well_id in metadata["held_out_well_ids"]:
        active = store.get("well", well_id)
        if active is None: continue
        formation = next(f for f in active["formations"] if f["formation_id"] == "TIPAM")
        source_events = [e for e in active_records(store, "event") if e["event_type"] == "MUD_LOSS" and e["well_id"] != well_id and not store.get("well", e["well_id"]).get("held_out") and e["review_status"] == "VERIFIED" and e.get("md_from_m") is not None]
        radius_events = [e for e in source_events if ((store.get("well", e["well_id"])["x_m"]-active["x_m"])**2+(store.get("well", e["well_id"])["y_m"]-active["y_m"])**2)**.5 <= 3000]
        expected_ids = {e["id"] for e in held if e["well_id"] == well_id and e["event_type"] == "MUD_LOSS"}
        expected = [i["md_interval_m"] for i in intervals if i["event_id"] in expected_ids]
        alerts = {"radius_only": [], "raw_depth": [], "formation_evidence": [], "mud_loss_slice": []}
        coverage, cache = set(), {}
        monitoring = [max(formation["top_md_m"], 2460), min(formation["base_md_m"], 2580)]
        for cursor, frame in enumerate(frames):
            context = ReplayAdapter(active, frames, {"cursor": cursor, "epoch": "2026-01-15T00:00:00+00:00", "failures": {}}).context_at()
            observed = deepcopy(active)
            observed["mud_program"]["ecd_sg"] = context["channels"]["ecd_sg"]["value"]
            key = (observed["mud_program"]["ecd_sg"], context["operation_state"])
            if key not in cache: cache[key] = evaluate(store, observed, "TIPAM", "MUD_LOSS", monitoring, 3, context["operation_state"])
            evidence = cache[key]
            coverage.update(r["well_id"] for r in evidence["rows"] if r["role"] in ("SUPPORT", "COUNTER"))
            depth = frame["values"]["bit_md_m"]
            if radius_events and not alerts["radius_only"]: alerts["radius_only"].append({"bit_md_m": depth, "window": monitoring})
            for e in radius_events:
                window = [e["md_from_m"]-50, e["md_from_m"]+50]
                if window[0]-100 <= depth <= window[1] and not alerts["raw_depth"]: alerts["raw_depth"].append({"bit_md_m": depth, "window": window})
            projected = [t["projection"]["projected_md_interval_m"] for row in evidence["rows"] if row["role"] == "SUPPORT" for t in row["transfers"] if t["event_id"] == row["selected_event_id"]]
            near = next((window for window in projected if window[0]-100 <= depth <= window[1]), None)
            if near and not alerts["formation_evidence"]: alerts["formation_evidence"].append({"bit_md_m": depth, "window": near})
            if near and corroborate(context, evidence)["warning_allowed"] and not alerts["mud_loss_slice"]:
                alerts["mud_loss_slice"].append({"bit_md_m": depth, "window": near})
        results.append({"well_id": well_id, "risk": "MUD_LOSS", "expected_event_count": len(expected), "evidence_coverage_wells": len(coverage),
                        "source_status": "Usable support/counter evidence found" if coverage else "No usable reviewed historical evidence; missing support is scored as a miss",
                        "baselines": {name: score(rows, expected, frames) for name, rows in alerts.items()}})
    payload = {"version": VERSION, "generated_at": datetime.now(timezone.utc).isoformat(), "results": results,
               "synthetic_flag": True, "generator_version": metadata["version"], "seed": metadata["seed"],
               "input_sha256": hashlib.sha256((root/"runtime/replay.csv").read_bytes()+(root/"evaluation/held_out_events.json").read_bytes()).hexdigest(),
               "repository_sha256": hashlib.sha256(json.dumps({kind: store.all(kind) for kind in ("well", "event", "coverage", "document")}, sort_keys=True).encode()).hexdigest(),
               "policies": {"mud_loss": get_settings().mud_loss_policy.model_dump(), "historical": get_settings().historical_policy.model_dump()},
               "limitations": ["Tiny synthetic held-out population; no operational accuracy claim", "No independent negative cases: specificity and accuracy unavailable", "Scores reflect the repository review state at evaluation time", "Only mud loss is scored as a live vertical slice; secondary modules are partial", "A hit requires an overlapping projected window and alert before the expected interval end", "Baseline alerts are simulated advisories, not rig alarms"]}
    payload["id"] = "VALIDATION-"+hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:20]
    store.put("validation_report", payload)
    return payload


if __name__ == "__main__":
    report = run(repository())
    print(json.dumps({"id": report["id"], "results": report["results"]}, indent=2))
