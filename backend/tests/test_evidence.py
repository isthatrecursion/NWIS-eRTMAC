from copy import deepcopy
from fastapi.testclient import TestClient
from app.main import app
from app.evidence import candidate, transfer, aggregate, evaluate
from app.ingestion import ingest

client = TestClient(app)
ACTIVE = "SYN-ACTIVE-01"


def pair(store):
    active = store.get("well", ACTIVE)
    offset = deepcopy(store.get("well", "SYN-NHK-02"))
    offset["structural_domain"] = active["structural_domain"]
    offset["mud_program"] = deepcopy(active["mud_program"])
    store.put("well", offset)
    return active, offset


def event():
    return {"id": "EV-TEST", "event_type": "MUD_LOSS", "formation_id": "TIPAM", "md_from_m": 2500,
            "datum": "LOCAL_KB", "confidence": 1., "review_status": "VERIFIED", "operation_state": "DRILLING",
            "source_span_id": "SPAN", "document_id": "DOC"}


def test_cascade_and_trusted_structure(isolated_repository):
    a, b = pair(isolated_repository)
    assert candidate(a, b, "TIPAM", 3)["decision"] == "CANDIDATE"
    assert "outside_surface_radius" in candidate(a, b, "TIPAM", 1)["blockers"]
    b["formations"] = []
    assert "formation_absent" in candidate(a, b, "TIPAM", 3)["blockers"]
    a, b = pair(isolated_repository)
    b["structural_domain"] = "OTHER"
    assert "trusted_structural_domain_mismatch" in candidate(a, b, "TIPAM", 3)["blockers"]
    b["structural_quality"] = "UNTRUSTED"
    result = candidate(a, b, "TIPAM", 3)
    assert not result["blockers"] and result["unknowns"]


def test_transfer_factors_and_missing_penalty(isolated_repository):
    a, b = pair(isolated_repository)
    full = transfer(a, b, event())
    assert full["decision"] == "INCLUDED" and full["projection"]["projected_md_interval_m"]
    del b["mud_program"]["ecd_sg"]
    missing = transfer(a, b, event())
    assert missing["weight"] < full["weight"] and "missing ecd_sg" in missing["unknowns"]
    b["mud_program"]["hole_section_in"] = 12.25
    assert transfer(a, b, event())["weight"] == 0


def test_event_review_datum_and_operation_blockers(isolated_repository):
    a, b = pair(isolated_repository)
    for update in ({"review_status": "QUARANTINED"}, {"review_status": "NEEDS_REVIEW"}, {"datum": "UNKNOWN"}, {"md_from_m": None}, {"operation_state": "TRIPPING"}, {"source_span_id": None}):
        result = transfer(a, b, {**event(), **update})
        assert result["weight"] == 0 and result["decision"] == "EXCLUDED" and result["blockers"]


def test_risk_specific_unknowns(isolated_repository):
    a, b = pair(isolated_repository)
    for risk, phrase in (("KICK", "pressure"), ("STUCK_PIPE", "overbalance"), ("CEMENTING_ISSUE", "cement programme")):
        result = transfer(a, b, {**event(), "event_type": risk})
        assert any(phrase in s for s in result["unknowns"])
        assert result["weight"] < transfer(a, b, event())["weight"]


def report(store, offset, positive=False):
    text = "Formation: Tipam\nOperation: DRILLING\nDatum: LOCAL_KB\nCoverage: 2200 m to 2580 m MD\n"
    text += "At 2500 m MD, partial mud loss observed.\n" if positive else "No mud loss observed during the covered drilling interval.\n"
    return ingest(store, text.encode(), "phase4.txt", offset["id"], True)


def test_clean_requires_review_explicit_negation_and_envelope(isolated_repository):
    store = isolated_repository
    a, b = pair(store)
    doc = report(store, b)
    def row(interval=(2460, 2520)):
        return next(r for r in evaluate(store, a, "TIPAM", "MUD_LOSS", interval)["rows"] if r["well_id"] == b["id"])
    assert row()["role"] == "UNKNOWN"
    coverage = store.get("coverage", doc["coverage_ids"][0])
    coverage["coverage_status"] = "VERIFIED"; store.put("coverage", coverage)
    assert row()["role"] == "COUNTER" and row()["clean_source"]["source_text"].startswith("No mud loss")
    assert row((2540, 2580))["role"] == "UNKNOWN"  # uncertainty extends beyond coverage
    doc["page_data"][0]["text"] = "Coverage only; no risk-specific clean assertion"
    store.put("document", doc)
    assert row()["role"] == "UNKNOWN"


