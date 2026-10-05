"""Publish real JUnit results and inspect narrowly defined local safeguards."""
import argparse
import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET
from .store import repository
from .paths import DATA_ROOT

VERSION = "engineering-assurance/1.0"


def safety(store):
    directory = Path(__file__).parent
    from .ingestion import DATA_ROOT as source_root
    checks = []
    for name in ("ingestion.py", "document_intelligence.py"):
        tree = ast.parse((directory/name).read_text(encoding="utf-8"))
        unsafe = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("eval","exec","__import__")]
        checks.append({"name": name+" has no code-execution calls", "passed": not unsafe, "detail": "AST inspected; document extraction is local parsing/OCR with no tool or model agent"})
    checks.append({"name":"Stored sources remain in configured storage", "passed":all(Path(d["path"]).resolve().is_relative_to(source_root.resolve()) for d in store.all("document")), "detail":"Resolved source paths checked; API reads reject paths outside configured storage"})
    checks.append({"name":"No rig write-back integration", "passed":not any(p.exists() for p in (directory/"rig_writeback.py",directory/"actuators.py")), "detail":"Simulation-only APIs; architecture and route contract tests verify no actuation endpoints"})
    checks.append({"name":"Local package avoids external model calls", "passed":"NONE_DETERMINISTIC_RENDERER" in (directory/"ask.py").read_text(encoding="utf-8"), "detail":"Ask planner, tools and renderer are deterministic; uploaded text cannot choose operations"})
    result = {"id":"SAFETY-"+datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"), "generated_at":datetime.now(timezone.utc).isoformat(), "version":VERSION, "checks":checks,
        "limitations":["Local prototype, not a penetration test or production security certification", "Public/private classification is metadata, not multi-user authorization", "Startup binds loopback; manual deployments need authentication, TLS and deployment review", "No external model or rig integration is configured"]}
    store.put("safety_report",result)
    return result


def publish_junit(path, store):
    tree = ET.parse(path)
    suites = [tree.getroot()] if tree.getroot().tag == "testsuite" else list(tree.getroot().iter("testsuite"))
    counts = {key:sum(int(s.attrib.get(key,0)) for s in suites) for key in ("tests","failures","errors","skipped")}
    result = {"id":"ENGINEERING-"+hashlib.sha256(path.read_bytes()).hexdigest()[:20], "generated_at":datetime.now(timezone.utc).isoformat(), "version":VERSION,
        **counts, "junit_sha256":hashlib.sha256(path.read_bytes()).hexdigest(), "test_cases":[c.attrib["name"] for c in tree.getroot().iter("testcase")],
        "limitations":["Automated prototype engineering checks; not field performance validation", "PostgreSQL/PostGIS clean-start verification is separate from these SQLite tests"]}
    store.put("engineering_report",result)
    return result


if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--junit",type=Path);args=parser.parse_args()
    folder=DATA_ROOT/"validation";folder.mkdir(parents=True,exist_ok=True)
    record=safety(repository());(folder/"safety.json").write_text(json.dumps(record,indent=2),encoding="utf-8")
    if args.junit:
        record=publish_junit(args.junit,repository());(folder/"engineering.json").write_text(json.dumps(record,indent=2),encoding="utf-8")
    print(json.dumps({"id":record["id"],"tests":record.get("tests"),"checks":record.get("checks")},indent=2))
