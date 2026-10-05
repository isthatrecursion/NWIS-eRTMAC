from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import get_settings, MudLossPolicy, Settings
from app.live import channel, resolve_context

client = TestClient(app)


def control(run, action, **kwargs):
    response = client.post(f"/api/v1/replay/sessions/{run}/control", json={"action": action, **kwargs})
    assert response.status_code == 200, response.text
    return response.json()


def test_demo_complete_sequence_and_reset(isolated_repository):
    response = client.post("/api/v1/replay/demo")
    assert response.status_code == 200, response.text
    initial = response.json()
    run = initial["session"]["id"]
    assert initial["assessment"]["historical"]["state"] == "ELEVATED"
    assert initial["assessment"]["corroboration"]["state"] == "NO_EVIDENCE"
    assert initial["alert"] is None
    lesson = control(run, "seek", cursor=2)
    assert lesson["assessment"]["corroboration"]["state"] == "LESSON"
    elevated = client.post(f"/api/replay/sessions/{run}/advance", json={"frames": 4}).json()
    assert elevated["assessment"]["corroboration"]["state"] == "ELEVATED"
    warning = client.post(f"/api/replay/sessions/{run}/advance", json={"frames": 4}).json()
    assert warning["assessment"]["corroboration"]["state"] == "WARNING"
    assert warning["assessment"]["corroboration"]["mud_weight_change_sg"] > 0
    lesson_event = warning["assessment"]["lessons"][0]
    assert lesson_event["severity"] == "SEVERE"
    assert lesson_event["event_md_interval_m"] == [2490, 2500]
    assert lesson_event["mud_context"]["mud_weight_sg"] == 1.16
    for name in ("mud_weight_sg", "wob_kn", "rpm", "torque_kn_m", "hookload_kn", "standpipe_pressure_kpa", "gas_pct"):
        assert warning["context"]["channels"][name]["quality_status"] == "FRESH"
        assert warning["context"]["channels"][name]["freshness_threshold_s"] > 0
    reset = control(run, "reset")
    assert reset["session"]["id"] == run and reset["session"]["cursor"] == 0
    assert reset["session"]["failures"] == {} and reset["session"]["quality_events"] == []
    assert reset["context"] == initial["context"]
    replayed = control(run, "seek", cursor=10)
    assert replayed["context"] == warning["context"]
    assert replayed["assessment"]["corroboration"] == warning["assessment"]["corroboration"]
    assert replayed["alert"]["id"] == warning["alert"]["id"]
    assert any(row["event"] == "replay_episode_reset" for row in replayed["alert"]["history"])
    passed = client.post(f"/api/replay/sessions/{run}/advance", json={"frames": 6}).json()
    assert passed["alert"]["lifecycle"] == "RESOLVED"
    assert passed["alert"]["snoozed_until"] is None
    assert passed["context"]["formation_id"] == "BARAIL"
    assert not passed["assessment"]["corroboration"]["warning_allowed"]


def test_cross_run_dedup_and_resolved_latch(isolated_repository):
    first = client.post("/api/replay/demo").json()
    one = control(first["session"]["id"], "seek", cursor=10)
    second = client.post("/api/replay/sessions", json={"well_id": first["session"]["well_id"], "dataset_id": first["session"]["dataset_id"], "md_interval_m": [2460, 2520]}).json()
    assert second["alert"]["id"] == one["alert"]["id"]
    assert len([a for a in isolated_repository.all("alert") if a["well_id"] == first["session"]["well_id"]]) == 1
    client.post(f"/api/alerts/{one['alert']['id']}/transition", json={"action": "resolve", "actor": "Acceptance engineer"})
    response = client.post(f"/api/replay/sessions/{second['session']['id']}/evaluate").json()
    assert response["alert"]["lifecycle"] == "RESOLVED"


def test_per_channel_freshness_and_torque_unit(monkeypatch):
    monkeypatch.setattr(get_settings(), "channel_freshness_s", {"gas_pct": 5, "mud_weight_sg": 60})
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    sample = {"value": 1.16, "timestamp": (now-timedelta(seconds=10)).isoformat()}
    assert channel("mud_weight_sg", sample, now, "TEST")["quality_status"] == "FRESH"
    assert channel("gas_pct", sample, now, "TEST")["quality_status"] == "STALE"
    assert channel("gas_pct", sample, now, "TEST")["freshness_threshold_s"] == 5
    assert channel("torque_kn_m", {**sample, "unit": "ft"}, now, "TEST")["quality_status"] == "SUSPECT"
    with pytest.raises(ValueError): Settings(channel_freshness_s={"gas_pct": -1})
    with pytest.raises(ValueError): MudLossPolicy(lesson_distance_m=1, approach_distance_m=100)


def test_exact_formation_transition_and_uncertainty(isolated_repository):
    well = isolated_repository.get("well", "SYN-ACTIVE-01")
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    before = resolve_context(well, {"bit_md_m": {"value": 2579, "timestamp": now.isoformat()}}, now, "TEST")
    at = resolve_context(well, {"bit_md_m": {"value": 2580, "timestamp": now.isoformat()}}, now, "TEST")
    assert before["formation_id"] == "TIPAM" and before["distance_to_next_top_m"] == 1
    assert before["formation_uncertainty"]["boundary_overlap"]
    assert at["formation_id"] == "BARAIL"


