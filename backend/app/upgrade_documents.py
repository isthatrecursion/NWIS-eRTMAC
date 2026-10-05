"""Enrich retained document sources without replacing human-reviewed observations."""
from datetime import datetime, timezone
from copy import deepcopy
from .document_intelligence import VERSION, metadata, detect_layout
from .ingestion import extract
from .store import repository


def upgrade_documents(store):
    changed = 0
    for doc in store.all("document"):
        if doc.get("intelligence_version") == VERSION:
            continue
        well = store.get("well", doc["well_id"])
        before = deepcopy(doc)
        pages = doc.get("page_data", [])
        for page in pages:
            page["layout"] = detect_layout(page)
        intelligence = metadata(pages, well,
            declared_type=doc.get("doc_type") if doc.get("doc_type_source") == "DECLARED" and doc.get("doc_type") != "UNKNOWN" else None,
            classification=doc.get("classification", "PRIVATE"))
        if doc.get("well_identity_confirmed"):
            intelligence["review_reasons"] = [reason for reason in intelligence["review_reasons"] if reason != "Reported well name does not match associated well"]
        doc.update(intelligence)
        doc.setdefault("measurements", {}).update({name: field["measurement"] for name, field in intelligence["numerical_fields"].items()})
        for page in pages:
            parsed = extract(page)
            for event_id in doc["event_ids"]:
                event = store.get("event", event_id)
                span = store.get("source_span", event["source_span_id"])
                matching = next((item for item in parsed if item["event_type"] == event["event_type"] and item["source_text"] == span["text"] and span["page"] == page["page"]), None)
                if matching:
                    for key in ("formation_match", "numerical_fields", "context_values", "event_date"):
                        event[key] = matching[key]
                    # Original measurements and human corrections remain authoritative.
                    event.setdefault("field_evidence", {}).update({key: value for key, value in matching["field_evidence"].items() if key not in event.get("field_evidence", {})})
                    event.setdefault("measurements", {}).update({key: value for key, value in matching.get("measurements", {}).items() if key not in event.get("measurements", {})})
                    if not event.get("reviewer") and matching["review_reasons"]:
                        event["review_reasons"] = matching["review_reasons"]
                        event["review_status"] = matching["review_status"]
                        task_id = "REV-"+event_id
                        task = store.get("review", task_id)
                        if task is None or task.get("status") != "RESOLVED":
                            store.put("review", {"id": task_id, "kind": "event", "entity_id": event_id, "document_id": doc["id"],
                                "status": "PENDING", "reason": "; ".join(event["review_reasons"]), "priority": "HIGH"})
                    store.put("event", event)
        for coverage_id in doc["coverage_ids"]:
            coverage = store.get("coverage", coverage_id)
            date_intervals = [item for item in intelligence["date_coverages"] if item["source"]["page"] == coverage["page"]]
            dates = date_intervals[0] if len(date_intervals) == 1 else None
            if dates:
                if coverage.get("date_reviewer"):
                    for date_record in (doc.get("date_coverage"), *doc.get("date_coverages", [])):
                        if date_record and date_record["source"]["page"] == coverage["page"]:
                            date_record.update(date_from=coverage["date_from"], date_to=coverage["date_to"], status=coverage["date_coverage_status"])
                    continue
                coverage.update(date_from=dates["date_from"], date_to=dates["date_to"], date_source=dates["source"], date_coverage_status="PROBABLE")
                store.put("coverage", coverage)
                store.put("review", {"id": "REV-"+coverage_id+"-DATES-"+VERSION, "kind": "coverage", "entity_id": coverage_id,
                    "document_id": doc["id"], "status": "PENDING", "reason": "Confirm newly extracted date coverage", "priority": "MEDIUM"})
        if intelligence["review_reasons"]:
            store.put("review", {"id": "REV-"+doc["id"], "kind": "document", "entity_id": doc["id"], "document_id": doc["id"],
                "status": "PENDING", "reason": "; ".join(intelligence["review_reasons"]), "priority": "HIGH"})
            if doc["review_status"] != "QUARANTINED":
                doc["review_status"] = "NEEDS_REVIEW"
        store.put("document", doc)
        stamp = datetime.now(timezone.utc).isoformat()
        store.put("audit", {"id": "DOC-UPGRADE-"+doc["id"]+"-"+VERSION, "timestamp": stamp,
            "reviewer": "SYSTEM_DOCUMENT_UPGRADE", "action": "enrich_metadata_preserve_reviews", "entity_id": doc["id"],
            "before": before, "after": doc})
        changed += 1
    return changed


if __name__ == "__main__":
    print(f"Enriched {upgrade_documents(repository())} retained documents")
