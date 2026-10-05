import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.ingestion import ingest
from app.live import channel, parse_csv, ReplayAdapter, resolve_context
from app.mud_loss import corroborate

client = TestClient(app)
ACTIVE = "SYN-ACTIVE-01"
NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def dataset():
    text = "elapsed_s,bit_md_m,operation_state,flow_in_l_min,flow_out_l_min,pit_volume_m3,ecd_sg\n"
    return (text+"\n".join(f"{i*10},{2400+i*5},DRILLING,950,880,{410-i*.1:.2f},1.19" for i in range(40))).encode()


def start(store, historical=True):
    well = store.get("well", ACTIVE)
    well["mud_program"]["ecd_sg"] = 1.19; store.put("well", well)
    if historical:
        for i in range(1, 5):
            offset = {**deepcopy(well), "id": f"SYN-NHK-{i:02d}", "status": "OFFSET", "held_out": False}
            store.put("well", offset)
            text = "Formation: Tipam\nOperation: DRILLING\nDatum: LOCAL_KB\nCoverage: 2200 m to 2580 m MD\n"
            text += "At 2500 m MD, partial mud loss observed.\nMitigation: LCM pill pumped.\nOutcome: returns improved.\n" if i <= 2 else "No mud loss observed during the covered drilling interval."
            doc = ingest(store, text.encode(), f"live-test-{i}.txt", offset["id"], True)
            for task in store.all("review"):
                if task["document_id"] == doc["id"]:
                    assert client.post(f"/api/review/{task['id']}", json={"reviewer": "Fixture validation", "action": "accept"}).status_code == 200
    uploaded = client.post("/api/replay/datasets", files={"file": ("signals.csv", dataset(), "text/csv")})
    assert uploaded.status_code == 200
    response = client.post("/api/replay/sessions", json={"dataset_id": uploaded.json()["id"], "md_interval_m": [2460, 2520]})
    assert response.status_code == 200, response.text
    return response.json()


def advance(result, frames=6):
    response = client.post(f"/api/replay/sessions/{result['session']['id']}/advance", json={"frames": frames})
    assert response.status_code == 200
    return response.json()


def test_csv_bounds_labels_and_missing():
    assert len(parse_csv(dataset())) == 40
    for content in (b"elapsed_s,bit_md_m\n0,2400", dataset().replace(b"ecd_sg", b"hidden_event_label"), dataset().replace(b"10,2405", b"0,2405"), dataset().replace(b"950", b"nan"), dataset().replace(b"0,2400", b"999999999,2400")):
        with pytest.raises(ValueError): parse_csv(content)
    sparse = parse_csv(b"elapsed_s,bit_md_m,operation_state\n0,2400,DRILLING")
    assert "flow_out_l_min" not in sparse[0]["values"]


def test_channel_freshness_boundary_future_and_suspect():
    def sample(age, value=950): return {"value": value, "timestamp": (NOW-timedelta(seconds=age)).isoformat()}
    assert channel("flow_in_l_min", sample(30), NOW, "TEST")["quality_status"] == "FRESH"
    assert channel("flow_in_l_min", sample(31), NOW, "TEST")["quality_status"] == "STALE"
    assert channel("flow_in_l_min", sample(-5), NOW, "TEST")["quality_status"] == "SUSPECT"
    assert channel("flow_in_l_min", sample(0, -5), NOW, "TEST")["quality_status"] == "SUSPECT"
    assert channel("flow_in_l_min", None, NOW, "TEST")["quality_status"] == "MISSING"


def test_context_precedence_conflict_and_adapter_interface(isolated_repository):
    well = isolated_repository.get("well", ACTIVE)
    samples = {"bit_md_m": {"value": 2400, "timestamp": NOW.isoformat()}, "tvd_m": {"value": 100, "timestamp": NOW.isoformat()}, "hole_md_m": {"value": 2000, "timestamp": NOW.isoformat()}}
    context = resolve_context(well, samples, NOW, "TEST")
    assert context["tvd_m"] == 100 and context["context_conflict"]
    assert context["formation_id"] == "TIPAM" and context["next_formation_id"] == "BARAIL"
    assert context["hole_section_in"] == 8.5 and "FALLBACK" in context["field_sources"]["hole_section_in"]
    adapter = ReplayAdapter(well, parse_csv(dataset()), {"cursor": 0, "epoch": NOW.isoformat(), "failures": {}})
    assert asyncio.run(adapter.get_current_context(ACTIVE))["clock"] == "REPLAY_SIMULATION"
    async def consume(): return [frame async for frame in adapter.stream_updates(ACTIVE)]
    assert len(asyncio.run(consume())) == 40


