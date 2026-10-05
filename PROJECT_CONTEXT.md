# NWIS project context

This file is a handoff snapshot based on the code, tests, generated artifacts, and the original `Phase by Phase Implementation Plan 121.txt`. Status means: ✅ implemented and exercised in this repository; ⚠️ implemented with a material limitation; ❌ absent; 🧪 synthetic, simulated, or otherwise not validated on field data.

## 1. Project in brief

NWIS is a prototype drilling look-ahead decision-support system for rig and office users. It combines offset-well documents, trajectories, formations, event history, transferability rules, and replayed live drilling signals to explain upcoming risk. Mud loss is the polished vertical slice. Stuck pipe, kick/influx, torque dysfunction, and cementing are deliberately lower-maturity modules. All supplied data is synthetic; the product has no rig write-back.

The backend is Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PyMuPDF, RapidOCR/ONNX Runtime, NumPy, and Shapely. Storage is SQLite for the one-command local demo and PostgreSQL 16/PostGIS 3.4 in Docker. The frontend is React 19, TypeScript, and Vite. The UI uses a custom hash router rather than React Router. Ask NWIS is a deterministic rule-based planner and renderer; no external LLM or API key is used.

### Install and run

The shortest Windows path is:

```powershell
cd "C:\Users\omkud\SIH 121 Prototype"
.\Start-Demo.ps1
```

Open `http://127.0.0.1:8765/#brief`. The script creates `backend\.venv` from the offline wheel cache when necessary, builds the frontend when necessary, uses `storage\demo\nwis-demo.db`, seeds deterministic data, and starts one loopback Uvicorn worker. Use `.\Start-Demo.ps1 -Rebuild` to force a frontend rebuild.

To create or refresh the offline dependency cache while network access is available:

```powershell
.\Prepare-Offline.ps1
.\Prepare-Offline.ps1 -InstallFromCache
```

Manual backend development:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.bootstrap
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Manual frontend development in a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/#brief`. The Vite client uses `http://127.0.0.1:8000` by default in development.

Docker/PostGIS:

```powershell
cd "C:\Users\omkud\SIH 121 Prototype"
docker compose up --build
```

The Docker frontend is at `http://127.0.0.1:5173/#brief`, the API is at `http://127.0.0.1:8000`, and PostgreSQL is exposed at port 5432 with the development-only credentials in `docker-compose.yml`. A clean-start run was completed and recorded in `storage/validation/docker-postgis.json`.

