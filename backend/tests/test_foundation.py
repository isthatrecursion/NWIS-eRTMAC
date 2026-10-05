import json
from datetime import datetime, timezone
import pytest
from sqlalchemy import text
from fastapi.testclient import TestClient
from app.main import app
from app.generator import build_field, generate_reports, write_evaluation, EVENT_DETAILS
from app.domain.units import normalize
from app.live import channel
from app.migrate import upgrade


@pytest.mark.parametrize("value,unit,quantity,expected", [
    (100, "ft", "depth", 30.48), (10, "ppg", "density", 1.19826427316),
    (1200, "kg/m3", "density", 1.2), (100, "psi", "pressure", 689.4757293168),
    (2, "MPa", "pressure", 2000), (1, "bar", "pressure", 100)])
def test_units_preserve_source(value, unit, quantity, expected):
    measurement = normalize(value, unit, quantity, "KB", "MD", "report")
    assert measurement.value == pytest.approx(expected)
    assert (measurement.original_value, measurement.original_unit, measurement.datum, measurement.source) == (value, unit, "KB", "report")


def test_reject_unknown_and_nonfinite_units():
    with pytest.raises(ValueError):
        normalize(1, "furlongs", "depth")
    with pytest.raises(ValueError):
        normalize(float("nan"), "sg", "density")


def test_live_unit_conversion():
    now = datetime.now(timezone.utc)
    result = channel("ecd_sg", {"value": 10, "unit": "ppg", "timestamp": now, "datum": "KB"}, now, "MANUAL")
    assert result["value"] == pytest.approx(1.19826427316)
    assert result["quality_status"] == "FRESH"
    assert result["measurement"]["original_unit"] == "ppg"
    mismatched = channel("bit_md_m", {"value": 8000, "unit": "ft", "reference": "TVD", "timestamp": now}, now, "MANUAL")
    assert mismatched["value"] is None
    assert mismatched["quality_status"] != "FRESH"


def test_migration_idempotent_and_data_preserved(isolated_repository):
    store = isolated_repository
    upgrade(store.engine)
    upgrade(store.engine)
    assert store.get("well", "SYN-ACTIVE-01")
    with store.engine.connect() as connection:
        assert connection.execute(text("select version_num from alembic_version")).scalar() == "0001_foundation"


def test_versioned_api_and_error_contract():
    client = TestClient(app)
    assert client.get("/api/v1/wells").json() == client.get("/api/wells").json()
    response = client.get("/api/v1/wells/missing")
    assert response.status_code == 404
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
    assert client.get("/api/v1/wells/SYN-ACTIVE-01/lookahead?risk=TORQUE_DYSFUNCTION").status_code == 200
    assert client.get("/api/v1/evaluation/truth").status_code == 404


def test_event_mix_manifests_and_nested_labels(tmp_path):
    field, truth = build_field()
    assert (field, truth) == build_field()
    assert {event["event_type"] for event in field["events"]} == {"MUD_LOSS", *EVENT_DETAILS}
    assert all(event["well_id"] != "SYN-ACTIVE-01" for event in field["events"])
    assert field["wells"][0]["survey"][0]["synthetic_flag"]
    assert field["wells"][0]["mud_program"]["synthetic_flag"]
    write_evaluation(field, truth, tmp_path)
    held_out = json.loads((tmp_path/"held_out_events.json").read_text())
    assert {event["event_type"] for event in held_out} == {"MUD_LOSS", *EVENT_DETAILS}
    assert all(event["well_id"] == "SYN-ACTIVE-01" for event in held_out)
    assert (tmp_path/"generator_metadata.json").exists()
    assert json.loads((tmp_path/"expected_intervals.json").read_text())


def test_generated_native_reports_cover_all_event_types(tmp_path, isolated_repository):
    from pathlib import Path
    from app.ingestion import ingest
    field, _ = build_field()
    manifest = generate_reports(field, tmp_path/"reports")
    assert {item["doc_type"] for item in manifest} == {"DDR", "WCR"}
    extracted = set()
    for item in manifest:
        if item["is_scan"]:
            continue
        path = Path(item["path"])
        doc = ingest(isolated_repository, path.read_bytes(), path.name, item["well_id"], synthetic=True)
        assert doc["measurements"]["page_1_standpipe_pressure_kpa"]["original_unit"] == "psi"
        for key in doc["event_ids"]:
            event = isolated_repository.get("event", key)
            assert event["synthetic_flag"]
            assert event["measurements"]["md_from_m"]["datum"] == "LOCAL_KB"
            extracted.add(event["event_type"])
    assert extracted == {"MUD_LOSS", *EVENT_DETAILS}
