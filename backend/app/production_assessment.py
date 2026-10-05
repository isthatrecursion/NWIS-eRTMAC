"""Repeatable local concurrency probe and candid production-readiness assessment."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import time
from urllib.request import Request, urlopen

from .paths import DATA_ROOT


def probe(base_url: str, requests: int = 300, workers: int = 32):
    paths = ("/health", "/api/v1/meta", "/api/v1/wells", "/api/v1/documents")

    def one(index):
        started = time.perf_counter()
        try:
            with urlopen(Request(base_url.rstrip("/") + paths[index % len(paths)], headers={"Accept": "application/json"}), timeout=15) as response:
                response.read()
                return response.status, (time.perf_counter() - started) * 1000, None
        except Exception as exc:  # reported rather than hidden
            return 0, (time.perf_counter() - started) * 1000, type(exc).__name__

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = [future.result() for future in as_completed([executor.submit(one, index) for index in range(requests)])]
    latencies = sorted(row[1] for row in results)
    return {
        "requests": requests, "workers": workers,
        "successes": sum(row[0] == 200 for row in results),
        "failures": sum(row[0] != 200 for row in results),
        "p50_ms": round(statistics.median(latencies), 2),
        "p95_ms": round(latencies[min(len(latencies) - 1, int(len(latencies) * .95))], 2),
        "max_ms": round(max(latencies), 2),
        "errors": sorted({row[2] for row in results if row[2]}),
    }


def write_probe(base_url: str, requests: int = 60, workers: int = 8):
    payload = json.dumps({"question": "What historical mud loss events occurred in TIPAM?"}).encode()

    def one(_):
        started = time.perf_counter()
        try:
            request = Request(base_url.rstrip("/") + "/api/v1/ask", data=payload,
                              headers={"Accept": "application/json", "Content-Type": "application/json"}, method="POST")
            with urlopen(request, timeout=30) as response:
                response.read()
                return response.status, (time.perf_counter() - started) * 1000, None
        except Exception as exc:
            return 0, (time.perf_counter() - started) * 1000, type(exc).__name__

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = [future.result() for future in as_completed([executor.submit(one, index) for index in range(requests)])]
    latencies = sorted(row[1] for row in results)
    return {"requests": requests, "workers": workers, "successes": sum(row[0] == 200 for row in results),
            "failures": sum(row[0] != 200 for row in results), "p50_ms": round(statistics.median(latencies), 2),
            "p95_ms": round(latencies[min(len(latencies)-1, int(len(latencies)*.95))], 2),
            "max_ms": round(max(latencies), 2), "errors": sorted({row[2] for row in results if row[2]})}


def assess(base_url: str, compose_path: Path, requests: int, workers: int):
    compose = compose_path.read_text(encoding="utf-8")
    concurrency = probe(base_url, requests, workers)
    write_concurrency = write_probe(base_url)
    blockers = [
        {"id": "AUTHN_AUTHZ", "status": "OPEN", "detail": "No production identity, role or tenant authorization layer is implemented."},
        {"id": "TLS_EDGE", "status": "OPEN", "detail": "TLS termination and managed certificates are deployment responsibilities and are not configured here."},
        {"id": "SECRETS", "status": "OPEN" if "POSTGRES_PASSWORD: nwis" in compose else "REVIEW", "detail": "Development Compose uses demo credentials; production must use an external secret provider."},
        {"id": "RATE_LIMIT", "status": "OPEN", "detail": "No production rate limiting or abuse controls are implemented."},
        {"id": "HA_BACKUP", "status": "OPEN", "detail": "Restore drills, database backups, failover and multi-instance coordination have not been validated."},
        {"id": "SCA_PEN_TEST", "status": "OPEN", "detail": "Independent dependency scanning and penetration testing remain external activities."},
    ]
    return {
        "id": "production-security-concurrency-local-v1", "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Local synthetic deployment; this is engineering evidence, not production certification",
        "concurrency": concurrency, "write_concurrency": write_concurrency,
        "concurrency_result": "PASS" if concurrency["failures"] == 0 and write_concurrency["failures"] == 0 else "FAIL",
        "production_readiness": "NOT_PRODUCTION_READY",
        "positive_controls": ["parameterized SQLAlchemy persistence", "request correlation IDs", "structured error envelopes", "security response headers", "upload size and type controls", "no rig write-back", "uploaded text has no tool access"],
        "blockers": blockers,
        "limitations": ["Load probe covers read endpoints and deterministic Ask audit writes on one local host", "No destructive, stress-to-failure or internet-facing test was performed"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--compose", default=str(Path(__file__).resolve().parents[2] / "docker-compose.yml"))
    parser.add_argument("--requests", type=int, default=300)
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--output", default=str(DATA_ROOT / "validation" / "production-assessment.json"))
    args = parser.parse_args()
    report = assess(args.base_url, Path(args.compose), args.requests, args.workers)
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
