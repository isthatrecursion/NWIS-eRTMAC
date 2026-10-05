# Foundation and synthetic-field completion pass

Scope: the supplied Phase 0 and Phase 1A gap list. This pass does not certify unrelated phases 1B–6.

Implemented:

- Shared Pydantic storage contracts for wells, survey stations, formations, mud/casing programmes, documents/pages, extracted events, coverage, source spans, trajectories, reviews, alignment, transferability, evidence snapshots, replay datasets/sessions, alerts and audit records. Storage validates registered entity types. Engine extension fields remain supported for compatibility.
- Dedicated cause-type and extraction-confidence enums. TypeScript and JSON Schema are generated from Pydantic with `python -m app.export_contracts`; CI checks for drift. Frontend API types use generated contracts.
- Canonical metres, specific gravity, and kPa conversions; source quantities, units, datums and MD/TVD references are preserved in measurement records. Coverage boundaries preserve their raw units. Document ECD/density/pressure labels and manual telemetry support conversion. Unsupported units cannot become trusted live quantities. Unspecified datums stay `UNKNOWN`; no automatic datum transformation is implied.
- Alembic baseline migration, persisted `alembic_version`, legacy SQLite table adoption, and PostgreSQL/PostGIS spatial initialization under migration control. Run `python -m app.migrate` from `backend`; repository initialization also upgrades to head.
- `/api/v1` routes with legacy `/api` compatibility aliases. Frontend requests use v1. HTTP, validation and unexpected errors use a consistent envelope with `X-Request-ID`; request logs include method, path, status and duration. Errors retain `detail` for frontend compatibility.
- Basic Ruff correctness lint, frontend TypeScript checks, backend tests, frontend production build, generated-contract drift check, and a separate fresh Docker/PostGIS smoke job.
- Deterministic planting of mud loss, stuck pipe, kick/influx, torque dysfunction and cementing issues. A separate event random stream preserves the established geometry and mud-loss fixture.
- Offline `truth.json`, `held_out_events.json`, `expected_intervals.json`, and `generator_metadata.json`. Expected intervals are synthetic event-depth envelopes with a declared 10 m tolerance, not calibrated predictions. Runtime APIs never load evaluation manifests.
- Mixed DDR and WCR reports, structured operational tables, a separate WCR formation/casing summary table, feet/metres and ppg/sg variants, native PDFs, scanned PDFs and controlled scan noise. OCR events continue to require review.
- `synthetic_flag` on generated and persisted nested entity records, retaining legacy `synthetic` compatibility. Numeric channel maps and other keyed maps preserve their existing shape. Reviewed historical document versions remain retained; obsolete unreviewed versions of regenerated sources are superseded.

Verification limitation: Docker is absent on this machine, including its standard Windows installation path. The clean Docker/PostgreSQL/PostGIS smoke is implemented in CI but has not been executed locally. SQLite is still the locally used database. CI execution itself requires pushing this workspace to a GitHub repository; this workspace currently has no Git repository metadata.

Local verification on 4 October 2026: 72 backend tests passed; Ruff correctness lint, generated-contract drift verification, frontend TypeScript check and production build passed. Bootstrap completed twice with 24 wells, 12 current report fixtures and two scanned reports. A pre-refresh SQLite backup is retained as `backend/nwis.pre-foundation-completion.db`. Existing reviewed source records remain retained alongside current fixtures.

Clean-stack verification on a Docker-capable host:

```powershell
docker compose -p nwis-clean-check up --build -d --wait --wait-timeout 300
docker compose -p nwis-clean-check exec -T backend python -m app.smoke_postgis
```

The project name creates a separate stack and database volume. After inspection, its disposable stack can be removed with `docker compose -p nwis-clean-check down -v`.
