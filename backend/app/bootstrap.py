"""Offline field installation and report ingestion. Does not expose evaluation truth."""
import json
from pathlib import Path
from .generator import main as generate
from .store import repository
from .ingestion import ingest, VERSION
from .paths import DATA_ROOT


def main():
    generate()
    from .gold_set import author as author_gold
    if not (DATA_ROOT/"gold"/"labels.json").exists():
        author_gold(DATA_ROOT/"gold")
    store = repository()
    from .upgrade_documents import upgrade_documents
    upgrade_documents(store)
    manifest = DATA_ROOT/"runtime"/"reports"/"manifest.json"
    count = 0
    for item in json.loads(manifest.read_text(encoding="utf-8")):
        path = Path(item["path"])
        title = path.name
        # Generated reports are versioned fixtures; regenerating PDF trailer IDs must not
        # create a second historical observation or discard a human review.
        candidates = [doc for doc in store.all("document") if doc["synthetic"] and
                      doc["well_id"] == item["well_id"] and doc["title"] == path.name]
        def reviewed(doc):
            return any(store.get("event", key).get("reviewer") for key in doc["event_ids"]) or any(store.get("coverage", key).get("reviewer") for key in doc["coverage_ids"])
        # Ingest the current fixture, retaining human-reviewed source records for audit.
        # Repeating an identical generation reuses its content-addressed document.
        doc = ingest(store, path.read_bytes(), title, item["well_id"], synthetic=True)
        for prior in candidates:
            if prior["id"] != doc["id"] and not reviewed(prior):
                store.put("document", {**prior, "superseded_by": doc["id"]})
        count += 1
        print(f"Ingested {title}: {len(doc['event_ids'])} events; {'OCR' if doc['is_scan'] else 'native'}")
    print(f"Ready: {count} documents")
    from .upgrade_mud_events import upgrade_mud_events
    print(f"Enriched {upgrade_mud_events(store)} historical mud-loss contexts")


if __name__ == "__main__": main()
