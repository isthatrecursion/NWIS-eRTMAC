import pytest
from app.field_validation import evaluate


def test_field_validation_stays_pending_without_external_data():
    assert evaluate({})["status"] == "PENDING_EXTERNAL_FIELD_DATA"


def test_field_validation_rejects_temporal_leakage():
    with pytest.raises(ValueError, match="frozen before"):
        evaluate({"predictions_frozen_at": "2026-02-01", "truth_revealed_at": "2026-01-01",
                  "frozen_predictions": [{"well_id": "W1", "risk_type": "MUD_LOSS", "md_interval_m": [100, 120], "issued_at_md_m": 80}],
                  "revealed_truth": [{"well_id": "W1", "risk_type": "MUD_LOSS", "md_interval_m": [110, 115]}]})


def test_field_scoring_does_not_auto_calibrate_small_set():
    report = evaluate({"predictions_frozen_at": "2026-01-01", "truth_revealed_at": "2026-02-01",
        "frozen_predictions": [{"well_id": "W1", "risk_type": "MUD_LOSS", "md_interval_m": [100, 120], "issued_at_md_m": 80}],
        "revealed_truth": [{"well_id": "W1", "risk_type": "MUD_LOSS", "md_interval_m": [110, 115], "severity": "SEVERE"}]})
    assert report["alert_precision"] == 1
    assert report["severe_event_recall"] == 1
    assert report["calibration"]["eligible"] is False
    assert report["production_claim_allowed"] is False
