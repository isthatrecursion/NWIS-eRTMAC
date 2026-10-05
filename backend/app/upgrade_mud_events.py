"""Add source-grounded severity and intervals while retaining reviewed depth edits."""
from copy import deepcopy
from datetime import datetime, timezone
from .ingestion import extract

VERSION = "mud-event-context/1.1"


def upgrade_mud_events(store):
    changed = 0
    for doc in store.all("document"):
        for page in doc.get("page_data", []):
            parsed = None
            for key in doc.get("event_ids", []):
                event = store.get("event", key)
                span = store.get("source_span", event["source_span_id"])
                if event["event_type"] != "MUD_LOSS" or event.get("mud_context_version") == VERSION or span["page"] != page["page"]:
                    continue
                if parsed is None: parsed = extract(page)
                found = next((row for row in parsed if row["event_type"] == "MUD_LOSS" and row["source_text"] == span["text"]), None)
                if not found: continue
                before = deepcopy(event)
                for field, value in found.get("context_values", {}).items():
                    event.setdefault("context_values", {}).setdefault(field, value)
                for field, value in found.get("numerical_fields", {}).items():
                    event.setdefault("numerical_fields", {}).setdefault(field, value)
                if event.get("severity", "UNKNOWN") == "UNKNOWN": event["severity"] = found["severity"]
                if found.get("event_md_interval_m"):
                    if event["md_from_m"] == found["md_from_m"] and not event.get("event_md_interval_m"):
                        event["event_md_interval_m"] = found["event_md_interval_m"]
                        event["md_to_m"] = found["md_to_m"]
                        event.setdefault("measurements", {})["md_to_m"] = deepcopy(found["measurements"]["md_to_m"])
                    elif event["md_from_m"] != found["md_from_m"]:
                        store.put("review", {"id": "REV-MUD-INTERVAL-"+key, "kind": "event", "entity_id": key, "document_id": doc["id"],
                            "status": "PENDING", "priority": "HIGH", "reason": "New source interval conflicts with reviewed event depth; confirm interval endpoints"})
                for field in ("severity", "event_md_interval_m"):
                    if field in found["field_evidence"]: event.setdefault("field_evidence", {}).setdefault(field, found["field_evidence"][field])
                event["mud_context_version"] = VERSION
                store.put("event", event)
                store.put("audit", {"id": "MUD-UPGRADE-"+key, "timestamp": datetime.now(timezone.utc).isoformat(),
                    "reviewer": "SYSTEM_SOURCE_ENRICHMENT", "action": "add_source_severity_interval_preserve_review", "entity_id": key, "before": before, "after": event})
                changed += 1
    return changed


if __name__ == "__main__":
    from .store import repository
    print(f"Enriched {upgrade_mud_events(repository())} historical mud-loss events")
