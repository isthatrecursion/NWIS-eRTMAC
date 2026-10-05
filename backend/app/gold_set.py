"""Offline extraction reference authoring and scoring; no parser-generated labels."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from .paths import DATA_ROOT
from .store import repository
from .ingestion import read_pages, extract, VERSION as PARSER_VERSION
from .document_intelligence import detect_layout

VERSION = "curated-extraction-reference/1.0"
# These labels are authored independently of extractor output. Human sign-off is pending.
POSITIVE = [
    ("MUD_LOSS", "severe mud loss observed", "LCM pill pumped.", "Returns improved."),
    ("STUCK_PIPE", "stuck pipe observed", "Worked pipe within approved limits.", "Pipe freed."),
    ("KICK", "influx observed", "Well shut in under approved procedure.", "Pressures stabilized."),
    ("TORQUE_DYSFUNCTION", "stick slip observed", "Adjusted drilling parameters after review.", "Torque stabilized."),
    ("CEMENTING_ISSUE", "cementing failure observed", "Remedial squeeze performed.", "Integrity reviewed."),
]
DEPTHS = [("2438.4 m MD",2438.4), ("8000 ft MD",2438.4), ("2450 m MD",2450.), ("2480 m TVD",None), ("2500 m MD",2500.), ("2520 m MD",2520.)]
NEGATIVE = [
    "No mud loss observed during the covered drilling interval.",
    "No stuck pipe observed during the covered drilling interval.",
    "No kick observed during the covered drilling interval.",
    "No torque dysfunction observed during the covered drilling interval.",
    "No cementing failure observed during the covered cementing interval.",
    "At 2450 m MD, check the kick contingency plan before drilling ahead.",
    "At 2460 m MD, discuss possible stuck pipe hazards at the planning meeting.",
    "At 2470 m MD, mud loss is a potential risk; none occurred on this shift.",
    "At 2480 m MD, stick slip is listed in the training manual, not observed here.",
    "At 2490 m MD, cement loss contingency prepared; the cement job has not started.",
]


def author(root):
    import fitz
    root.mkdir(parents=True, exist_ok=True)
    pdf, records = fitz.open(), []
    for risk, symptom, action, outcome in POSITIVE:
        for style, (quantity, depth) in enumerate(DEPTHS):
            index = len(records)+1
            formation = "Tipam Sandstone" if style == 1 else "Barail" if style == 4 else "Tippam" if style == 3 else "Tipam"
            expected_formation = "BARAIL" if style == 4 else None if style == 3 else "TIPAM"
            sentence = f"At {quantity}, {symptom}."
            title = "SYNTHETIC WELL COMPLETION REPORT" if style % 2 else "SYNTHETIC DAILY DRILLING REPORT"
            text = f"{title}\nDate: 2026-01-{index:02}\nFormation: {formation}\nDatum: LOCAL_KB\nOperation: {'CEMENTING' if risk == 'CEMENTING_ISSUE' else 'DRILLING'}\nCoverage: 2200 m to 2580 m MD\nMud weight: 9.8 ppg\nHole size: 8.5 in\n{sentence}\nMitigation: {action}\nOutcome: {outcome}\n"
            page = pdf.new_page(width=600,height=800)
            scanned = style == 5
            if scanned:
                scratch = fitz.open();canvas = scratch.new_page(width=600,height=800)
                canvas.insert_textbox(fitz.Rect(35,35,565,760), text, fontsize=12)
                pixels = canvas.get_pixmap(matrix=fitz.Matrix(1.5,1.5), alpha=False)
                page.insert_image(page.rect, pixmap=pixels);scratch.close()
            else: page.insert_textbox(fitz.Rect(35,35,565,760), text, fontsize=12)
            records.append({"id": f"GOLD-{index:02}", "page": index, "text": text, "scanned": scanned,
                "events": [{"event_type": risk, "md_from_m": depth, "formation_id": expected_formation, "mitigation": action, "outcome": outcome, "source_quote": sentence}], "label_review_status": "HUMAN_REVIEW_PENDING"})
    for sentence in NEGATIVE:
        index = len(records)+1
        text = f"SYNTHETIC DAILY REPORT\nFormation: Tipam\nDatum: LOCAL_KB\nOperation: DRILLING\n{sentence}\n"
        page = pdf.new_page(width=600,height=800);page.insert_textbox(fitz.Rect(35,35,565,760),text,fontsize=12)
        records.append({"id": f"GOLD-{index:02}", "page": index, "text": text, "scanned": False, "events": [], "label_review_status": "HUMAN_REVIEW_PENDING"})
    pdf.save(root/"representative_pages.pdf");pdf.close()
    labels = {"version": VERSION, "annotation_method": "Curated reference labels authored independently of extractor outputs", "independent_human_signoff": False,
        "scope": "Synthetic authored pages; native text, scanned pages, feet, TVD, aliases, narratives and hard negatives", "pages": records}
    (root/"labels.json").write_text(json.dumps(labels,indent=2),encoding="utf-8")
    return labels


def norm(text): return " ".join((text or "").lower().split())


def run(root=DATA_ROOT/"gold", publish_store=None):
    # Re-running scoring preserves edited labels and manual review status.
    if not (root/"labels.json").exists(): author(root)
    labels = json.loads((root/"labels.json").read_text(encoding="utf-8"))
    reviews_path = root/"human_reviews.json"
    reviews = json.loads(reviews_path.read_text(encoding="utf-8")) if reviews_path.exists() else {"reviews": {}}
    completed_reviews = reviews.get("reviews", {})
    expected_boxes = sum(len(page["events"]) for page in labels["pages"])
    independent_human_signoff = bool(labels["pages"]) and all(
        page["id"] in completed_reviews and completed_reviews[page["id"]].get("independent_human_attestation")
        and completed_reviews[page["id"]].get("decision") in {"ACCEPTED", "CORRECTED"}
        for page in labels["pages"]
    ) and sum(len(row.get("annotations", [])) for row in completed_reviews.values()) == expected_boxes
    raw = (root/"representative_pages.pdf").read_bytes()
    pages = read_pages(raw, ".pdf")
    if len(pages) != len(labels["pages"]): raise ValueError("Reference labels must cover every page")
    counts = {risk:{"tp":0,"fp":0,"fn":0} for risk,_,_,_ in POSITIVE}
    depth_correct = depth_total = formation_correct = field_correct = field_total = grounded = predicted_total = review_pages = 0
    failures = []
    for page, reference in zip(pages, labels["pages"]):
        page["layout"] = detect_layout(page)
        predicted = extract(page)
        predicted_total += len(predicted)
        review_pages += any(e["review_status"] != "AUTO_ACCEPTED" for e in predicted)
        used = set()
        for expected in reference["events"]:
            index = next((i for i,p in enumerate(predicted) if i not in used and p["event_type"] == expected["event_type"]), None)
            if index is None:
                counts[expected["event_type"]]["fn"] += 1
                failures.append({"page": page["page"], "kind": "MISSED_EVENT", "event_type": expected["event_type"]})
                depth_total += expected["md_from_m"] is not None;field_total += 2
                continue
            used.add(index);actual = predicted[index];counts[expected["event_type"]]["tp"] += 1
            if expected["md_from_m"] is not None:
                depth_total += 1
                depth_correct += actual["md_from_m"] is not None and abs(actual["md_from_m"]-expected["md_from_m"]) <= .1
            formation_correct += actual["formation_id"] == expected["formation_id"]
            for key in ("mitigation", "outcome"):
                field_total += 1;field_correct += norm(actual.get(key)) == norm(expected[key])
            grounded += norm(actual["source_text"]) == norm(expected["source_quote"]) and norm(actual["source_text"]) in norm(page["text"])
        for i,actual in enumerate(predicted):
            if i not in used:
                counts[actual["event_type"]]["fp"] += 1
                failures.append({"page": page["page"], "kind": "FALSE_POSITIVE", "source_text": actual["source_text"]})
    total_expected = sum(len(p["events"]) for p in labels["pages"])
    for row in counts.values():
        row["precision"] = row["tp"]/(row["tp"]+row["fp"]) if row["tp"]+row["fp"] else None
        row["recall"] = row["tp"]/(row["tp"]+row["fn"]) if row["tp"]+row["fn"] else None
    result = {"id": "EXTRACTION-"+hashlib.sha256(raw+(root/"labels.json").read_bytes()+PARSER_VERSION.encode()).hexdigest()[:20],
        "version": VERSION, "parser_version": PARSER_VERSION, "generated_at": datetime.now(timezone.utc).isoformat(), "synthetic_flag": True,
        "page_count": len(pages), "scanned_pages": sum(p["is_scan"] for p in pages), "independent_human_signoff": independent_human_signoff,
        "event_types": counts, "depth_accuracy": depth_correct/depth_total if depth_total else None, "depth_tolerance_m": .1,
        "formation_correctness": formation_correct/total_expected if total_expected else None,
        "mitigation_outcome_exact_match": field_correct/field_total if field_total else None,
        "source_span_grounding": grounded/predicted_total if predicted_total else None, "requiring_review_fraction": review_pages/len(pages),
        "denominators": {"expected_events": total_expected, "predicted_events": predicted_total, "depth_fields": depth_total, "mitigation_outcome_fields": field_total},
        "failures": failures, "input_sha256": hashlib.sha256(raw).hexdigest(), "labels_sha256": hashlib.sha256((root/"labels.json").read_bytes()).hexdigest(),
        "limitations": (["Reference annotations are curated synthetic authoring, not independently human-certified labels", "Human sign-off and bounding-box review are pending"] if not independent_human_signoff else ["Independent human page and bounding-box sign-off is recorded in human_reviews.json"]) + ["Metrics do not estimate field-document performance", "Source grounding uses exact normalized quote matching"]}
    (publish_store or repository()).put("extraction_report",result)
    (root/"results.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result


if __name__ == "__main__":
    report = run()
    print(json.dumps({key:value for key,value in report.items() if key != "failures"},indent=2))