Verification commands:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m app.export_contracts --check
cd ..\frontend
npm run lint
npm run build
```

No API keys are required. Configuration is read by `backend/app/config.py`:

- `NWIS_ENVIRONMENT`: environment label.
- `NWIS_DEMO_MODE`: enables demo-oriented behavior.
- `NWIS_SERVE_FRONTEND`: lets FastAPI serve `frontend/dist`.
- `NWIS_DATABASE_URL`: SQLAlchemy URL. Omit it to use the configured SQLite path; Docker supplies PostgreSQL.
- `NWIS_CORS_ORIGINS`: comma-separated allowed origins.
- `NWIS_CHANNEL_FRESHNESS_S`: JSON object of per-channel freshness thresholds.
- `NWIS_MUD_LOSS_POLICY`: JSON mud-loss live policy.
- `NWIS_HISTORICAL_POLICY`: JSON historical-evidence policy.
- `VITE_API_BASE_URL`: frontend API origin at build/dev time.
- `VITE_MAP_TILE_URL`: optional frontend map-tile URL template with `{z}`, `{x}`, and `{y}`; defaults to OpenStreetMap's standard HTTPS tiles.

Known configuration defect: `.env.example` declares `NWIS_ENV`, while `Settings` reads `NWIS_ENVIRONMENT`. Rename the example variable before relying on it.

## 2. Architecture in one view

### Important folders and files

| Path | Purpose |
|---|---|
| `backend/app/main.py` | FastAPI application, core HTTP routes, middleware registration, and `/api/v1` route cloning. |
| `backend/app/domain/` | Shared enums, Pydantic contracts, runtime record models, measurements, and unit normalization. |
| `backend/app/store.py` | SQLAlchemy repository over generic JSON records plus PostGIS trajectory storage. |
| `backend/app/migrate.py`, `backend/migrations/` | Alembic migration entry point and the baseline schema/PostGIS migration. |
| `backend/app/generator.py` | Deterministic synthetic field, hidden truth, manifests, and report generation. |
| `backend/app/ingestion.py`, `document_intelligence.py` | Upload handling, native text/OCR routing, layout analysis, extraction, grounding, aliases, and review creation. |
| `backend/app/geometry.py` | Minimum-curvature trajectories, separation, formation projection, fallbacks, and uncertainty bounds. |
| `backend/app/transfer_context.py`, `evidence.py` | Analog cascade, risk-specific transferability, clean crossings, weighted evidence, and deterministic summaries. |
| `backend/app/live.py`, `live_routes.py`, `mud_loss.py` | Live context, replay/CSV/manual adapters, freshness, playback/WebSocket control, mud-loss corroboration, and alert lifecycle. |
| `backend/app/secondary.py` | Stuck-pipe, kick, torque/dysfunction, and cementing support modules. |
| `backend/app/workflow.py` | Next Interval Brief, compare/ranking-swap, evidence chain, and validation routes/view models. |
| `backend/app/ask.py` | Deterministic Ask NWIS planning, tool execution, answer sections, source retrieval, number verification, and routes. |
| `backend/app/*validation*.py`, `gold_set.py`, `production_assessment.py`, `assurance.py` | Gold set, held-out replay, baselines, external validation scaffolding, bounded concurrency assessment, and safety checks. |
| `backend/tests/` | Unit, API, replay, provenance, security, PostgreSQL, and validation tests. |
| `frontend/src/App.tsx` | Shell, navigation, provider mode, and custom hash routing. |
| `frontend/src/IntegratedPages.tsx` | Offset, alignment, document, and review workspaces. |
| `frontend/src/LiveWorkspace.tsx` | Next Interval Brief, replay controls, live state, alert handling, and simplified rig view. |
| `frontend/src/WorkflowWorkspace.tsx` | Depth strip, planning integration, evidence explorer, secondary modules, and validation workspace. |
| `frontend/src/AskWorkspace.tsx` | Ask NWIS question/plan/answer/source UI. |
| `frontend/src/IndependentValidation.tsx` | Human gold review, usability study, and external field-validation status. |
| `frontend/src/api.ts` | Typed fetch helpers and `/api` to `/api/v1` rewriting. |
| `frontend/src/generated-contracts.ts` | TypeScript definitions generated from Pydantic schemas. Do not edit manually. |
| `storage/runtime/` | Generated runtime data, documents, and local persisted records. |
| `storage/evaluation/` | Hidden truth, held-out events, expected intervals, and generator metadata; runtime risk code does not read these. |
| `storage/gold/`, `storage/benchmark/`, `storage/validation/` | Gold labels/results, blind replay/baselines, and engineering/security/deployment results. |
| `docs/` | Architecture, claim ledger, demo script, validation protocols, screenshots, and backup demonstration video. |
| `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile` | Three-service development/demo Docker stack. |
| `Start-Demo.ps1`, `Prepare-Offline.ps1` | One-command demo and offline dependency preparation. |
| `.github/workflows/ci.yml` | Python checks/tests, generated-contract check, frontend checks, and clean PostGIS CI. |

### Data flow

The React page calls typed helpers in `frontend/src/api.ts`. FastAPI routes in `backend/app/main.py`, `backend/app/live_routes.py`, `backend/app/workflow.py`, `backend/app/ask.py`, and `backend/app/independent_validation.py` validate requests and call deterministic modules. Those modules read and write Pydantic-validated records through `backend/app/store.py`; SQLite stores JSON locally, while PostgreSQL stores the same records and PostGIS trajectory geometry. Responses return source links, evidence roles, calculations, freshness, uncertainty, and alerts to React. The UI renders FACT, COMPUTED, and INFERRED labels and can follow an alert through evidence, transfer assessment, historical event, source span, and document page.

## 3. Phase-by-phase breakdown

### Phase 0: Foundation

**Goal:** Establish shared contracts, units, persistence, API/UI skeletons, reproducible startup, and automated checks.

**What was done:**

- **0.1 Repository structure — ✅ Done.** Backend, frontend, storage, migrations, docs, scripts, and CI are separated at the root.
- **0.2 Canonical contracts — ✅ Done.** `domain/contracts.py` defines shared live contracts; `domain/runtime.py` validates stored runtime entities. Some extensible payloads intentionally allow extra fields and nested dictionaries.
- **0.3 Enums — ✅ Done.** Risk/event, evidence, provenance, operation, freshness, review, coverage, alert, extraction-confidence, and cause-type enums are in `domain/enums.py`.
- **0.4 Units and datum — ✅ Done.** Depth, density, and pressure values are normalized while original value, unit, datum/reference, source, version, and `synthetic_flag` are retained. Unsupported or mismatched datums block relevant geometry calculations.
- **0.5 Persistence and migrations — ✅ Done.** SQLite and PostgreSQL/PostGIS use the same SQLAlchemy repository. Alembic creates `nwis_records`, PostGIS trajectory storage, and indexes. There is one baseline migration; records are primarily JSON documents rather than a normalized relational schema.
- **0.6 API/UI skeleton — ✅ Done.** FastAPI supplies consistent errors, request IDs, logging, CORS/security headers, `/api/v1`, and legacy `/api` aliases. React supplies design tokens, loading/error states, responsive navigation, and an API client. One synthetic active well is seeded.
- **0.7 Reproducible environment — ✅ Done.** Docker Compose, one-command Windows startup, deterministic bootstrap, an offline wheel/runtime bundle, and clean-start evidence exist.
- **Completion checks — ✅ Done.** CI and local artifacts cover Ruff, Pytest, contract drift, frontend lint/build, and PostgreSQL/PostGIS startup.

**Where in the code:** `backend/app/domain/contracts.py`, `backend/app/domain/runtime.py`, `backend/app/domain/enums.py`, `backend/app/domain/units.py`, `backend/app/store.py`, `backend/app/api_support.py`, `backend/app/config.py`, `backend/app/main.py`, `backend/app/export_contracts.py`, `backend/migrations/versions/0001_foundation.py`, `frontend/src/api.ts`, `frontend/src/generated-contracts.ts`, `.github/workflows/ci.yml`, `docker-compose.yml`, `Start-Demo.ps1`.

**Where it shows on the site:** Every page depends on it. `/#settings` exposes frontend provider/presentation choices; health and version metadata are backend-only through `/health` and `/api/v1/meta`.

**What it does for the user:** The user starts one repeatable application, receives typed API responses and consistent failures, and sees measurements with traceable units and provenance.

**Depends on:** Nothing earlier.

### Phase 1: Synthetic field and document intelligence

**Goal:** Supply a deterministic synthetic field and convert its reports into grounded, reviewable structured records.

**What was done:**

- **1A.1 Field population — 🧪 Mocked.** `generator.py` creates 24 synthetic wells by default with coordinates, trajectories, formations, uncertainty, casing, mud programmes, events, clean/missing coverage, and `synthetic_flag`.
- **1A.2 Directional surveys — 🧪 Mocked.** Stations contain MD, inclination, and azimuth at regular intervals.
- **1A.3 Geology — 🧪 Mocked.** Formation tops/thickness vary laterally; uncertainty is explicit; one well omits a formation and another requires approximate thickness fallback.
- **1A.4 Event mix — 🧪 Mocked.** Mud loss, stuck pipe, kick/influx, torque dysfunction, and cementing problems are all generated.
- **1A.5 Hidden causes — ✅ Done.** Weakness/latent causal values are written only to evaluation truth; runtime evidence code does not query them.
- **1A.6 Evaluation manifests — ✅ Done.** Separate `hidden_truth.json`, `held_out_events.json`, `expected_intervals.json`, and `generator_metadata.json` are written under `storage/evaluation`.
- **1A.7 Reports — 🧪 Mocked.** Current generation writes 12 manifest-controlled alternating DDR/WCR PDFs, including tables, unit variation, formatting noise, watermarks, and two image-only scans. The report directory can retain stale PDFs from older runs; bootstrap ingests only the manifest.
- **1B.1 Ingestion metadata — ✅ Done.** Native PDF, image-only PDF, and text uploads are supported with well association, explicit report type, title, page count, scan status, synthetic status, and PUBLIC/PRIVATE classification. Classification is metadata only; authorization is not implemented.
- **1B.2 Native text and OCR — ✅ Done.** PyMuPDF text is preferred; low-text pages use RapidOCR.
- **1B.3 Layout — ⚠️ Partial.** Page/line boxes, header, section, table, daily-section, and depth-column heuristics are implemented. They are deterministic heuristics tuned to the supplied reports, not a general document-layout model.
- **1B.4 Field extraction — ✅ Done.** Rules cover dates, measured depths/ranges, units, well-name validation, formations, mud weight, hole size, and a bounded drilling-abbreviation dictionary.
- **1B.5 Event chain — ✅ Done.** Runtime models capture observed event, response/mitigation, result/outcome, source spans, confidence, review status, and context.
- **1B.6 Numeric grounding — ✅ Done.** Supported extracted numbers must occur in the cited span or be an explicit unit conversion; derived values carry provenance.
- **1B.7 Formation gazetteer — ✅ Done.** Canonical names, aliases, basin, source URL, match confidence, and fuzzy candidates are stored; ambiguous matches enter review.
- **1B.8 Confidence and review — ✅ Done.** Field confidence, review status, correction, acceptance, rejection/quarantine, and audit records exist. Quarantined events are excluded from active evidence.
- **1B.9 Coverage ledger — ✅ Done.** Interval and date coverage can be COMPLETE, PARTIAL, UNKNOWN, or reviewed negative; this is what permits clean crossings.

**Where in the code:** `backend/app/generator.py`, `backend/app/bootstrap.py`, `backend/app/ingestion.py`, `backend/app/document_intelligence.py`, `backend/app/domain/runtime.py`, document/review routes in `backend/app/main.py`; generated data in `storage/runtime`, `storage/evaluation`, and `storage/gold`.

**Where it shows on the site:** `/#documents` lists documents, page images, source highlighting, fields, confidence, and status. `/#review` supports review and corrections. Document evidence also opens from `/#evidence`, `/#ask`, and `/#rig`.

**What it does for the user:** A report is uploaded or seeded, split into pages, OCRed when needed, converted to reviewable events and coverage, and linked back to the exact page/span used by later risk explanations.

**Depends on:** Phase 0 contracts, units, storage, and API conventions.

### Phase 2: Geometry and formation alignment

**Goal:** Compare wells at the relevant subsurface interval and expose calculation method and uncertainty.

**What was done:**

- **2.1 Trajectory geometry — ✅ Done.** Minimum curvature calculates TVD, north/east displacement, 3D coordinates, and dogleg severity. PostgreSQL stores trajectory geometry in PostGIS.
- **2.2 Surface proximity — ✅ Done.** Radius-based offset selection returns surface distance.
- **2.3 At-depth separation — ✅ Done.** Corresponding formation samples produce target-depth 3D separation while preserving surface distance.
- **2.4 Formation-relative projection — ✅ Done.** Event position is converted to a fraction within its source formation and projected into the active-well equivalent interval.
- **2.5 Uncertainty propagation — ✅ Done.** Top/base and datum uncertainty produce conservative projected bounds and method notes. This is bounded propagation, not a calibrated probability distribution.
- **2.6 Fallback hierarchy — ✅ Done.** Verified top/base, approximate thickness, TVD, and raw-MD fallbacks are explicit and retain calculation inputs.
- **2.7 Missing formation behavior — ✅ Done.** If a required formation is absent, projection is blocked rather than invented.

**Where in the code:** `backend/app/geometry.py`, `backend/app/store.py`, geometry routes in `backend/app/main.py`, tests in `backend/tests/test_geometry.py` and related PostgreSQL tests.

**Where it shows on the site:** `/#offsets` shows surface and target-depth distance; `/#compare` shows formation-normalized intervals; the depth strip on `/#brief` shows projected events, risk windows, and uncertainty. Dogleg severity is available in survey/geometry responses and diagnostics rather than as a main dashboard card.

**What it does for the user:** The user selects an active well/formation and receives offsets ranked by where their wellbores actually are near that target, plus projected historical event intervals with visible uncertainty and fallback method.

**Depends on:** Phases 0 and 1 trajectory, formation, unit, and datum records.

### Phase 3: Analog selection and transferability

**Goal:** Decide whether a historical event is applicable to the active interval without treating proximity as proof.

**What was done:**

- **3.1 Candidate cascade — ✅ Done.** Selection proceeds through radius, formation, downhole geometry, structure/operating context, and data-quality gates.
- **3.2 Comparison factors — ✅ Done.** Separation, formation match, alignment quality, hole size, event-depth inclination, mud weight/ECD, pressure/overbalance, technology era, drilling technology, permeability, stationary exposure, gas/influx context, and source quality are represented where relevant.
- **3.3 Risk-specific policies — ✅ Done.** Mud loss, stuck pipe, and kick/influx use separate context policies. Missing inputs remain unknown and reduce confidence.
- **3.4 Blockers and penalties — ✅ Done.** Datum/formation failures block transfer; weaker alignment or missing context lowers weight and never increases it.
- **3.5 Explanations — ✅ Done.** Transfer results expose included, excluded, blocker, missing-factor, method, and weight explanations. Policies are rule-based and uncalibrated on field data.

**Where in the code:** `backend/app/transfer_context.py`, `backend/app/evidence.py`, `/api/v1/transferability/event`, analog and alignment routes in `backend/app/main.py`.

**Where it shows on the site:** `/#offsets`, `/#compare`, and the transfer-assessment step in `/#evidence`.

**What it does for the user:** A historical event is filtered and weighted against the active interval; the UI states why it counts, why it was excluded, and which context was unavailable.

**Depends on:** Phases 1 and 2.

### Phase 4: Historical evidence engine

**Goal:** Turn transferable history into auditable evidence states without overstating sparse data.

**What was done:**

- **4.1 Evidence roles — ✅ Done.** Support, verified counter/clean crossing, unknown, and excluded records remain separate. Missing documents are not clean evidence.
- **4.2 Weighted summaries — ✅ Done.** One contribution per well is selected; weighted event rate and effective sample size are computed deterministically.
- **4.3 Historical states — ✅ Done.** NO_EVIDENCE, INSUFFICIENT_EVIDENCE, LESSON, and ELEVATED are produced. WARNING is reserved for fresh live corroboration.
- **4.4 Deterministic summary — ✅ Done.** The summary sentence is built from stored counts, weights, state, and uncertainty rather than model-generated prose.
- **4.5 Evidence API — ✅ Done.** Snapshots return support/counter/unknown counts, selected records, transfer details, source links, coverage, calculations, and policy version.

**Where in the code:** `backend/app/evidence.py`, `backend/app/domain/runtime.py`, evidence routes in `backend/app/main.py`, `backend/tests/test_evidence.py`.

**Where it shows on the site:** Evidence state and counts appear on `/#brief`; full rows, calculations, transfer rationale, and source chain appear on `/#evidence`.

**What it does for the user:** The user gets a conservative historical state, a short reproducible explanation, and direct access to every supporting, counter, or unknown record.

**Depends on:** Phases 1–3.

### Phase 5: Replay and current-well context

**Goal:** Maintain a time-aware current-well context and drive it through a deterministic replay.

**What was done:**

- **5.1 Current context — ✅ Done.** Bit depth, hole depth, formation, next formation, activity, operation state, flow in/out, pit volume, mud weight, ECD, WOB, RPM, torque, hookload, SPP, gas, ROP, source, timestamp, freshness, and quality are represented.
- **5.2 Source precedence — ✅ Done.** Source priority and timestamp rules select values and retain conflicts rather than silently overwriting them.
- **5.3 Adapters — ⚠️ Partial.** Replay, CSV upload, and manual entry work. REST, database polling, WITSML, and ETP production adapters are not implemented.
- **5.4 Playback — ✅ Done.** Start/play, pause, reset, speed, seek, cursor advancement, failure injection, and WebSocket streaming are backend-controlled.
- **5.5 Freshness — ✅ Done.** Per-channel configurable thresholds produce FRESH, STALE, MISSING, INVALID, or CONFLICTED states.
- **5.6 Formation context — ✅ Done.** Current formation, next formation, distance to next top, and structured uncertainty are returned. Reset and transition behavior have tests.

**Where in the code:** `backend/app/live.py`, `backend/app/live_routes.py`, `backend/app/domain/contracts.py`, `backend/tests/test_live.py`, `backend/tests/test_replay_completion.py`, `frontend/src/LiveWorkspace.tsx`.

**Where it shows on the site:** `/#brief` contains the full replay controls and context. `/#rig` contains the reduced operational view.

**What it does for the user:** The user creates or resumes a replay, changes speed or position, injects data failures, and sees current depth, formation, signals, freshness, and risk recomputed from the selected frame.

**Depends on:** Phases 0–4.

### Phase 6: Mud-loss vertical slice

**Goal:** Deliver one complete, auditable historical-plus-live risk workflow.

**What was done:**

- **6.1 Historical mud-loss evidence — ✅ Done.** Event severity, projected event interval, mud/ECD/hole/operation context, mitigation, outcome, transfer assessment, and source span are included when present.
- **6.2 Depth-driven triggering — ✅ Done.** State moves from no evidence to LESSON and ELEVATED as the bit approaches/enters configured look-ahead windows. Thresholds are backend policy settings and are explicitly uncalibrated.
- **6.3 Live corroboration — ✅ Done.** Flow imbalance, pit trend, ECD/change, mud-weight trend, freshness, and operation-state gating are evaluated.
- **6.4 Warning gate — ✅ Done.** WARNING requires an ELEVATED historical state, fresh corroboration, valid operation state, and minimum evidence sufficiency. Stale flow blocks escalation and is explained.
- **6.5 Alert lifecycle — ✅ Done.** Stable well/risk/formation/interval IDs deduplicate across runs. Created, escalated, acknowledged, snoozed, resolved, interval-passed, evidence-changed, and restarted episodes are audited; escalation and material evidence changes control re-notification.
- **6.6 Alert evidence — ✅ Done.** Alerts include source well/event/document, projection and uncertainty, transfer reasoning, support/counter/unknown counts, historical lessons, corroboration, freshness, and policy version.
- **6.7 Safe wording — ✅ Done.** UI and API label the result as decision support and simulation; recommendations direct users to verify data and approved procedures rather than issuing operational commands.

**Where in the code:** `backend/app/mud_loss.py`, `backend/app/live_routes.py`, `backend/app/evidence.py`, configuration in `backend/app/config.py`, lifecycle tests in `backend/tests/test_live.py` and `test_replay_completion.py`.

**Where it shows on the site:** `/#brief` is the complete slice; `/#rig` shows one important alert, evidence sentence, signals, acknowledge, Why, and source controls; `/#evidence` shows the complete provenance chain.

**What it does for the user:** As replay depth advances, the user first sees the historical lesson, then elevated exposure, and only sees a warning if live data is fresh and corroborating. The user can inspect and manage the resulting alert.

**Depends on:** Phases 1–5.

### Phase 7: Secondary risk modules

**Goal:** Demonstrate a common extensible framework while displaying lower maturity explicitly.

**What was done:**

- **7.1 Stuck pipe — ✅ Done at partial-support scope.** Historical stuck-pipe evidence, formation/trajectory context, operation binding, torque trend, hookload deviation, SPP trend, and stationary duration are shown. It never presents itself as a complete predictor.
- **7.2 Kick/overpressure — ✅ Done at conservative-support scope.** Historical kick/influx, formation/pressure/mud context, pit gain, flow-out-over-flow-in, gas rise, and operation gating are shown. No black-box classifier exists.
- **7.3 Torque/dysfunction — ✅ Done at supporting-indicator scope.** Torque residual, ROP/WOB/RPM, optional MSE, and trend changes are shown. MSE is explicitly not treated as a standalone stuck-pipe predictor.
- **7.4 Cementing — ✅ Done at historical-planning scope.** Cement jobs expose casing interval, problems, remedial action, and outcome. There is no real-time cementing model.
- **Common framework — ✅ Done.** Each module uses the Phase 4 evidence snapshot and transfer framework, reports maturity, and disables live WARNING generation. All behavior remains 🧪 synthetic/unvalidated.

**Where in the code:** `backend/app/secondary.py`, secondary route in `backend/app/workflow.py`, rendering in `frontend/src/WorkflowWorkspace.tsx`, tests in `backend/tests/test_phase7_8.py`.

**Where it shows on the site:** Secondary module cards are part of the planning integration on `/#brief`; underlying evidence opens in `/#evidence`.

**What it does for the user:** The user sees relevant history and current indicators for four additional risks, with an explicit maturity label and no unsupported prediction claim.

**Depends on:** Phases 1–5 and the common Phase 4 evidence model.

### Phase 8: Dashboard and workflow integration

**Goal:** Join the engines into usable field and office workflows.

**What was done:**

- **8.1 Next Interval Brief — ✅ Done.** It is the default route and shows active well, depth, current/next formation, distance, upcoming intervals, evidence state/counts, freshness, lessons, and alerts.
- **8.2 Look-Ahead depth strip — ✅ Done.** Formation tops, uncertainty, casing points, projected events, current bit, risk windows, and evidence states share one depth axis.
- **8.3 Map — ✅ Done.** Active and offset wells, radius control, surface/target distance, relevance, and a surface-vs-target ranking-swap demonstration are present. `/#offsets` fetches an OpenStreetMap basemap near the synthetic Upper Assam anchor; markers are synthetic and tile imagery requires internet access. Co-located demo offsets are grouped visibly. The bit marker follows the selected replay session through its WebSocket stream (or polls manual context), with play/pause/step/reset controls and a computed plan-view survey trace. This is simulated replay position, not rig GPS.
- **8.4 Compare view — ✅ Done.** Wells are normalized by formation and show intervals, events, clean crossings, mud/casing context, and alignment uncertainty.
- **8.5 Evidence explorer — ✅ Done.** The alert-to-source chain is navigable and FACT, COMPUTED, and INFERRED values are labeled.
- **8.6 Document viewer — ✅ Done.** Original page image, highlighted source span, fields, confidence, and review status are displayed.
- **8.7 Review queue — ✅ Done.** Reviewers can accept/correct extraction, resolve aliases through corrections, correct units/depths, and quarantine events. Active look-ahead impact influences priority.
- **8.8 Simplified rig view — ✅ Done.** Current/next formation, one alert, evidence sentence, key signals, acknowledge, Why, and source controls are shown.
- **8.9 Validation page — ✅ Done.** Held-out results, baselines, alerts, hits/misses, lead distance, evidence/source coverage, assurance, gold-review, usability, and external-status panels are shown.
- **20-second criterion — ⚠️ Unverified.** The measurement workflow exists, but no participant study has been completed (`0/5` required sessions).

**Where in the code:** `frontend/src/App.tsx`, `frontend/src/IntegratedPages.tsx`, `frontend/src/GeoBasemap.tsx`, `frontend/src/useReplayMap.ts`, `frontend/src/LiveWorkspace.tsx`, `frontend/src/WorkflowWorkspace.tsx`, `frontend/src/NormalizedCompare.tsx`, `frontend/src/IndependentValidation.tsx`; backend view models and routes in `backend/app/workflow.py` and `backend/app/independent_validation.py`.

**Where it shows on the site:** `/#brief`, `/#offsets`, `/#compare`, `/#evidence`, `/#documents`, `/#review`, `/#rig`, and `/#validation`.

**What it does for the user:** A field user can start at the brief, inspect a risk and live gate, follow its evidence to the source page, compare offsets, and manage the alert; an office user can review extraction and validation detail.

**Depends on:** Phases 0–7.

### Phase 9: Grounded Ask NWIS

**Goal:** Answer supported questions through deterministic project tools while keeping risk calculations out of language generation.

**What was done:**

- **9.1 Query planner — ✅ Done.** Bounded regex/rule parsing maps supported questions to intent, requested entities, tool calls, and source retrieval. It is not a general semantic LLM planner.
- **9.2 Deterministic tools — ✅ Done.** Well lookup, formation lookup, event filtering, offset selection, alignment, evidence, mitigation, and alert lookup tools are implemented.
- **9.3 Structured-first retrieval — ✅ Done.** Records are selected before document source passages are retrieved.
- **9.4 Response structure — ✅ Done.** Answers separate Facts, Computed pattern, Interpretation, Gaps and uncertainty, and Sources.
- **9.5 Numeric verification — ✅ Done.** Numeric tokens must come from a tool result or cited source; the verifier rejects unsupported numbers.
- **9.6 Refusal — ✅ Done.** Unsupported, ambiguous, action-seeking, or insufficient-evidence questions return a limitation instead of a fabricated answer.
- **Prompt-injection boundary — ✅ Done.** Uploaded text is data only and cannot choose tools or execute instructions. Extraction code has no tool interface.

**Where in the code:** `backend/app/ask.py`, `backend/tests/test_ask_demo.py`, `frontend/src/AskWorkspace.tsx`.

**Where it shows on the site:** `/#ask` shows the plan, deterministic tool trace, sectioned answer, gaps, and source links.

**What it does for the user:** The user asks a supported well/formation/event/evidence question; NWIS plans fixed lookups, runs existing calculation code, verifies all numbers, cites records/pages, or explains exactly what evidence is missing.

**Depends on:** Phases 1–8 APIs and provenance records.

### Phase 10: Validation, hardening, and final demonstration

**Goal:** Exercise engineering behavior, quantify the synthetic demonstration, expose external validation gaps, and package a repeatable demo.

**What was done:**

- **10.1 Automated engineering tests — ✅ Done.** The current recorded run has 137 passing tests and no failures/skips. Tests cover units, datums, aliases, geometry, projection/uncertainty, coverage, transfer blockers, freshness, deduplication, transitions, provenance, Ask verification, and API behavior.
- **10.2 Extraction gold set — ⚠️ Partial.** Forty representative pages, including five scanned pages, have independent-of-extractor authored labels and calculated metrics. No independent human has accepted the pages or bounding boxes: current sign-off is `0/40` pages and `0/30` event boxes. Therefore the reported precision/recall and grounding metrics are development metrics, not certified extraction performance.
- **10.3 Blind held-out replay — 🧪 Mocked.** Eight synthetic held-out cases hide active-well future events, use offset history, replay, reveal truth, and score results.
- **10.4 Baselines — 🧪 Mocked.** Surface-nearest, same-formation equal weighting, fixed weights, and keyword/document retrieval are compared against NWIS in aggregate and case output.
- **10.5 Metrics — 🧪 Mocked.** Alert precision, severe-event recall, lead distance, alerts per 1,000 m, false negatives, projected interval overlap, evidence sufficiency, and source coverage are stored and displayed.
- **10.6 Controlled failure — ✅ Done.** The deterministic demo includes ELEVATED, stale-flow refusal, recovery, and interval-passed stages; the UI explains why stale live corroboration prevents WARNING.
- **10.7 Security and safety — ⚠️ Partial.** Automated checks verify untrusted document treatment, no extraction tool access, no rig write-back, configured local storage boundaries, audit records, and rule/model versions. Authentication/authorization, TLS, secret management, rate limiting, backup/failover, dependency scanning, penetration testing, and production multi-worker behavior remain open.
- **10.8 Startup/packaging — ✅ Done for demo use.** One-command startup, deterministic seed, replay reset, demo configuration, offline dependencies, claim ledger, architecture diagram, five-minute script, ZIP package, and `docs/demo_media/backup-demonstration.mp4` exist. The backup video is a generated demonstration artifact, not an independently recorded field run.
- **Field validation — ❌ Not done.** `storage/validation/field-validation.json` is `PENDING_EXTERNAL_FIELD_DATA`; there is no independent field calibration or acceptance evidence.
- **Concurrency assessment — ⚠️ Partial.** A bounded local read/write assessment exists and reports no failures in its recorded run, but the application uses a process-local lock and the demo intentionally runs one worker. This does not establish production concurrency safety.

**Where in the code:** `backend/tests/`, `backend/app/gold_set.py`, `independent_validation.py`, `blind_validation.py`, `production_assessment.py`, `field_validation.py`, `assurance.py`, `demo_routes.py`, `demo_recording.py`, `package_demo.py`; artifacts in `storage/gold`, `storage/benchmark`, `storage/validation`, `storage/packaging`, and `docs`.

**Where it shows on the site:** `/#validation`; the controlled stale-flow scenario is also visible on `/#brief` and `/#rig`.

**What it does for the user:** A demonstrator can reset and replay a fixed case, show failure-safe behavior, inspect synthetic benchmark/gold metrics, and see exactly which external validation and production controls are still missing.

**Depends on:** All earlier phases.

## 4. Site map

### Frontend pages

| Hash route | Phase | Purpose |
|---|---:|---|
| `/#brief` | 5–8 | Default Next Interval Brief, replay controls, formation/depth strip, risk evidence, secondary modules, signals, and active alerts. |
| `/#overview` | 0, 8 | Product scope and API-backed loaded-data inventory (well/report/event counts, record flags, current report links, gazetteer count). |
| `/#offsets` | 2–3, 5, 8 | Map/radius selection, surface and target-depth distance, relevance, ranking swap, and replay-synchronized bit movement. |
| `/#compare` | 2–4, 8 | Formation-normalized offset comparison with events, clean intervals, casing/mud, and uncertainty. |
| `/#evidence` | 4, 6, 8 | Evidence rows and alert → transfer → event → source span → document chain. |
| `/#documents` | 1 | Document list, original page images, extracted fields, spans, confidence, and status. |
| `/#review` | 1, 8 | Prioritized extraction/coverage review, correction, acceptance, and quarantine. |
| `/#ask` | 9 | Grounded question planner, deterministic tool trace, answer sections, limitations, and sources. |
| `/#validation` | 8, 10 | Engineering/gold/benchmark results, baselines, safety, production assessment, human review, usability study, and field-validation status. |
| `/#rig` | 6, 8 | Reduced rig view with one alert, formations, evidence sentence, key signals, acknowledge, Why, and source. |
| `/#settings` | 0 | Frontend-local provider/presentation settings. These are not persisted server policy administration. |

The shell has three provider labels. `SYNTHETIC` and `API` both call the backend in the current implementation. `MOCK` uses illustrative fixtures in `frontend/src/data.ts`; mock values must never be quoted as measured results.

### Backend routes

All HTTP routes below are available under `/api/v1`. Legacy `/api` aliases remain for compatibility. WebSocket streaming is `/api/v1/replay/sessions/{session_id}/stream`.

| Route or family | Phase | Purpose |
|---|---:|---|
| `GET /health`, `GET /api/v1/meta` | 0 | Health, environment, versions, policy metadata, and seed identity. |
| `/api/v1/wells`, `/wells/{id}`, `/survey`, `/formations`, `/events`, `/coverage` | 1–2 | Canonical well, trajectory, formation, event, and coverage records. |
| `/api/v1/wells/{id}/offsets`, `/offsets/at-depth`, `/analogs` | 2–3 | Surface/downhole candidates and analog selection. |
| `POST /api/v1/alignment/project-event` | 2 | Formation-relative event projection and uncertainty. |
| `POST /api/v1/transferability/event` | 3 | Risk-specific transfer assessment. |
| `/api/v1/evidence/snapshots/{id}`, `/wells/{id}/lookahead` | 4, 6 | Historical evidence detail and look-ahead states. |
| `/api/v1/documents*`, `/api/v1/gazetteer` | 1 | Ingest/list documents, extracted events, source spans, page data/images, and aliases. |
| `GET /api/v1/review`, `POST /api/v1/review/{id}` | 1, 8 | Review queue and review actions. |
| `/api/v1/replay/config`, `/datasets`, `/sessions`, `/demo` | 5 | Replay configuration, CSV datasets, session creation, and deterministic demo session. |
| `/api/v1/replay/sessions/{id}*` | 5–6 | Current context, advance, quality/failure injection, evaluation, manual input, control, and WebSocket stream. |
| `GET /api/v1/alerts`, `POST /api/v1/alerts/{id}/transition` | 6 | Alert list and acknowledge/snooze/resolve lifecycle. |
| `/api/v1/replay/sessions/{id}/brief`, `/secondary` | 7–8 | Next Interval Brief and secondary module view models. |
| `/api/v1/evidence/chain/{snapshot_id}/{event_id}` | 8 | Full evidence provenance chain for one event in a snapshot, including any linked alert. |
| `/api/v1/wells/{id}/compare`, `/ranking-swap` | 8 | Formation compare and surface-vs-target ranking case. |
| `/api/v1/validation/results`, `/hardening` | 10 | Validation artifacts and hardening summary. |
| `POST /api/v1/ask`, `/ask/plan`, `/ask/verify` | 9 | Grounded answer, plan inspection, and numeric-verification endpoints. |
| `/api/v1/demo/session`, `POST /api/v1/demo/scenario` | 10 | Fixed five-minute scenario controller. |
| `/api/v1/validation/gold*` | 10 | Gold pages/images and human review submissions. |
| `/api/v1/validation/usability*`, `/external-status` | 10 | 20-second study records and external-validation status. |

## 5. Current state and gaps

### Fully working in the repository

- Deterministic synthetic field and five historical event families.
- Native PDF and image-only PDF ingestion, OCR, source geometry, event extraction, corrections, quarantine, and coverage.
- Minimum-curvature geometry, PostGIS trajectory persistence, at-depth separation, projection, fallbacks, and uncertainty bounds.
- Risk-specific transfer rules, support/counter/unknown evidence, deterministic summaries, and source reconstruction.
- Full replay/manual/CSV current context with every planned signal, channel freshness, reset/seek/speed/play/pause, WebSocket updates, and failure injection.
- Mud-loss look-ahead, live gating, cross-run alert deduplication, lifecycle, and stale-signal refusal.
- Lower-maturity secondary modules with explicit labels.
- All requested dashboard pages and review/source workflows.
- Deterministic Ask NWIS with tool/number/source verification and refusal behavior.
- One-command SQLite demo, offline bundle, Docker/PostGIS stack, CI, test suite, benchmark artifacts, demo script, package, and backup video.

### Partial, mocked, or unverified

- All domain data, replays, gold pages, and benchmark cases are synthetic. No claim is supported for field accuracy, calibration, reliability, or operational benefit.
- Gold labels were authored separately from the extractor, but independent human review is incomplete: `0/40` pages and `0/30` event bounding boxes accepted.
- The 20-second usability criterion has no completed participant sample (`0/5`).
- External field validation is pending because no approved field manifest/data has been supplied.
- The production assessment is deliberately `NOT_PRODUCTION_READY`; it is a local bounded exercise, not a security audit or load certification.
- Document layout and extraction are heuristic and tuned to the synthetic report formats. Handwriting, broad vendor format variation, poor scans, and unseen abbreviations are unproven.
- Ask NWIS supports bounded intent patterns. It has no language model, broad conversational understanding, or cross-turn semantic memory.
- Secondary risks are historical/supporting modules, not calibrated predictors. Cementing has no real-time model. Mud loss is the only polished vertical slice.
- `PUBLIC`/`PRIVATE` is record metadata. There are no users, roles, tenant boundaries, or document access controls.
- There are no REST polling, database streaming, WITSML, ETP, or rig adapters and no write-back path.
- The Docker stack uses development credentials, exposes database/API/dev-server ports, and has no TLS or production reverse proxy.

### Known bugs and fragile areas

- `.env.example` uses `NWIS_ENV`; the application expects `NWIS_ENVIRONMENT`.
- Synthetic report generation does not clean obsolete PDFs. The manifest is authoritative, so stale files are ignored by bootstrap but remain on disk.
- Only one Alembic baseline exists. Most domain entities share a generic JSON-record table, which simplifies the prototype but weakens database-level constraints and query planning.
- The repository uses a process-local `RLock`; `Start-Demo.ps1` intentionally runs one Uvicorn worker. Multi-process transactional behavior has not been designed or proven.
- `App.tsx`, `IntegratedPages.tsx`, `LiveWorkspace.tsx`, and `WorkflowWorkspace.tsx` are large components with substantial inline rendering logic. They should be split before sustained feature growth.
- Routing is a custom hash switch. URL parsing, route-level tests, nested state, and browser history behavior are less robust than a dedicated router.
- Active session/well state is partly retained in `localStorage`; an old replay ID can survive backend database replacement and must fall back to a new demo session.
- `SYNTHETIC` and `API` provider modes currently have the same backend behavior, while `MOCK` is a separate fixture path. The labels imply more distinction than exists.
- Some explanatory UI strings include policy thresholds. They can drift from backend-configured JSON policies unless they are sourced from `/meta` or replay configuration.
- The bounding-box review UI uses numeric normalized coordinates and preview rather than drag-to-draw annotation.
- Usability timing uses client `performance.now()` and participant attestation; it is sufficient for a prototype exercise, not a controlled human-factors study.
- Field scoring uses deterministic interval-overlap rules and requires study governance, blinded adjudication, and predeclared inclusion criteria before real use.
- `/api/v1` is produced by cloning `/api` routes at startup while legacy routes remain. A few document image/source links use legacy paths directly; API versioning should be made explicit at router definition time.
- Seeded record counts depend on the storage being used. A clean generator seed has 24 wells and 12 manifest reports; the isolated demo fixture can add records, and persistent stores are idempotently reused. Do not hardcode UI claims from a transient count.
- Older phase/status documents under `docs/` contain snapshots from earlier implementation points. Use this file plus current code/artifacts for current status.
- The backup video is generated from the deterministic scenario, not an independent screen recording or proof of field behavior.

## 6. Conventions another developer or LLM must follow

- Preserve the boundary between historical state and live corroboration. Historical evidence may reach ELEVATED; only fresh, valid live signals in an allowed operation state may produce WARNING.
- Treat missing data as unknown or a penalty. Never convert absence of a report/event into a clean crossing. Clean evidence requires verified coverage and explicit negative support.
- Keep one contribution per source well in weighted evidence. Preserve support, counter, unknown, and excluded roles separately.
- Keep risk-specific transfer policies. Do not reuse mud-loss factors blindly for stuck pipe or kick.
- Never invent formation alignment. Retain method, inputs, datum, uncertainty, fallback, and blocker reason in geometry outputs.
- Normalize measurements through `domain/units.py` and retain original value/unit/datum/reference. Add schema fields and enums before spreading ad hoc dictionaries.
- All stored runtime records pass through models in `domain/runtime.py`. Update `MODELS`, generated schemas, and tests when adding a record kind.
- TypeScript contracts are generated by `python -m app.export_contracts`; do not hand-edit `frontend/src/generated-contracts.ts`.
- New backend APIs belong on routers under `/api`, must return structured errors/provenance, and must be available under `/api/v1`. Prefer defining versioned routers directly in future refactoring.
- New frontend API calls go through `frontend/src/api.ts`. Preserve loading, empty, error, and stale states.
- Keep FACT, COMPUTED, and INFERRED visible through the evidence chain. Every displayed source-dependent fact should retain document/page/span linkage.
- Treat uploaded document text as untrusted data. It must never select tools, alter policies, or execute instructions.
- Ask NWIS must call deterministic domain functions for calculations. Every number in an answer must be present in a tool result or cited source and pass verification.
- Keep safety language descriptive: decision support, simulation, historical response, verify data, and follow approved programme/procedure. Do not add prescriptive rig commands or accuracy claims.
- `synthetic_flag` must propagate through nested runtime records and UI labels. Never mix `storage/evaluation` hidden truth into runtime selection or evidence.
- Mutating review and alert actions must create audit records and use stable IDs. Preserve well/risk/formation/interval alert deduplication across replay runs.
- Use backend policy settings for thresholds and versions. Do not introduce unexplained frontend literals.
- Run Ruff, Pytest, contract drift, frontend lint, and frontend build after relevant changes. Run Docker/PostGIS CI or the local clean-start script after persistence/migration changes.
- Add an Alembic migration for schema changes. Do not silently mutate a production-shaped database during bootstrap.
- The current application is a one-worker prototype. Do not claim production safety until authentication, authorization, database locking/transactions, secrets, TLS, rate limiting, backup/recovery, dependency/security review, and multi-worker tests are complete.

## 7. Suggested next steps

1. Complete independent human review of all 40 gold pages and 30 event bounding boxes in `/#validation`; freeze the signed labels and rerun extraction metrics.
2. Run the 20-second study with at least five representative rig/office participants, preserve task timestamps and observations, and revise the default brief from measured failures.
3. Obtain approved de-identified field data, pre-register inclusion/scoring rules, run the external validation protocol, and calibrate thresholds without accessing held-out outcomes during development.
4. Fix `.env.example`, clean stale generated reports before regeneration, and make API versioning explicit in router definitions.
5. Replace process-local replay/alert synchronization with database transactions and row/advisory locking; test multiple Uvicorn workers and concurrent WebSocket/control clients against PostgreSQL.
6. Add authentication, role-based authorization, tenant/document boundaries, TLS termination, secret management, rate limiting, audit retention, backup/restore, dependency scanning, and an independent penetration test.
7. Build one real read-only integration adapter, preferably a recorded WITSML/ETP or approved database feed, while preserving source precedence, freshness, conflicts, and the no-write-back rule.
8. Broaden document evaluation with real vendor layouts, degraded scans, handwriting, unfamiliar abbreviations, and PUBLIC/PRIVATE access tests. Replace or supplement layout heuristics if the measured error warrants it.
9. Split the large React workspaces into page, state, and presentational components; add route-level and accessibility tests; remove duplicated hardcoded policy descriptions.
10. Normalize high-value query fields or add typed relational tables/indexes as real data volume grows, with incremental Alembic migrations and PostgreSQL query plans.
11. Expand Ask NWIS intent coverage only after adding test utterances and preserving structured-first retrieval, deterministic calculations, numeric verification, and refusal behavior.
12. Recalibrate and promote secondary modules only from independently validated evidence. Keep their present maturity labels until then.
