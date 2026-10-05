import json
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import independent_validation as module


def client(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "DATA_ROOT", tmp_path)
    gold = tmp_path / "gold"; gold.mkdir()
    (gold / "labels.json").write_text(json.dumps({"pages": [
        {"id": "GOLD-01", "page": 1, "events": [{"event_type": "MUD_LOSS", "source_quote": "loss"}]},
        {"id": "GOLD-02", "page": 2, "events": []},
    ]}), encoding="utf-8")
    app = FastAPI(); app.include_router(module.router)
    return TestClient(app)


def test_gold_signoff_requires_human_and_all_boxes(tmp_path, monkeypatch):
    api = client(tmp_path, monkeypatch)
    invalid = api.post("/api/validation/gold/pages/GOLD-01/review", json={
        "reviewer": "Codex bot", "independent_human_attestation": True, "decision": "ACCEPTED", "annotations": []})
    assert invalid.status_code == 422
    body = {"reviewer": "Reviewer-17", "independent_human_attestation": True, "decision": "ACCEPTED",
            "annotations": [{"event_index": 0, "source_bbox": {"x": .1, "y": .2, "width": .3, "height": .1}}]}
    first = api.post("/api/validation/gold/pages/GOLD-01/review", json=body)
    assert first.status_code == 200
    assert first.json()["summary"]["independent_human_signoff"] is False
    second = api.post("/api/validation/gold/pages/GOLD-02/review", json=body | {"annotations": []})
    assert second.status_code == 200
    assert second.json()["summary"]["independent_human_signoff"] is True


def test_usability_needs_five_independent_participants(tmp_path, monkeypatch):
    api = client(tmp_path, monkeypatch)
    for index in range(5):
        response = api.post("/api/validation/usability", json={
            "participant_code": f"P{index+1:02}", "independent_human_attestation": True,
            "elapsed_seconds": 18, "identified_risk": "mud loss", "identified_reason": "Offset loss projects ahead",
            "reason_choice": "HISTORICAL_OFFSET_LOSSES_PROJECTED_AHEAD", "opened_source": True})
        assert response.status_code == 200
    assert response.json()["summary"]["criterion_verified"] is True


def test_bbox_must_stay_on_page(tmp_path, monkeypatch):
    api = client(tmp_path, monkeypatch)
    response = api.post("/api/validation/gold/pages/GOLD-01/review", json={
        "reviewer": "Reviewer-17", "independent_human_attestation": True, "decision": "ACCEPTED",
        "annotations": [{"event_index": 0, "source_bbox": {"x": .9, "y": .2, "width": .3, "height": .1}}]})
    assert response.status_code == 422