def test_elevated_warning_dedup_and_audited_lifecycle(isolated_repository):
    result = start(isolated_repository)
    assert result["assessment"]["historical"]["state"] == "ELEVATED"
    assert result["assessment"]["corroboration"]["state"] == "ELEVATED"
    result = advance(result)
    assert result["assessment"]["corroboration"]["state"] == "WARNING"
    alert = result["alert"]
    assert alert["lifecycle"] == "ESCALATED" and alert["notification_count"] == 2
    assert result["assessment"]["lessons"][0]["mitigation"] == "LCM pill pumped."
    for _ in range(3):
        same = client.post(f"/api/replay/sessions/{result['session']['id']}/evaluate").json()
        assert same["alert"]["id"] == alert["id"] and same["alert"]["notification_count"] == 2
    ack = client.post(f"/api/alerts/{alert['id']}/transition", json={"action": "acknowledge", "actor": "Test engineer"})
    assert ack.json()["lifecycle"] == "ACKNOWLEDGED"
    repeated = advance(result, 1)
    assert repeated["alert"]["lifecycle"] == "ACKNOWLEDGED" and repeated["alert"]["notification_count"] == 2
    assert len(client.get(f"/api/alerts?session_id={result['session']['id']}").json()) == 1
    assert isolated_repository.all("alert_audit")


@pytest.mark.parametrize("name", ["bit_md_m", "operation_state", "flow_in_l_min", "flow_out_l_min", "pit_volume_m3", "ecd_sg"])
@pytest.mark.parametrize("quality", ["STALE", "MISSING", "SUSPECT"])
def test_any_required_bad_channel_blocks_warning(isolated_repository, name, quality):
    result = advance(start(isolated_repository))
    response = client.post(f"/api/replay/sessions/{result['session']['id']}/quality", json={"channel": name, "quality": quality})
    assert response.status_code == 200
    changed = response.json()
    assert not changed["assessment"]["corroboration"]["warning_allowed"]
    assert changed["assessment"]["corroboration"]["state"] != "WARNING"
    assert changed["alert"]["evidence_state"] != "WARNING"
    assert changed["context"]["channels"][name]["quality_status"] == quality


def test_snooze_escalation_expiry_resolution_and_recovery(isolated_repository):
    result = start(isolated_repository)
    alert_id, run = result["alert"]["id"], result["session"]["id"]
    snooze = client.post(f"/api/alerts/{alert_id}/transition", json={"action": "snooze", "actor": "Engineer", "snooze_seconds": 60})
    assert snooze.json()["lifecycle"] == "SNOOZED"
    result = advance(result)  # Higher severity breaks snooze.
    assert result["alert"]["lifecycle"] == "ESCALATED"
    client.post(f"/api/alerts/{alert_id}/transition", json={"action": "snooze", "actor": "Engineer", "snooze_seconds": 30})
    result = advance(result, 3)
    assert result["alert"]["lifecycle"] == "CREATED"
    stale = client.post(f"/api/replay/sessions/{run}/quality", json={"channel": "flow_out_l_min", "quality": "STALE"}).json()
    assert stale["assessment"]["historical"]["state"] == "ELEVATED"
    assert stale["assessment"]["corroboration"]["state"] == "ELEVATED"
    result = advance(stale, 2)
    recovered = client.post(f"/api/replay/sessions/{run}/quality", json={"channel": "flow_out_l_min", "quality": "FRESH"}).json()
    assert not recovered["assessment"]["corroboration"]["warning_allowed"]
    result = advance(recovered, 6)
    assert result["assessment"]["corroboration"]["state"] == "WARNING"
    resolved = client.post(f"/api/alerts/{alert_id}/transition", json={"action": "resolve", "actor": "Engineer"})
    assert resolved.json()["lifecycle"] == "RESOLVED"
    assert advance(result, 1)["alert"]["lifecycle"] == "RESOLVED"
    assert client.post(f"/api/alerts/{alert_id}/transition", json={"action": "acknowledge", "actor": "Engineer"}).status_code == 409


