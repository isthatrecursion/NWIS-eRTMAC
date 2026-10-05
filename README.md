# eRTMAC-NWIS prototype

Phases 0–10 of the Nearby Wells Intelligence System prototype (including the Phase 0.5 frontend).

## What is implemented

- Canonical backend contracts, enums, unit conventions, configuration, and versioned APIs.
- Persisted field, survey, formation, event, coverage, source-span, review, and audit records.
- Deterministic 24-well field with deviated trajectories, missing records, and isolated hidden truth.
- Twelve mixed DDR/WCR reports with structured tables, all five event families, unit variants, and two image-only PDFs processed by local OCR.
- Grounded extraction, feet-to-metres normalization, source highlights, coverage review, and event correction.
- Minimum-curvature trajectories, surface radius filtering, downhole separation, and uncertainty-aware formation projection.
- Explainable analog selection and risk-specific transferability with trusted-domain gates, missing-context penalties and source provenance.
- Coverage-aware support/counter/unknown populations, one contribution per well, weighted internal statistics and historical evidence states.
- Validated replay/CSV/manual adapters, canonical current context, source precedence/conflicts and per-channel freshness.
- Historical plus fresh-signal mud-loss gates, persisted alert deduplication, acknowledgement, snooze, escalation and resolution.
- SQLite for local use and a PostgreSQL/PostGIS storage path for Docker deployments.
- Complete React frontend shell with a deterministic mock scenario.
- Next Interval Brief, map, comparison, evidence, documents, review, Ask NWIS, validation, rig, and settings routes.
- Interactive replay, risk-state transitions, stale-channel failure injection, radius filtering, alert acknowledgement, and provider switching.

Documents, Review, Offset wells, Formation compare, Evidence, Next interval brief, Rig view, Ask NWIS and Validation consume backend results in connected mode. Overview now shows live database counts and synthetic/non-synthetic record flags from `/api/meta`, plus the loaded report links and formation-gazetteer count. These flags describe stored records; they do not verify field origin. Ask NWIS uses a local deterministic planner and renderer with allowlisted read-only tools and numeric verification. Validation reports measured synthetic results, including misses and false warnings. The mock provider remains available and labeled. All thresholds are uncalibrated prototype policy, not validated field prediction.

## Repeatable local demo

From the project root run `./Start-Demo.ps1`, then open `http://127.0.0.1:8765/#brief`. This serves the prebuilt frontend and API on one loopback port, creates a separate demo database, and restores a seeded synthetic replay. Use the controlled failure buttons to reset, reach Elevated, make flow-out stale, restore fresh signals, and pass the interval.

`./Prepare-Offline.ps1` caches pinned Python wheels; `./Prepare-Offline.ps1 -InstallFromCache` installs without an index. The Windows x64 ZIP includes Python 3.12, prebuilt frontend, wheels and bundled OCR models. On a fresh extraction, `Start-Demo.ps1` creates its environment from those local assets automatically. Node is needed only for rebuilding the frontend; rebuilding needs prepared npm dependencies. See [Phase 9–10 implementation](docs/PHASE_9_10.md), [five-minute demo](docs/DEMO_SCRIPT.md), [claim ledger](docs/CLAIM_LEDGER.md) and [architecture](docs/ARCHITECTURE.md).

## Run the frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Run the backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m app.bootstrap
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

API documentation is available at `http://localhost:8000/docs`.

## Data-provider modes

Settings switches between:

- `MOCK`: browser-local, deterministic Phase 0.5 scenario.
- `SYNTHETIC`: persisted generated field and ingested reports (default).
- `API`: the same configured backend as `SYNTHETIC`, also supporting uploaded reports; selecting it does not obtain external field data.

Pages whose engines belong to later phases retain an explicit workflow-preview notice.

Set `VITE_API_BASE_URL` to use another backend origin. The default is `http://127.0.0.1:8000`.

## Docker

`docker compose up --build` configures PostgreSQL/PostGIS, runs bootstrap, and starts both applications. A clean isolated startup has been verified locally on Docker Desktop 4.93.0, including migrations, PostGIS, generated data, API/frontend health and spatial trajectory persistence. The evidence is in `storage/validation/docker-postgis.json`.

## Phase boundary

Phases 0–10 are implemented as a synthetic decision-support prototype. Regular historical reports retain review gates. In Next interval brief, **Load full mud-loss demo** installs an isolated synthetic acceptance scenario with usable evidence; select 10× or 20× and Play to see Lesson → Elevated → Warning → Resolved. Backend controls support pause, reset, seek and streaming. Rig view restores the same run. Real-rig integration, independent field calibration, human gold-set sign-off, multi-user production security and user-study results remain external gates.

## Verify

```powershell
cd backend
.venv\Scripts\python -m pytest tests -q
cd ..\frontend
npm run build
```

## Data locations

- `backend/nwis.db`: local persisted records.
- `storage/runtime/reports`: generated source reports.
- `storage/runtime/uploads`: retained ingestion sources.
- `storage/evaluation/`: offline truth, held-out events, expected intervals and generator metadata, never read by runtime API modules.

Re-running bootstrap is idempotent for the configured field and preserves reviewed observations. Superseded development fixtures remain stored but are excluded from active lists and evidence populations.

See [Phase 1–2 implementation notes](docs/PHASE_1_2.md) for API routes, algorithms, and current limits.

See [Phase 3–4 implementation notes](docs/PHASE_3_4.md) for transferability and evidence policy.

See [Phase 5–6 implementation notes](docs/PHASE_5_6.md) for adapters, clocks, warning gates, lifecycle and verification.

See [Foundation and synthetic-field completion](docs/FOUNDATION_SYNTHETIC_COMPLETION.md) for the Phase 0/1A gap fixes, migration and contract commands, CI checks, and Docker verification details.

See [Document, geometry and transferability completion](docs/DOCUMENT_GEOMETRY_TRANSFER_COMPLETION.md) for the Phase 1B–3 gap fixes, sourced gazetteer, numerical grounding, datum uncertainty and implemented risk-context comparisons.

See [Replay and mud-loss completion](docs/REPLAY_MUD_LOSS_COMPLETION.md) for the complete demo, per-channel freshness, backend controls, configured warning policy, sourced severity/intervals and cross-run alert deduplication.

See [Phase 7–8](docs/PHASE_7_8.md) for secondary module maturity, the integrated field/office views, source tracing, and actual offline validation results and limits.
