from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.ingestion import ingest
from app.document_intelligence import detect_layout, extract_quantities
from app.gazetteer import match_formation, ENTRIES
from app.geometry import trajectory, project_event, separation
from app.transfer_context import compare_context
from app.evidence import transfer, evaluate

client = TestClient(app)


def test_metadata_content_type_private_default_and_dates(isolated_repository):
    text = b"Well Completion Report\nWell: SYN-NHK-02\nDate: 2026-10-04\nDate coverage: 2026-10-01 to 2026-10-04\nFormation: Tipam\nCoverage: 2200 m to 2580 m MD\n"
    doc = ingest(isolated_repository, text, "incorrect-DDR-name.txt", "SYN-NHK-02")
    assert doc["doc_type"] == "WCR" and doc["doc_type_source"] == "CONTENT"
    assert doc["classification"] == "PRIVATE"
    assert doc["well_identity_status"] == "MATCHED"
    assert doc["dates"][0]["value"] == "2026-10-04"
    coverage = isolated_repository.get("coverage", doc["coverage_ids"][0])
    assert coverage["date_from"] == "2026-10-01" and coverage["date_coverage_status"] == "PROBABLE"
    task = next(item for item in isolated_repository.all("review") if item["entity_id"] == coverage["id"])
    response = client.post(f"/api/review/{task['id']}", json={"reviewer": "Verifier", "action": "accept"})
    assert response.status_code == 200 and response.json()["date_coverage_status"] == "VERIFIED"


def test_public_confidential_conflict_and_declared_type(isolated_repository):
    with pytest.raises(ValueError):
        ingest(isolated_repository, b"CONFIDENTIAL\nDaily Drilling Report", "doc.txt", "SYN-NHK-02", classification="PUBLIC")
    doc = ingest(isolated_repository, b"Daily Drilling Report", "doc.txt", "SYN-NHK-02", classification="PUBLIC", doc_type="WCR")
    assert doc["classification"] == "PUBLIC" and doc["doc_type"] == "WCR"
    assert any(item["kind"] == "document" for item in isolated_repository.all("review"))


def test_mismatched_well_is_reviewed_and_blocks_evidence(isolated_repository):
    text = b"Daily Drilling Report\nWell: ANOTHER-WELL\nFormation: Tipam\nDatum: LOCAL_KB\nOperation: DRLG\nAt 2500 m MD, mud loss observed."
    doc = ingest(isolated_repository, text, "doc.txt", "SYN-NHK-02")
    event = isolated_repository.get("event", doc["event_ids"][0])
    assert event["review_status"] == "NEEDS_REVIEW"
    assert event["operation_state"] == "DRILLING"
    task = next(item for item in isolated_repository.all("review") if item["kind"] == "document")
    assert client.post(f"/api/review/{task['id']}", json={"reviewer": "Verifier"}).status_code == 422
    assert client.post(f"/api/review/{task['id']}", json={"reviewer": "Verifier", "confirm_well_identity": True}).status_code == 200


def test_narrative_quantities_and_source_grounding(isolated_repository):
    text = b"Daily Drilling Report\nFormation: Tipam\nDatum: LOCAL_KB\nOperation: DRLG\nAt 8000 ft MD, LC observed due to fractured rock.\nMW: 10 ppg; Hole size: 8 1/2 in; SPP: 1800 psi.\nPumped LCM pill 15 bbl. Returns restored.\nGas: 3 %; Influx volume: 5 bbl.\n"
    doc = ingest(isolated_repository, text, "narrative.txt", "SYN-NHK-02")
    event = isolated_repository.get("event", doc["event_ids"][0])
    assert event["event_type"] == "MUD_LOSS" and event["cause_kind"] == "stated"
    assert "Pumped" in event["mitigation"] and "restored" in event["outcome"]
    assert event["context_values"]["mud_weight_sg"] == pytest.approx(1.19826427316)
    assert event["context_values"]["hole_section_in"] == 8.5
    assert event["context_values"]["standpipe_pressure_kpa"] == pytest.approx(12410.5631277)
    assert event["context_values"]["lcm_volume_m3"] == pytest.approx(15*.158987294928)
    for item in event["numerical_fields"].values():
        source = item["source"]
        assert source["char_start"] >= 0
        assert text.decode()[source["char_start"]:source["char_end"]] == source["text"]