def test_live_signals_alone_do_not_warn_and_interval_passed(isolated_repository):
    result = advance(start(isolated_repository, historical=False))
    assert result["assessment"]["corroboration"]["gates"]["flow_deficit_sustained"]
    assert not result["assessment"]["corroboration"]["warning_allowed"] and result["alert"] is None
    result = advance(start(isolated_repository), 39)
    assert not result["assessment"]["corroboration"]["warning_allowed"]
    assert result["alert"]["lifecycle"] == "RESOLVED"
    assert result["alert"]["peak_state"] == "WARNING"  # Batched replay evaluates intermediate frames.


def test_manual_partial_updates_freshness_and_validation(isolated_repository, monkeypatch):
    from app import live
    monkeypatch.setattr(live, "utc_now", lambda: NOW)
    created = client.post("/api/replay/sessions", json={"adapter": "MANUAL"}).json()
    run = created["session"]["id"]
    sample = {"bit_md_m": {"value": 2400, "timestamp": NOW.isoformat()}, "flow_out_l_min": {"value": 880, "timestamp": (NOW-timedelta(seconds=40)).isoformat()}}
    result = client.post(f"/api/replay/sessions/{run}/manual", json={"samples": sample}).json()
    assert result["context"]["channels"]["flow_out_l_min"]["quality_status"] == "STALE"
    assert not result["assessment"]["corroboration"]["warning_allowed"]
    for value in ({"unknown": sample["bit_md_m"]}, {"bit_md_m": {"value": 2, "timestamp": "2026-10-04T00:00:00"}}, {"bit_md_m": {"value": 2, "timestamp": (NOW-timedelta(seconds=5)).isoformat()}}):
        assert client.post(f"/api/replay/sessions/{run}/manual", json={"samples": value}).status_code == 422


def test_time_skew_conflict_and_operation_guards(isolated_repository):
    result = advance(start(isolated_repository))
    context, evidence = result["context"], result["assessment"]["historical"]
    context["context_conflict"] = True
    assert not corroborate(context, evidence)["warning_allowed"]
    context["context_conflict"] = False; context["operation_state"] = "TRIPPING"
    assert not corroborate(context, evidence)["warning_allowed"]
    context["operation_state"] = "DRILLING"
    at = datetime.fromisoformat(context["timestamp"])
    context["channels"]["flow_out_l_min"]["timestamp"] = (at-timedelta(seconds=20)).isoformat()
    assert not corroborate(context, evidence)["gates"]["samples_time_coherent"]


def test_meaningful_review_change_and_storage_reopen(isolated_repository):
    from app.store import Store
    result = advance(start(isolated_repository))
    row = next(r for r in result["assessment"]["historical"]["rows"] if r["role"] == "SUPPORT")
    event = isolated_repository.get("event", row["selected_event_id"])
    event["md_from_m"] += 10
    isolated_repository.put("event", event)
    new = client.post(f"/api/replay/sessions/{result['session']['id']}/evaluate").json()
    assert new["alert"]["notification_count"] == result["alert"]["notification_count"]+1
    reopened = Store(str(isolated_repository.engine.url))
    assert reopened.get("alert", new["alert"]["id"])["history"][-1]["event"] == "evidence_changed"
    assert reopened.get("live_session", new["session"]["id"])["cursor"] == 6
    assert client.get(f"/api/evidence/snapshots/{new['assessment']['historical']['id']}").status_code == 200


def test_duplicate_manual_samples_do_not_prove_sustained_flow(isolated_repository):
    result = advance(start(isolated_repository))
    context, evidence = result["context"], result["assessment"]["historical"]
    timestamp = context["channels"]["flow_out_l_min"]["timestamp"]
    for record in context["history"]:
        record["channel_timestamps"] = {"flow_out_l_min": timestamp}
    assert not corroborate(context, evidence)["gates"]["flow_deficit_sustained"]
