"""Score externally supplied, pre-registered field validation without tuning on the test set."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from .paths import DATA_ROOT


def overlap(a, b):
    intersection = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return intersection / union if union else 0.0


def evaluate(manifest):
    predictions, truth = manifest.get("frozen_predictions", []), manifest.get("revealed_truth", [])
    wells = {row["well_id"] for row in predictions + truth}
    if not predictions or not truth:
        return {"status": "PENDING_EXTERNAL_FIELD_DATA", "production_claim_allowed": False,
                "limitations": ["No independently collected frozen predictions and revealed field truth were supplied"]}
    frozen_at, revealed_at = manifest.get("predictions_frozen_at"), manifest.get("truth_revealed_at")
    if not frozen_at or not revealed_at or frozen_at >= revealed_at:
        raise ValueError("Predictions must be timestamped and frozen before truth reveal")
    hits, matched_truth, lead = 0, set(), []
    for prediction in predictions:
        candidates = [(index, event) for index, event in enumerate(truth)
                      if event["well_id"] == prediction["well_id"] and event["risk_type"] == prediction["risk_type"]
                      and overlap(prediction["md_interval_m"], event["md_interval_m"]) > 0]
        if candidates:
            index, event = max(candidates, key=lambda item: overlap(prediction["md_interval_m"], item[1]["md_interval_m"]))
            hits += 1; matched_truth.add(index)
            lead.append(max(0, event["md_interval_m"][0] - prediction["issued_at_md_m"]))
    severe = [i for i, row in enumerate(truth) if row.get("severity") in {"SEVERE", "TOTAL"}]
    result = {
        "status": "SCORED_EXTERNAL_FIELD_SET", "production_claim_allowed": False,
        "well_count": len(wells), "prediction_count": len(predictions), "truth_event_count": len(truth),
        "alert_precision": round(hits / len(predictions), 4),
        "event_recall": round(len(matched_truth) / len(truth), 4),
        "severe_event_recall": round(len(set(severe) & matched_truth) / len(severe), 4) if severe else None,
        "median_lead_distance_m": sorted(lead)[len(lead)//2] if lead else None,
        "calibration": {"eligible": len(wells) >= 10 and len(truth) >= 30,
                        "minimum": "10 wells and 30 truth events",
                        "action": "INDEPENDENT_REVIEW_REQUIRED; policy values are never changed automatically"},
        "limitations": ["Field representativeness and labels require independent domain review", "This scorer does not tune on the held-out set"],
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(DATA_ROOT / "validation" / "field-manifest-template.json"))
    parser.add_argument("--output", default=str(DATA_ROOT / "validation" / "field-validation.json"))
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    report = evaluate(manifest) | {"generated_at": datetime.now(timezone.utc).isoformat(), "manifest_id": manifest.get("id")}
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