def test_layout_tables_and_depth_grounding(isolated_repository):
    text = b"Daily Drilling Report\nFormation: Tipam\nDatum: LOCAL_KB\nOPERATIONS\nMD (ft) | Event | MW (ppg)\n8000 | mud loss observed | 10\n"
    doc = ingest(isolated_repository, text, "table.txt", "SYN-NHK-02")
    layout = doc["page_data"][0]["layout"]
    assert any(item["kind"] == "HEADER" for item in layout["regions"])
    assert layout["sections"] and layout["tables"][0]["depth_columns"][0]["unit"] == "ft"
    event = isolated_repository.get("event", doc["event_ids"][0])
    assert event["md_from_m"] == pytest.approx(2438.4)
    assert event["field_evidence"]["md_from_m"]["table_header"] == "MD (ft)"
    assert doc["numerical_fields"]["page_1_mud_weight_sg"]["source"]["cell_text"] == "10"


def test_fuzzy_basin_and_source_registry(isolated_repository):
    exact = match_formation("Tipam Sandstone")
    assert exact["formation_id"] == "TIPAM" and exact["sources"][0]["url"].startswith("https://www.ndrdgh")
    fuzzy = match_formation("Tipm")
    assert fuzzy["formation_id"] is None and fuzzy["requires_review"] and fuzzy["candidates"][0]["formation_id"] == "TIPAM"
    assert match_formation("Tipam", "OTHER_BASIN")["formation_id"] is None
    assert len(ENTRIES) >= 15
    doc = ingest(isolated_repository, b"Formation: Tipm\nAt 2500 m MD, stuck pipe observed.", "fuzzy.txt", "SYN-NHK-02")
    assert isolated_repository.get("event", doc["event_ids"][0])["review_status"] == "NEEDS_REVIEW"


def test_conflicting_quantity_is_not_used_as_event_context(isolated_repository):
    doc = ingest(isolated_repository, b"Formation: Tipam\nAt 2500 m MD, kick observed.\nMW: 10 ppg\nMW: 14 ppg", "conflict.txt", "SYN-NHK-02")
    event = isolated_repository.get("event", doc["event_ids"][0])
    assert "mud_weight_sg" not in event["context_values"]
    assert event["numerical_fields"]["mud_weight_sg"]["alternatives"]
    assert event["review_status"] == "NEEDS_REVIEW"


def test_dogleg_severity_and_datum_envelope():
    path = trajectory([{"md_m": 0, "incl_deg": 0, "azi_deg": 0}, {"md_m": 100, "incl_deg": 10, "azi_deg": 0}])
    assert path[-1]["dogleg_severity_deg_per_30m"] == pytest.approx(3)
    source = {"top_md_m": 1000, "base_md_m": 1200, "datum": "KB", "uncertainty_m": 10}
    target = {**source, "top_md_m": 2000, "base_md_m": 2400}
    normal = project_event({"md_from_m": 1100}, source, target)
    wide = project_event({"md_from_m": 1100, "depth_uncertainty_m": 2}, {**source, "datum_uncertainty_m": 5}, {**target, "datum_uncertainty_m": 7})
    assert wide["projected_md_interval_m"][0] == pytest.approx(normal["projected_md_interval_m"][0]-16)
    assert wide["uncertainty_components"]["datum_margin_m"] == 12
    assert wide["inputs"]["event"]["depth_uncertainty_m"] == 2
    distance = separation(path, path, [0,100], [0,100], 12)
    assert distance["target_distance_interval_m"] == [0,12]