def test_support_dedup_interval_and_superseded(isolated_repository):
    store = isolated_repository; a, b = pair(store)
    doc = report(store, b, True)
    e = store.get("event", doc["event_ids"][0]); e["review_status"] = "VERIFIED"; store.put("event", e)
    store.put("event", {**e, "id": "DUPLICATE"})
    result = evaluate(store, a, "TIPAM", "MUD_LOSS", [2460, 2520])
    assert result["support_count"] == 1 and result["usable_wells"] == 1
    assert evaluate(store, a, "TIPAM", "MUD_LOSS", [2240, 2280])["support_count"] == 0
    doc["superseded_by"] = "NEW"; store.put("document", doc)
    assert evaluate(store, a, "TIPAM", "MUD_LOSS", [2460, 2520])["support_count"] == 0


def test_weighted_stats_unknown_exclusion_no_warning():
    rows = [{"role": "SUPPORT", "weight": .5}, {"role": "SUPPORT", "weight": .5}, {"role": "COUNTER", "weight": .5}]
    result = aggregate(rows)
    assert result["state"] == "ELEVATED" and result["internal_statistics"]["n_eff"] == 3
    assert result["internal_statistics"]["p_hat"] == 2/3.5
    more = aggregate(rows+[{"role": "UNKNOWN", "weight": 99}])
    assert result["internal_statistics"] == more["internal_statistics"]
    assert not result["warning_allowed"]
    assert aggregate([])["state"] == "NO_EVIDENCE"
    assert aggregate(rows[:1])["state"] == "LESSON"


def test_api_validation_and_snapshot(isolated_repository):
    for query in ("md_from_m=2580&md_to_m=2460", "md_from_m=0", "radius_km=nan", "risk=UNKNOWN", "formation=ABSENT"):
        assert client.get(f"/api/wells/{ACTIVE}/lookahead?{query}").status_code == 422
    result = client.get(f"/api/wells/{ACTIVE}/lookahead").json()
    assert result["policy_version"] and result["context_source"] and not result["warning_allowed"]
    assert isolated_repository.get("evidence_snapshot", result["id"])
    assert client.get(f"/api/wells/{ACTIVE}/analogs").status_code == 200
    assert client.get("/api/evaluation/truth").status_code == 404


def test_review_to_elevated_end_to_end(isolated_repository):
    store = isolated_repository; a, template = pair(store)
    for index in range(1, 5):
        offset = {**deepcopy(template), "id": f"SYN-NHK-{index:02d}"}
        store.put("well", offset)
        doc = report(store, offset, positive=index <= 2)
        for task in store.all("review"):
            if task["document_id"] == doc["id"]:
                assert client.post(f"/api/review/{task['id']}", json={"reviewer": "Automated fixture verification", "action": "accept"}).status_code == 200
    result = client.get(f"/api/wells/{ACTIVE}/lookahead?md_from_m=2460&md_to_m=2520").json()
    assert result["support_count"] == 2 and result["counter_count"] == 2
    assert result["state"] == "ELEVATED" and result["internal_statistics"]["n_eff"] >= 3
    assert not result["warning_allowed"]
    included = next(t for r in result["rows"] for t in r["transfers"] if t["decision"] == "INCLUDED")
    assert included["source"]["text"] and included["inputs"]["event"]["review_status"] in ("AUTO_ACCEPTED", "VERIFIED")
    posted = client.post("/api/transferability/event", json={"active_well_id": ACTIVE, "event_id": included["event_id"]})
    assert posted.status_code == 200 and store.get("transferability", posted.json()["id"])
    # Review quarantine invalidates current evaluation without altering the old snapshot.
    ev = included["inputs"]["event"]; ev["review_status"] = "QUARANTINED"; store.put("event", ev)
    updated = client.get(f"/api/wells/{ACTIVE}/lookahead?md_from_m=2460&md_to_m=2520").json()
    assert updated["support_count"] == 1 and updated["state"] == "LESSON"
    assert updated["id"] != result["id"]
    assert store.get("evidence_snapshot", result["id"])["support_count"] == 2
