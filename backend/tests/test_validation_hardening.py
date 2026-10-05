import json
from pathlib import Path
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app
from app.blind_validation import prepare, metrics, overlap, fixed_similarity
from app.gold_set import author
from app.safety import source_path
from app.assurance import publish_junit, safety
from app.config import get_settings


def test_metrics_match_once_and_count_false_negatives():
    rows = [{"well_id":"A", "alerts":[{"bit_md_m":90,"window":[95,115]}, {"bit_md_m":95,"window":[95,115]}]}, {"well_id":"B","alerts":[]}]
    truth = [{"well_id":"A","events":[{"md_interval_m":[100,110],"severity":"SEVERE"}]}, {"well_id":"B","events":[{"md_interval_m":[200,220],"severity":"SEVERE"}]}]
    result = metrics(rows, truth, 1000)
    assert result["hits"] == 1 and result["false_alerts"] == 1
    assert result["false_negatives"] == 1
    assert result["alert_precision"] == result["severe_event_recall"] == .5
    assert result["lead_distance_m"] == [10]
    assert result["alerts_per_1000_m"] == 2
    assert overlap([95,115],[100,110]) == .5


def test_blind_runtime_excludes_labels_and_future_records(tmp_path):
    root = tmp_path/"blind"
    store = prepare(root)
    runtime = json.loads((root/"runtime/blind_cases.json").read_text(encoding="utf-8"))
    hidden = json.loads((root/"evaluation/blind_truth.json").read_text(encoding="utf-8"))
    assert len(runtime["cases"]) == 8
    assert sum(bool(t["events"]) for t in hidden["truth"]) == 3
    assert all("events" not in c and "case_kind" not in c for c in runtime["cases"])
    ids = {c["id"] for c in runtime["cases"]}
    assert not any(e["well_id"] in ids for e in store.all("event"))
    assert not any(d["well_id"] in ids for d in store.all("document"))


def test_fixed_baseline_uses_declared_features():
    active={"mud_program":{"hole_section_in":8.5,"mud_system":"WBM","ecd_sg":1.2}}
    close={**active,"formations":[{"formation_id":"TIPAM"}]}
    different={"mud_program":{"hole_section_in":12.25,"mud_system":"OBM","ecd_sg":1.5},"formations":[]}
    assert fixed_similarity(active,close) == 1
    assert fixed_similarity(active,different) == 0


def test_reference_has_independently_authored_labels_and_pending_signoff(tmp_path):
    import fitz
    labels=author(tmp_path/"gold")
    assert len(labels["pages"]) == 40
    assert not labels["independent_human_signoff"]
    assert sum(len(p["events"]) for p in labels["pages"]) == 30
    assert sum(p["scanned"] for p in labels["pages"]) == 5
    with fitz.open(tmp_path/"gold/representative_pages.pdf") as pdf:
        assert len(pdf) == 40
    assert all(p["label_review_status"] == "HUMAN_REVIEW_PENDING" for p in labels["pages"])


def test_source_paths_cannot_escape_storage(tmp_path):
    assert source_path({"path":str(tmp_path/"allowed.pdf")}) == tmp_path/"allowed.pdf"
    with pytest.raises(HTTPException) as error:
        source_path({"path":str(tmp_path.parent/"secret.txt")})
    assert error.value.status_code == 403


def test_junit_publication_preserves_actual_failures(tmp_path, isolated_repository):
    path=tmp_path/"results.xml"
    path.write_text('<testsuites><testsuite tests="2" failures="1" errors="0" skipped="0"><testcase name="pass"/><testcase name="fail"><failure/></testcase></testsuite></testsuites>',encoding="utf-8")
    result=publish_junit(path,isolated_repository)
    assert result["tests"] == 2 and result["failures"] == 1
    assert result["test_cases"] == ["pass","fail"]
    assert isolated_repository.get("engineering_report",result["id"]) == result


def test_demo_headers_and_no_actuation_routes(monkeypatch, isolated_repository):
    monkeypatch.setattr(get_settings(),"demo_mode",True)
    response=TestClient(app).get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"
    assert not any(word in r.path.lower() for r in app.routes for word in ("actuate","writeback","rig-command"))
    assert all(c["passed"] for c in safety(isolated_repository)["checks"])


def test_hardening_api_exposes_only_published_aggregates(isolated_repository):
    response=TestClient(app).get("/api/v1/validation/hardening")
    assert response.status_code == 200
    assert "blind_truth" not in response.text
    assert set(response.json()) == {"benchmark_report","extraction_report","engineering_report","safety_report"}