@pytest.mark.parametrize("method", ["estimated_thickness", "tvd_fallback", "raw_md_last_resort"])
def test_every_fallback_retains_inputs(method):
    source = {"top_md_m": 1000, "base_md_m": None, "datum": "KB", "uncertainty_m": 5}
    target = {"top_md_m": 2000, "base_md_m": None, "datum": "KB", "uncertainty_m": 5}
    event = {"md_from_m": 1100}
    path = None
    if method == "estimated_thickness":
        source["approx_thickness_m"], target["approx_thickness_m"] = 200, 400
    if method == "tvd_fallback":
        path = trajectory([{"md_m": 0, "incl_deg": 0, "azi_deg": 0}, {"md_m": 3000, "incl_deg": 0, "azi_deg": 0}])
    result = project_event(event, source, target, path, path)
    assert result["method"] == method
    assert result["inputs"]["source"] == source and result["inputs"]["target"] == target
    assert result["inputs"]["source_path"] == path


def context_pair(store):
    active, offset = deepcopy(store.get("well", "SYN-ACTIVE-01")), deepcopy(store.get("well", "SYN-NHK-02"))
    for well in (active, offset):
        well["mud_program"]["mud_weight_sg"] = 1.2
        well["pressure_context"] = {"pore_pressure_kpa": 20000, "overbalance_kpa": 5000}
        well["operating_context"] = {"stationary_exposure_h": 3, "permeability_md": 100, "gas_pct": 3, "influx_volume_m3": 1}
        well["drilled_year"], well["drilling_technology"] = 2020, "ROTARY"
        well["survey"] = [{"md_m": 0, "incl_deg": 0, "azi_deg": 0}, {"md_m": 2500, "incl_deg": 30, "azi_deg": 0}, {"md_m": 3400, "incl_deg": 70 if well is offset else 30, "azi_deg": 0}]
    return active, offset


def test_stuck_pipe_uses_event_inclination_and_quantitative_factors(isolated_repository):
    active, offset = context_pair(isolated_repository)
    result = compare_context(active, offset, "STUCK_PIPE", {"md_from_m": 2500}, {"projected_md_interval_m": [2500,2500]}, "TIPAM")
    inclination = next(item for item in result["comparisons"] if "inclination" in item["name"])
    assert inclination["difference"] == 0  # terminal offset inclination is 70 degrees
    assert not result["unknowns"]
    offset["operating_context"]["stationary_exposure_h"] = 12
    changed = compare_context(active, offset, "STUCK_PIPE", {"md_from_m": 2500}, {"projected_md_interval_m": [2500,2500]}, "TIPAM")
    assert changed["factor"] < result["factor"]


def test_kick_comparisons_missing_penalty_and_opposite_regimes(isolated_repository):
    active, offset = context_pair(isolated_repository)
    args = ("KICK", {"md_from_m": 2500}, {"projected_md_interval_m": [2500,2500]}, "TIPAM")
    full = compare_context(active, offset, *args)
    assert not full["unknowns"]
    assert any(item["name"] == "gas_pct" for item in full["comparisons"])
    offset["operating_context"].pop("gas_pct")
    assert compare_context(active, offset, *args)["factor"] < full["factor"]
    offset["pressure_context"]["overbalance_kpa"] = -500
    assert "opposite_overbalance_regime" in compare_context(active, offset, *args)["blockers"]


def test_hydrostatic_overbalance_inputs_are_retained(isolated_repository):
    active, offset = context_pair(isolated_repository)
    for well in (active, offset):
        well["pressure_context"].pop("overbalance_kpa")
    result = compare_context(active, offset, "KICK", {"md_from_m": 2500}, {"projected_md_interval_m": [2500,2500]}, "TIPAM")
    calculation = result["derived_inputs"]["overbalance"]["active"]
    assert calculation["method"] == "hydrostatic-minus-pore-pressure"
    overbalance = next(item for item in result["comparisons"] if item["name"] == "overbalance_kpa")
    assert overbalance["active_value"] == pytest.approx(1.2*9.80665*calculation["tvd_m"]-20000)


