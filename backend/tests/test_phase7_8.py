from copy import deepcopy
from datetime import datetime, timedelta, timezone
import math
from fastapi.testclient import TestClient
import pytest
from app.main import app
from app.live import resolve_context
from app.secondary import module, trend
from app.ingestion import ingest
from app.validate_replay import score

client = TestClient(app)
NOW = datetime(2026, 1, 15, tzinfo=timezone.utc)


def context(store, operation="DRILLING", **current):
    well = store.get("well", "SYN-ACTIVE-01")
    values = {"bit_md_m": 2450, "hole_md_m": 2600, "operation_state": operation, "torque_kn_m": 12, "hookload_kn": 1000,
              "standpipe_pressure_kpa": 18000, "flow_in_l_min": 950, "flow_out_l_min": 945, "pit_volume_m3": 410,
              "gas_pct": .5, "mud_weight_sg": 1.16, "ecd_sg": 1.19, "rop_m_h": 20, "wob_kn": 90, "rpm": 120, "hole_section_in": 8.5}
    rows = [{"timestamp": (NOW-timedelta(seconds=s)).isoformat(), "values": deepcopy(values), "quality_status": "VALID"} for s in (40,30,20,10)]
    values.update(current)
    samples = {key: {"value": value, "timestamp": NOW.isoformat()} for key, value in values.items()}
    return well, resolve_context(well, samples, NOW, "TEST", history=rows)


def session(): return {"formation": "TIPAM", "md_interval_m": [2200, 2580], "radius_km": 3}


def test_stuck_pipe_is_partial_and_binds_operation(isolated_repository):
    well, ctx = context(isolated_repository, torque_kn_m=20, hookload_kn=1300, standpipe_pressure_kpa=23000)
    result = module(isolated_repository, well, session(), ctx, "STUCK_PIPE")
    assert result["maturity"] == "PARTIAL_DECISION_SUPPORT" and not result["warning_allowed"]
    assert all(item["triggered"] for item in result["indicators"][:3])
    assert result["indicators"][-1]["value"] == 40
    ctx["operation_state"] = "CEMENTING"
    assert not module(isolated_repository, well, session(), ctx, "STUCK_PIPE")["operation_bound"]
    ctx["channels"]["torque_kn_m"]["quality_status"] = "STALE"
    assert not trend(ctx, "torque_kn_m")["available"]


def test_kick_conservative_gas_pit_flow_and_tripping_gate(isolated_repository):
    well, ctx = context(isolated_repository, pit_volume_m3=411, gas_pct=2, flow_out_l_min=1030)
    for row in ctx["history"]: row["values"]["flow_out_l_min"] = 1030
    result = module(isolated_repository, well, session(), ctx, "KICK")
    assert all(i["triggered"] for i in result["indicators"])
    assert result["status"] == "SIGNALS_FOR_REVIEW" and not result["warning_allowed"]
    ctx["operation_state"] = "TRIPPING"
    assert not module(isolated_repository, well, session(), ctx, "KICK")["operation_bound"]
    ctx["operation_state"] = "DRILLING"; ctx["channels"]["gas_pct"]["quality_status"] = "STALE"
    assert not module(isolated_repository, well, session(), ctx, "KICK")["operation_bound"]


def test_torque_residual_and_mse_dimensions(isolated_repository):
    well, ctx = context(isolated_repository, torque_kn_m=18)
    result = module(isolated_repository, well, session(), ctx, "TORQUE_DYSFUNCTION")
    assert result["indicators"][0]["value"] == 6
    mse = result["indicators"][-1]
    area = math.pi*(8.5*.0254)**2/4
    assert mse["value"] == pytest.approx((90000/area + 120*math.pi*18000*120/(area*20))/1e6)
    assert not mse["triggered"] and "standalone" in mse["interpretation"]
    ctx["channels"]["rop_m_h"]["value"] = 0
    assert module(isolated_repository, well, session(), ctx, "TORQUE_DYSFUNCTION")["indicators"][-1]["value"] is None


def test_history_gaps_and_duplicate_acquisitions_unknown(isolated_repository):
    _, ctx = context(isolated_repository)
    for row in ctx["history"]: row["channel_timestamps"] = {"torque_kn_m": NOW.isoformat()}
    assert not trend(ctx, "torque_kn_m")["available"]
    ctx["history"][0]["quality_status"] = "SUSPECT"
    ctx["history"] = ctx["history"][:1]
    assert not trend(ctx, "hookload_kn")["available"]