def test_websocket_snapshot_and_backend_clock(isolated_repository, monkeypatch):
    from app import live_routes
    initial = client.post("/api/replay/demo").json()
    run = initial["session"]["id"]
    with client.websocket_connect(f"/api/v1/replay/sessions/{run}/stream") as socket:
        frame = socket.receive_json()
        assert frame["session"]["id"] == run and frame["session"]["cursor"] == 0
    session = isolated_repository.get("live_session", run)
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    session.update(playing=True, speed=10, wall_anchor=now.isoformat(), elapsed_anchor=0)
    monkeypatch.setattr(live_routes, "utc_now", lambda: now+timedelta(seconds=10))
    live_routes.tick(session)
    assert isolated_repository.get("live_session", run)["cursor"] == 10
    assert isolated_repository.all("alert")[0]["peak_state"] == "WARNING"
    paused = control(run, "pause")
    assert not paused["session"]["playing"]
    assert control(run, "speed", speed=20)["session"]["speed"] == 20
    assert client.post(f"/api/replay/sessions/{run}/control", json={"action": "seek", "cursor": 1000}).status_code == 422


def test_autonomous_play_pause_and_websocket_updates(isolated_repository):
    with TestClient(app) as running_client:
        run = running_client.post("/api/replay/demo").json()["session"]["id"]
        with running_client.websocket_connect(f"/api/v1/replay/sessions/{run}/stream") as socket:
            assert socket.receive_json()["session"]["cursor"] == 0
            playing = running_client.post(f"/api/replay/sessions/{run}/control", json={"action": "play", "speed": 100}).json()
            assert playing["session"]["playing"]
            while True:
                frame = socket.receive_json()
                if frame["session"]["cursor"] >= 10: break
            # At 100× a slow subscriber may observe the passed interval; the engine
            # must still have evaluated and retained intermediate Warning escalation.
            assert frame["alert"]["peak_state"] == "WARNING"
            paused = running_client.post(f"/api/replay/sessions/{run}/control", json={"action": "pause"}).json()
            assert not paused["session"]["playing"]
            cursor = paused["session"]["cursor"]
            if frame["session"]["playing"]:
                while socket.receive_json()["session"]["playing"]: pass
            assert isolated_repository.get("live_session", run)["cursor"] == cursor


def test_quality_is_scoped_to_trend_channel(isolated_repository):
    first = client.post("/api/replay/demo").json()
    run = first["session"]["id"]
    control(run, "seek", cursor=10)
    changed = client.post(f"/api/replay/sessions/{run}/quality", json={"channel": "gas_pct", "quality": "SUSPECT"}).json()
    changed = client.post(f"/api/replay/sessions/{run}/advance", json={"frames": 1}).json()
    assert changed["assessment"]["corroboration"]["warning_allowed"]
    changed = client.post(f"/api/replay/sessions/{run}/quality", json={"channel": "mud_weight_sg", "quality": "STALE"}).json()
    assert changed["assessment"]["corroboration"]["mud_weight_change_sg"] is None


def test_configured_policy_changes_gates_and_keeps_history(isolated_repository, monkeypatch):
    first = client.post("/api/replay/demo").json()
    run = first["session"]["id"]
    control(run, "seek", cursor=10)
    monkeypatch.setattr(get_settings(), "mud_loss_policy", MudLossPolicy(pit_drop_min_m3=5, flow_sustained_min_samples=4, lesson_distance_m=1000))
    changed = client.post(f"/api/replay/sessions/{run}/evaluate").json()
    assert not changed["assessment"]["corroboration"]["warning_allowed"]
    assert changed["assessment"]["corroboration"]["policy"]["pit_drop_min_m3"] == 5
    assert client.get("/api/v1/replay/config").json()["mud_loss_policy"]["flow_sustained_min_samples"] == 4


def test_review_event_interval_and_original_feet(isolated_repository):
    from app.ingestion import ingest
    from app.geometry import project_event
    doc = ingest(isolated_repository, b"Formation: Tipam\nOperation: DRILLING\nDatum: LOCAL_KB\nAt 8100 ft to 8200 ft MD, total mud loss observed.\nMud weight: 10 ppg\nMud system: OBM\n", "interval.txt", "SYN-ACTIVE-01", True)
    event = isolated_repository.get("event", doc["event_ids"][0])
    assert event["severity"] == "TOTAL" and event["context_values"]["mud_system"] == "OBM"
    assert event["md_to_m"] == pytest.approx(2499.36)
    assert event["measurements"]["md_to_m"]["original_unit"] == "ft"
    assert event["field_evidence"]["event_md_interval_m"]["char_end"] > event["field_evidence"]["event_md_interval_m"]["char_start"]
    interval = next(f for f in isolated_repository.get("well", "SYN-ACTIVE-01")["formations"] if f["formation_id"] == "TIPAM")
    projection = project_event(event, interval, interval)
    assert projection["projected_md_interval_m"][0] < event["md_from_m"]
    assert projection["projected_md_interval_m"][1] > event["md_to_m"]
    task = {"id": "REV-INTERVAL", "kind": "event", "entity_id": event["id"], "document_id": doc["id"], "status": "PENDING", "reason": "Acceptance interval correction", "priority": "HIGH"}
    isolated_repository.put("review", task)
    assert client.post("/api/review/REV-INTERVAL", json={"reviewer": "Engineer", "action": "correct", "md_from_m": 2500, "md_to_m": 2490}).status_code == 422
    response = client.post("/api/review/REV-INTERVAL", json={"reviewer": "Engineer", "action": "correct", "md_from_m": 2490, "md_to_m": 2500, "severity": "SEVERE"})
    assert response.status_code == 200
    assert response.json()["event_md_interval_m"] == [2490, 2500]