def test_missing_comparison_never_improves_dissimilar_weight(isolated_repository):
    active, offset = context_pair(isolated_repository)
    offset["pressure_context"]["pore_pressure_kpa"] = 100000
    known = compare_context(active, offset, formation_id="TIPAM")
    offset["pressure_context"].pop("pore_pressure_kpa")
    assert compare_context(active, offset, formation_id="TIPAM")["factor"] <= known["factor"]


def test_upgrade_preserves_reviewed_depth_and_is_repeatable(isolated_repository):
    from app.upgrade_documents import upgrade_documents
    text = b"Daily Drilling Report\nFormation: Tipam\nDate coverage: 2026-01-01 to 2026-01-02\nAt 2500 m MD, mud loss observed."
    doc = ingest(isolated_repository, text, "retained.txt", "SYN-NHK-02")
    event = isolated_repository.get("event", doc["event_ids"][0])
    event.update(md_from_m=2499, reviewer="Human", review_status="VERIFIED")
    isolated_repository.put("event", event)
    doc.pop("intelligence_version")
    doc["page_data"][0].pop("layout")
    isolated_repository.put("document", doc)
    assert upgrade_documents(isolated_repository) == 1
    assert upgrade_documents(isolated_repository) == 0
    retained = isolated_repository.get("event", event["id"])
    assert retained["md_from_m"] == 2499 and retained["reviewer"] == "Human"
    audit = isolated_repository.all("audit")[-1]
    assert audit["before"]["page_data"][0].get("layout") is None
    assert audit["after"]["page_data"][0]["layout"]["tables"] == []


def test_native_table_cells_preserve_actual_source_offsets(isolated_repository):
    import fitz
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((32, 40), "Daily Drilling Report\nFormation: Tipam\nDatum: LOCAL_KB")
    for row, cells in enumerate([["MD (m)", "Event", "MW (ppg)"], ["2500", "mud loss observed", "10"]]):
        for col, cell in enumerate(cells):
            page.insert_text((32+col*150, 120+row*30), cell)
    content = pdf.tobytes()
    pdf.close()
    doc = ingest(isolated_repository, content, "native.pdf", "SYN-NHK-02")
    event = isolated_repository.get("event", doc["event_ids"][0])
    assert event["md_from_m"] == 2500
    span = isolated_repository.get("source_span", event["source_span_id"])
    assert span["char_start"] >= 0 and span["bbox"]
    assert doc["numerical_fields"]["page_1_mud_weight_sg"]["source"]["bbox"]


def test_date_only_correction_preserves_source_and_never_verifies_depth(isolated_repository):
    text = b"Daily Drilling Report\nDate coverage: 01/02/2026 to 03/02/2026"
    doc = ingest(isolated_repository, text, "dates.txt", "SYN-NHK-02")
    task = next(item for item in isolated_repository.all("review") if item["kind"] == "coverage")
    response = client.post(f"/api/review/{task['id']}", json={"reviewer": "Verifier", "action": "correct", "date_from": "2026-01-02", "date_to": "2026-03-02"})
    assert response.status_code == 200
    coverage = response.json()
    assert coverage["date_coverage_status"] == "VERIFIED" and coverage["date_from"] == "2026-01-02"
    assert coverage["coverage_status"] == "UNKNOWN" and coverage["md_interval"] is None
    assert "01/02/2026" in coverage["date_source"]["text"]
    assert isolated_repository.get("document", doc["id"])["date_coverage"]["date_from"] == "2026-01-02"
    from app.upgrade_documents import upgrade_documents
    stored_doc = isolated_repository.get("document", doc["id"])
    stored_doc.pop("intelligence_version")
    isolated_repository.put("document", stored_doc)
    upgrade_documents(isolated_repository)
    assert isolated_repository.get("document", doc["id"])["date_coverage"]["date_from"] == "2026-01-02"
    assert isolated_repository.get("coverage", coverage["id"])["date_coverage_status"] == "VERIFIED"