def test_cementing_sourced_common_framework_without_live_model(isolated_repository):
    well, ctx = context(isolated_repository)
    well["mud_program"]["ecd_sg"] = 1.19
    offset = deepcopy(well); offset.update(id="SYN-CEMENT-OFFSET", status="OFFSET", held_out=False)
    isolated_repository.put("well", offset)
    doc = ingest(isolated_repository, b"Cement Report\nFormation: Tipam\nOperation: CEMENTING\nDatum: LOCAL_KB\nAt 2450 m MD, cementing failure observed.\nMitigation: remedial cement squeeze.\nOutcome: integrity reviewed.\n", "cement.txt", offset["id"], True, doc_type="CEMENT_REPORT")
    for key in doc["event_ids"]:
        event = isolated_repository.get("event", key);event["review_status"] = "VERIFIED";isolated_repository.put("event", event)
    result = module(isolated_repository, well, session(), ctx, "CEMENTING_ISSUE")
    assert result["maturity"] == "HISTORICAL_PLANNING_ONLY" and result["indicators"] == []
    assert result["historical"]["support_count"] == 1
    assert result["lessons"][0]["job_record"]["report_type"] == "CEMENT_REPORT"


def test_brief_chain_map_and_secondary_versioned_apis(isolated_repository):
    run = client.post("/api/replay/demo").json()["session"]["id"]
    secondary = client.get(f"/api/v1/replay/sessions/{run}/secondary")
    assert secondary.status_code == 200
    assert len(secondary.json()["modules"]) == 4
    brief = client.get(f"/api/v1/replay/sessions/{run}/brief").json()
    assert brief["risk_windows"] and brief["casing_points"] and brief["risk_summaries"]
    window = brief["risk_windows"][0]
    chain = client.get(f"/api/v1/evidence/chain/{window['evidence_snapshot_id']}/{window['event_id']}")
    assert chain.status_code == 200 and chain.json()["span"]["provenance_type"] == "FACT"
    assert chain.json()["alignment"]["provenance_type"] == "COMPUTED"
    assert client.get(f"/api/evidence/chain/{window['evidence_snapshot_id']}/unrelated").status_code == 404
    swap = client.get("/api/wells/SYN-ACTIVE-01/ranking-swap").json()
    assert swap["swap"] is not None
    assert swap["swap"][0]["surface_rank"] < swap["swap"][1]["surface_rank"]
    assert swap["swap"][0]["target_rank"] > swap["swap"][1]["target_rank"]
    assert client.get("/api/wells/SYN-ACTIVE-01/compare").json()["alignment"].startswith("normalized")
    assert client.get("/api/validation/results").json()["status"] == "NOT_RUN"


def test_unit_review_and_prioritized_queue(isolated_repository):
    run = client.post("/api/replay/demo").json()["session"]["id"]
    doc = ingest(isolated_repository, b"Formation: Tippam\nOperation: DRILLING\nDatum: LOCAL_KB\nAt 8100 ft MD, partial mud loss observed.\n", "review.txt", "SYN-DEMO-OFFSET-1", True)
    queue = client.get(f"/api/review?session_id={run}").json()
    task = next(item for item in queue if item["document_id"] == doc["id"] and item["kind"] == "event")
    assert task["affects_active_lookahead"]
    response = client.post(f"/api/review/{task['id']}", json={"reviewer": "Engineer", "action": "correct", "formation_id": "TIPAM", "depth_value": 8200, "depth_unit": "ft"})
    assert response.status_code == 200
    assert response.json()["md_from_m"] == pytest.approx(2499.36)
    assert response.json()["original_unit"] == "ft"
    assert response.json()["reviewed_depth_measurement"]["original_value"] == 8200


def test_validation_hit_miss_and_no_false_accuracy():
    result = score([{"bit_md_m": 2400, "window": [2490,2510]}], [[2500,2520],[2600,2620]], [1,2])
    assert result["hits"] == 1 and result["misses"] == 1 and result["lead_distance_m"] == [100]
    assert result["accuracy"] is None and result["specificity"] is None
    late = score([{"bit_md_m": 2530, "window": [2490,2510]}], [[2500,2520]], [1])
    assert late["hits"] == 0


def test_offline_validation_publishes_typed_aggregates_without_truth(isolated_repository):
    from app.validate_replay import run
    report = run(isolated_repository)
    stored = isolated_repository.get("validation_report", report["id"])
    assert set(stored["results"][0]["baselines"]) == {"radius_only", "raw_depth", "formation_evidence", "mud_loss_slice"}
    assert stored["repository_sha256"] and stored["results"][0]["source_status"]
    assert stored["results"][0]["baselines"]["mud_loss_slice"]["misses"] == 1
    published = client.get("/api/v1/validation/results").json()
    assert published["status"] == "AVAILABLE"
    assert "expected_intervals" not in published and "held_out_events" not in published


def test_compare_requires_explicit_clean_source(isolated_repository):
    client.post("/api/replay/demo")
    result = client.get("/api/wells/SYN-DEMO-ACTIVE/compare").json()
    counter = next(w for w in result["wells"] if w["well_id"] == "SYN-DEMO-OFFSET-3")
    assert any(c["risk_type"] == "MUD_LOSS" for c in counter["clean_crossings"])
    support = next(w for w in result["wells"] if w["well_id"] == "SYN-DEMO-OFFSET-1")
    assert not any(c["risk_type"] == "MUD_LOSS" for c in support["clean_crossings"])
