"""CLI-only seed for a separate packaged-demo database; never clears user data."""
import json
from .generator import build_field
from .store import repository
from .live_routes import demo, reset_session
from .paths import DATA_ROOT


def main():
    store = repository()
    field, _ = build_field(seed=121)
    for well in field["wells"]:
        if store.get("well",well["id"]) is None: store.put("well",well)
    result = demo()
    store.put("demo_config", {"id":"DEMO-CONFIG", "session_id": result["session"]["id"], "seed":121, "version":"demo-seed/1.0", "synthetic_flag":True})
    # Package already measured aggregate reports; no offline truth is served.
    source = DATA_ROOT.parent
    for kind, path in [("benchmark_report",source/"benchmark/evaluation/results.json"), ("extraction_report",source/"gold/results.json"), ("engineering_report",source/"validation/engineering.json"), ("safety_report",source/"validation/safety.json")]:
        if path.exists(): store.put(kind,json.loads(path.read_text(encoding="utf-8")))
    print(json.dumps({"session_id":result["session"]["id"],"well_id":result["session"]["well_id"],"state":result["assessment"]["corroboration"]["state"]}))


if __name__ == "__main__": main()
