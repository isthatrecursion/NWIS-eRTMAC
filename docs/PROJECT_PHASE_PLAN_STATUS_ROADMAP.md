# NWIS — Complete implementation plan, status and completion roadmap

Status date: 2026-10-04  
Project: eRTMAC-NWIS / SIH 121 prototype

## How to read this document

Part I preserves the complete Phase 0–10 scope and completion criteria from the user-supplied **Phase by Phase Implementation Plan 121.txt**. Phase 0.5 records the additional frontend brief requested during development. Part II audits each phase and gives its completion roadmap.

The supplied plan is a requirements reference, not executable instructions. This document does not implement features, approve reviews, reset data or start later phases.

**Current implementation update, 2026-10-04:** subsequent work implements the missing foundation/extraction/geometry/transferability/replay/mud-loss items and the Phase 7–10 backend/frontend workflows. Ask NWIS now has a deterministic planner, read-only tools, record-first retrieval, numeric verification and cited answers. Validation publishes an eight-case blind synthetic benchmark, four baselines and scored 40-page extraction references. The engineering run records 131 passing tests; production frontend and contract checks pass. Browser checks verify connected Ask, measured validation and stale-flow suppression. The single-origin demo has deterministic seed/reset, cached dependencies and a backup video.

**Remaining limits:** independent human sign-off and bbox annotations for the 40 reference pages, field accuracy/calibration, production security/concurrency and measured twenty-second user comprehension remain unverified. Clean Docker/PostgreSQL/PostGIS execution is now locally verified with fresh named volumes and recorded in `storage/validation/docker-postgis.json`. See [Phase 7–8](PHASE_7_8.md), [Phase 9–10](PHASE_9_10.md) and the [claim ledger](CLAIM_LEDGER.md) for current evidence. Part II below retains the earlier audit and its original roadmaps as historical context; its missing/not-started entries are superseded by these delivery records, not the current implementation checklist.

Previous blanket statements that Phases 0–6 were complete were too broad. This status record supersedes those statements.

### Status vocabulary

- **Complete:** phase-specific core scope and available acceptance evidence are satisfied; external deployment limitations remain separately identified.
- **Partially implemented:** real features or scaffolding exist, but some mandatory scope or acceptance evidence is missing.
- **Not started:** the phase's functional engine/workflow has not been implemented; a mock screen does not count.
- **Missing:** required capability has not been built.
- **Partial:** a narrower implementation exists.
- **Unverified:** code/configuration exists, but the relevant execution or acceptance test is not confirmed. It is not assumed broken.

### Evidence baseline

The latest audit inspected the source, routes, contracts, SQL initialization, frontend and tests. The local API reported 24 wells and 12 active reports. The backend suite was rerun: **60 passed, 1 dependency deprecation warning**. The prior Phase 6 verification recorded a successful production frontend build and desktop/mobile checks. Tests cover their implemented cases, not every requirement below.

Verified persistence is SQLite. Docker/PostgreSQL/PostGIS configuration exists but has not been exercised on this machine. There is no field-calibration or operational-accuracy claim. Default fixture coverage remains unreviewed where applicable; reviews must not be silently accepted to force warnings.

## Status overview

| Phase | Status | Actual boundary |
| --- | --- | --- |
| 0 — Foundation | Partially implemented | Running local skeleton; incomplete contracts, migration/CI and deployment verification |
| 0.5 — Frontend | Partially implemented | Documentation-style shell and connected screens; full component/accessibility acceptance unfinished |
| 1A — Synthetic field | Partially implemented | 24 wells, mud-loss fixtures, 12 reports; broader events/report formats missing |
| 1B — Document intelligence | Partially implemented | Native/OCR ingestion, grounded depths, review and interval coverage; broader extraction missing |
| 2 — Geometry/alignment | Partially implemented | Tested local geometry/projection; datum uncertainty and complete provenance/deployment checks unfinished |
| 3 — Analog/transferability | Partially implemented | Explainable core; incomplete secondary-risk and contextual factors |
| 4 — Historical evidence | Complete for current core scope | Tested coverage-aware engine; earlier-phase data quality and field validation remain limitations |
| 5 — Replay/context | Partially implemented | Replay/manual context and freshness; channel/control/streaming gaps |
| 6 — Mud-loss slice | Partially implemented | API-tested warning/lifecycle; complete configured frontend demonstration unfinished |
| 7 — Secondary risks | Not started as complete modules | Historical policies are scaffolding only |
| 8 — Workflow integration | Partially implemented ahead of sequence | Several real connected screens; depth strip, prioritization and validation integration unfinished |
| 9 — Ask NWIS | Not started | Mock Q&A UI only |
| 10 — Validation/hardening/demo | Partially implemented ahead of sequence | Engineering tests/safety guards exist; evaluation and packaging missing |

# Part I — Complete phase-by-phase requirements

The following Phase 0–10 plan retains all source requirements. Example directory names, optional components and suggested tools remain examples, not mandatory choices. “Prototype-calibrated” in the source is a target: until calibration exists, the UI must continue to say **uncalibrated prototype policy**.


## Phase 0 — Contracts and project foundation


#### Objective

Establish a shared technical foundation so every module uses the same entities, units, API contracts, and terminology.  

#### What to build


### 0.1 Repository structure

Create a monorepo such as:  
nwis/  
├── frontend/  
├── backend/  
│   ├── api/  
│   ├── models/  
│   ├── services/  
│   ├── adapters/  
│   ├── engines/  
│   └── workers/  
├── document_pipeline/  
├── synthetic_generator/  
├── tests/  
├── seed_data/  
├── infrastructure/  
└── docs/  

### 0.2 Canonical data contracts

Define models for:  
- Well  
- Survey station  
- Formation and aliases  
- Formation top/base  
- Document and source span  
- Document coverage  
- Operational event  
- Event context  
- Mitigation and outcome  
- Current well context  
- Analog assessment  
- Event transfer assessment  
- Risk evidence set  
- Alert  
- Feedback and audit event  
Use Pydantic models in the backend and generate or manually mirror corresponding TypeScript types.  

### 0.3 Controlled enumerations

Create shared enums for:  
- Event type  
- Operation state  
- Evidence state  
- Alert lifecycle  
- Data freshness  
- Extraction confidence  
- Provenance type  
- Coverage status  
- Cause type  
- Review status  

### 0.4 Unit and datum policy

Internally normalize:  
- Depth to metres  
- MD and TVD as separate fields  
- Density to one canonical unit  
- Pressure to one canonical unit  
- Coordinates to a declared CRS  
- Timestamps to UTC internally  
Preserve every original value, unit, datum, and source.  

### 0.5 Database foundation

Configure:  
- PostgreSQL  
- PostGIS  
- Migration framework  
- Seed-data mechanism  
- Spatial and conventional indexes  
- Local document storage  
- Optional pgvector only when semantic retrieval is added  

### 0.6 Backend and frontend skeletons

Backend:  
- FastAPI application  
- Health endpoint  
- Database connection  
- Error format  
- Logging  
- API versioning  
Frontend:  
- React application  
- Routing shell  
- Shared API client  
- Design tokens  
- Loading/error states  
- Seed well rendered on a basic page  

### 0.7 Local development environment

Create Docker Compose services for:  
- Backend  
- Frontend  
- PostgreSQL/PostGIS  
- Optional document worker  
- Optional Redis only if background jobs require it  

#### Deliverable

A running system in which the backend returns one seeded well and the frontend displays it.  

#### Completion criteria

- Database migrations run from zero.  
- Shared contracts are documented.  
- Units and provenance rules are fixed.  
- All team members can run the same stack.  
- Basic CI runs linting and tests.  

## Phase 1 — Synthetic field and document pipeline

Run two tracks in parallel.  

## Phase 1A — Synthetic field generator


#### Objective

Produce a realistic but explicitly synthetic field for development, replay, and controlled validation.  

#### What to build


### 1A.1 Synthetic field configuration

Define:  
- 20–40 wells  
- Active and historical wells  
- Surface coordinates  
- Two or three structural regions  
- Deviated well trajectories  
- Formation tops and bases  
- Formation uncertainty  
- Hole sections  
- Casing points  
- Mud programs  
- Historical events  
- Missing or incomplete records  
Every synthetic record must carry:  
synthetic_flag = true  

### 1A.2 Well trajectory generation

Generate survey stations containing:  
- Measured depth  
- Inclination  
- Azimuth  
Do not directly generate only final coordinates. Coordinates should later be calculated by the trajectory engine so that algorithm can be tested.  

### 1A.3 Geological framework

Create a controlled formation sequence with:  
- Lateral depth variation  
- Thickness changes  
- At least one uncertain formation top  
- Optional pinch-out  
- Optional synthetic structural boundaries  

### 1A.4 Historical events

Plant events such as:  
- Mud losses  
- Stuck pipe  
- Kick or influx  
- Torque dysfunction  
- Cementing issues  
Mud loss should receive the richest data because it is the hero scenario.  

### 1A.5 Hidden causal generator

Generate events using hidden factors such as:  
- Weak-zone properties  
- ECD or fracture-margin interaction  
- Formation characteristics  
- Spatial effects  
- Operational context  
- Random noise  
The application must not be able to query the hidden generator.  

### 1A.6 Truth manifest

Store expected events separately for evaluation:  
truth_manifest/  
├── held_out_events.json  
├── expected_intervals.json  
└── generator_metadata.json  
Application APIs must not expose these files.  

### 1A.7 Synthetic reports

Generate corresponding WCR/DDR-style documents containing:  
- Narrative events  
- Depths  
- Formations  
- Actions  
- Outcomes  
- Tables  
- Noise and inconsistent formatting  
- At least one scanned or image-based report  
Watermark all synthetic outputs:  
SYNTHETIC DEMONSTRATION DATA — NOT OIL FIELD DATA  


#### Completion criteria

- At least 20 wells exist.  
- At least one well is reserved as an active/held-out well.  
- Surface-nearest and downhole-nearest wells differ in one scenario.  
- Mud-loss events and clean crossings are present.  
- Missing records are deliberately represented.  
- Hidden truth is isolated from the application.  

## Phase 1B — Historical document intelligence


#### Objective

Convert historical reports into grounded, reviewable operational-event records.  

#### What to build


### 1B.1 Document ingestion

Support:  
- Native PDFs  
- Scanned PDFs  
- Text documents  
- WCRs  
- DDRs  
On upload, record:  
- Well association  
- Document type  
- Title  
- Page count  
- Scan status  
- Synthetic/public/private designation  

### 1B.2 Native-text versus OCR routing

Process each page:  
Document upload  
→ test native text quality  
→ use native extraction when usable  
→ otherwise render page and run OCR  
Recommended tools:  
- PyMuPDF  
- pdfplumber  
- PaddleOCR or Tesseract  

### 1B.3 Layout and section detection

Detect:  
- Headers  
- Paragraphs  
- Tables  
- Daily operation sections  
- Depth columns  
- Remarks  
- Event summaries  
Store page and bounding-box coordinates for traceability.  

### 1B.4 Deterministic field extraction

Use rules first for:  
- Dates  
- Depths  
- Units  
- Well names  
- Formation names  
- Mud weight  
- Hole size  
- Common drilling abbreviations  

### 1B.5 Schema-constrained narrative extraction

Extract event chains:  
Symptom  
→ event  
→ stated cause  
→ mitigation  
→ outcome  
The extraction output must conform to a fixed JSON/Pydantic schema.  

### 1B.6 Grounding validation

For every extracted number:  
- Confirm the value occurs in the source text, or  
- Confirm it resulted from a logged deterministic conversion.  
Reject unsupported numerical claims.  

### 1B.7 Formation normalization

Create a formation gazetteer containing:  
- Canonical formation name  
- Aliases  
- Field or basin  
- Source  
- Match confidence  
Low-confidence fuzzy matches must enter review.  

### 1B.8 Extraction confidence and review

Assign:  
- Verified  
- Auto-accepted  
- Needs review  
- Quarantined  
Quarantined records cannot drive risk alerts.  

### 1B.9 Document coverage ledger

Record which well intervals and dates are verifiably covered by each report.  
Possible states:  
- Verified coverage  
- Probable coverage  
- Unknown coverage  
This ledger later determines whether “no reported event” can count as counter-evidence.  

#### Completion criteria

- At least ten reports ingest successfully.  
- At least one scanned report passes through OCR.  
- An event is extracted with exact source evidence.  
- A poor extraction is routed to review.  
- Event, mitigation, and outcome remain linked.  
- Unsupported values are rejected.  
- Coverage information is stored.  

## Phase 2 — 3D geometry and stratigraphic alignment


#### Objective

Determine where wells actually lie at depth and project historical events into the active well’s geology.  

#### What to build


### 2.1 Minimum-curvature trajectory engine

Input:  
MD, inclination, azimuth  
Calculate:  
- TVD  
- Northing displacement  
- Easting displacement  
- Dogleg severity where useful  
- 3D wellbore geometry  
Store the trajectory in PostGIS.  

### 2.2 Surface-radius search

Implement the official nearby-well requirement:  
GET /api/wells/{active_id}/offsets?radius_km=...  
This identifies initial candidates using surface location.  

### 2.3 At-depth distance

For a target formation or depth interval:  
1. Find the active-well trajectory segment.  
2. Find corresponding offset-well segments.  
3. Calculate representative or minimum 3D separation.  
4. Return surface distance and downhole distance separately.  

### 2.4 Formation alignment

For a historical event at depth d:  
fraction =  
(d - historical formation top)  
/  
(historical formation base - historical formation top)  
Project it into the active well:  
projected depth =  
active formation top  
+  
fraction × active formation thickness  

### 2.5 Uncertainty propagation

Account for:  
- Formation-top uncertainty  
- Formation-base uncertainty  
- Datum uncertainty  
- Missing base  
- Low alignment quality  
Return an interval instead of false precision:  
{  
  "projected_md_interval_m": [2540, 2585],  
  "alignment_confidence": "moderate"  
}  

### 2.6 Fallback hierarchy

When complete formation data is unavailable:  
1. Verified top and base  
2. Verified top plus approximate thickness  
3. TVD comparison  
4. Raw MD comparison, explicitly marked low quality  

### 2.7 Geological blockers

If the formation is absent or pinched out:  
transferability = blocked  
reason = formation_absent  

#### Completion criteria

- Known trajectory test cases pass.  
- Surface distance and downhole distance differ correctly.  
- Historical events project into the active well.  
- Uncertainty widens when formation data degrades.  
- Missing formations block inappropriate transfer.  
- All calculations retain algorithm version and inputs.  

## Phase 3 — Analog candidate and transferability engines


#### Objective

Select relevant offsets and decide whether individual historical events apply to the active-well context.  

#### What to build


### 3.1 Candidate cascade

Filter and rank wells through:  
Surface radius  
→ formation availability  
→ downhole proximity  
→ trusted structural domain, if available  
→ operational context  
→ record quality  

### 3.2 Analog factors

Evaluate:  
- Target-interval separation  
- Formation match  
- Alignment confidence  
- Hole size  
- Inclination  
- Mud system  
- Mud weight/ECD context  
- Pressure context  
- Technology era  
- Record quality  

### 3.3 Event-specific transfer policies

Implement separate policies by risk.  
Mud-loss policy:  
- Same formation  
- Similar hole section  
- Comparable ECD/mud context  
- Alignment quality  
- Source quality  
Stuck-pipe policy:  
- Inclination  
- Overbalance  
- Operation state  
- Hole section  
- Exposure and stationary behavior  
Kick policy:  
- Formation and pressure context  
- Mud-weight context  
- Gas/influx evidence  
- Trusted structural relationship  

### 3.4 Blockers, penalties, and unknowns

Do not collapse all factors into one unexplained score.  
Return:  
{  
  "decision": "included",  
  "support": [  
    "same formation",  
    "350 m target-interval separation"  
  ],  
  "penalties": [  
    "different mud system"  
  ],  
  "unknowns": [  
    "structural domain unavailable"  
  ]  
}  
Missing information may reduce confidence but must never improve it.  

### 3.5 Explainability interface

Support:  
- Why this well?  
- Why not this well?  
- Why this event?  
- What data is missing?  
- Which factor blocked transfer?  

#### Completion criteria

- Expected synthetic analogs are selected.  
- Known poor analogs are excluded or penalized.  
- Each decision includes reasons.  
- Missing factors never strengthen transferability.  
- Policies differ appropriately by event type.  

## Phase 4 — Coverage-aware historical evidence engine


#### Objective

Combine transferable events without confusing absent data with safe outcomes.  

#### What to build


### 4.1 Evidence classification

For each aligned risk interval:  
SUPPORT  
Transferable analog where event occurred  

COUNTER  
Transferable analog with verified coverage and no event  

UNKNOWN  
Potential analog without adequate coverage  

### 4.2 Weighted aggregation

Optionally calculate internal evidence statistics:  
p_hat = (Σwᵢyᵢ + α) / (Σwᵢ + α + β)  

n_eff = (Σwᵢ)² / Σ(wᵢ²)  
Use only verified clean crossings as y = 0. Exclude unknown records.  

### 4.3 Evidence-state policy

Implement:  
- Lesson: relevant event exists, but evidence is limited  
- Elevated Historical Risk: sufficient transferable evidence exists  
- Warning: reserved for later live corroboration  

### 4.4 Evidence sentence generator

Generate deterministic summaries such as:  
Two transferable offsets experienced losses, three had verified clean crossings, and two lacked sufficient interval coverage.  


### 4.5 Evidence API

Create a look-ahead endpoint returning:  
- Formation  
- Projected interval  
- Evidence state  
- Supporting events  
- Clean crossings  
- Unknown records  
- Transfer reasons  
- Uncertainty  
- Historical mitigations  

#### Completion criteria

- Missing records never count as clean.  
- Support, counter, and unknown groups are visible separately.  
- Small evidence populations remain Lessons.  
- Risk states are reproducible.  
- Uncalibrated percentages are not shown as field probabilities.  

## Phase 5 — Live replay and current-well context


#### Objective

Create one reliable representation of the active operation and update it through simulated live data.  

#### What to build


### 5.1 CurrentWellContext resolver

Produce one canonical object containing:  
- Well ID and timestamp  
- Bit and hole depth  
- TVD  
- Current and next formation  
- Hole section  
- Inclination  
- Operation state  
- Mud weight and ECD  
- WOB, RPM, torque  
- Hookload and SPP  
- Flow in/out  
- Pit volume  
- Gas  
- Per-channel freshness  
Every value must include units and source metadata.  

### 5.2 Source precedence

When sources disagree:  
1. Trusted live value  
2. Deterministically computed value  
3. Explicit fallback estimate  
Serious disagreements produce:  
context_conflict = true  

### 5.3 Adapter interface

Implement:  
class LiveDataAdapter:  
    async def get_current_context(self, well_id): ...  
    async def stream_updates(self, well_id): ...  
Prototype adapters:  
- ReplayAdapter  
- CSVAdapter  
- ManualAdapter  
Future adapters:  
- REST  
- Database  
- WITSML/ETP  

### 5.4 Replay engine

Support:  
- Start  
- Pause  
- Resume  
- Reset  
- Speed control  
- Seek  
- Inject failure  
- Read current state  
- WebSocket streaming  

### 5.5 Freshness engine

For each channel track:  
- Value  
- Unit  
- Timestamp  
- Source  
- Quality  
- Freshness threshold  
States:  
- Fresh  
- Stale  
- Missing  
- Suspect  

### 5.6 Current formation resolver

Use current depth and formation tops to determine:  
- Current formation  
- Next formation  
- Distance to next top  
- Formation uncertainty  

#### Completion criteria

- Replay advances active-well depth.  
- Current context updates reliably.  
- Formation transitions occur correctly.  
- Stale-channel injection is detected.  
- Source conflicts are exposed.  
- Reset produces the same deterministic starting state.  

## Phase 6 — Complete mud-loss vertical slice


#### Objective

Connect every preceding module into one complete, believable use case.  

#### What to build


### 6.1 Historical mud-loss intelligence

Use:  
- Formation  
- Event severity  
- Depth interval  
- Hole section  
- Mud system  
- Mud weight/ECD  
- Mitigation  
- Outcome  
- Source evidence  

### 6.2 Look-ahead triggering

As the active bit approaches a projected interval:  
No state  
→ Historical Lesson  
→ Elevated Historical Risk  
The threshold must be configurable and labeled as prototype-calibrated.  

### 6.3 Live corroboration

During the applicable operation state, assess:  
- Flow-in/flow-out deficit  
- Pit-volume decline  
- ECD behavior  
- Mud trend  
- Channel freshness  
Do not evaluate drilling indicators as if they were equally meaningful during tripping, cementing, or static operations.  

### 6.4 Warning escalation

Escalate only when:  
- Historical state is Elevated  
- Active well is approaching or inside the interval  
- Relevant live indicators corroborate the concern  
- Required channels are fresh and valid  

### 6.5 Alert lifecycle

Support:  
created  
→ acknowledged  
→ snoozed  
→ escalated  
→ resolved  
Enforce one active alert per:  
risk type + aligned stratigraphic interval  
Re-notify only for:  
- Escalation  
- New material evidence  
- Snooze expiry  

### 6.6 Evidence-backed alert content

Show:  
- Risk type  
- Evidence state  
- Formation and projected interval  
- Uncertainty  
- Supporting events  
- Clean crossings  
- Unknown coverage  
- Live corroboration  
- Transfer reasons  
- Missing data  
- Historical mitigation and outcome  
- Source links  

### 6.7 Safe recommendation language

Use:  
- Verify  
- Review  
- Prepare  
- Consider  
Do not prescribe numeric drilling-control changes.  

#### Completion criteria

A single replay demonstrates:  
Historical Lesson/Elevated state  
→ active well approaches interval  
→ fresh live signals corroborate  
→ Warning  
→ engineer opens complete evidence chain  
→ alert is acknowledged and resolved  

## Phase 7 — Secondary risk modules


#### Objective

Show extensibility without pretending all risks are equally mature.  

### 7.1 Stuck-pipe module

Build:  
- Historical stuck-pipe retrieval  
- Formation and trajectory context  
- Operation-state binding  
- Torque trend  
- Hookload deviation  
- SPP trend  
- Stationary-duration indicator  
Label it as partial decision support, not a complete predictor.  

### 7.2 Kick/overpressure module

Build conservatively using:  
- Historical kick/influx events  
- Formation and pressure context  
- Mud-weight context  
- Pit gain  
- Flow-out greater than flow-in  
- Gas rise  
- Operation-state gating  
Do not build or claim a black-box kick classifier.  

### 7.3 Torque/dysfunction module

Show supporting indicators:  
- Torque residual  
- ROP/WOB/RPM context  
- Optional MSE  
- Trend changes  
MSE must not be presented as a standalone stuck-pipe predictor.  

### 7.4 Cementing module

Implement as historical planning intelligence:  
- Cement-job records  
- Casing interval  
- Cementing problems  
- Remedial actions  
- Outcomes  
No fabricated real-time cementing model is necessary.  

#### Completion criteria

- Every secondary module uses the common evidence framework.  
- Maturity is visible.  
- No module makes unsupported accuracy claims.  
- Mud loss remains the only fully polished vertical slice.  

## Phase 8 — Dashboard and workflow integration


#### Objective

Turn the engines into a coherent field and office user experience.  

#### What to build


### 8.1 Next Interval Brief

Make this the default page.  
Show:  
- Active well  
- Current depth  
- Current formation  
- Next formation  
- Distance ahead  
- Upcoming risk intervals  
- Evidence state  
- Support/counter/unknown counts  
- Live freshness  
- Historical lessons  
- Active alerts  

### 8.2 Look-Ahead depth strip

Display:  
- Formation tops  
- Uncertainty bands  
- Casing points  
- Historical event projections  
- Current bit position  
- Risk windows  
- Evidence states  

### 8.3 Map

Display:  
- Active well  
- Radius control  
- Offset wells  
- Surface distance  
- Target-depth distance  
- Relevance status  
Include the ranking-swap demonstration.  

### 8.4 Compare view

Align offset wells by formation rather than raw screen position.  
Show:  
- Formation intervals  
- Event locations  
- Clean crossings  
- Mud/casing context  
- Alignment uncertainty  

### 8.5 Evidence explorer

Expose:  
Alert  
→ risk evidence  
→ transfer assessment  
→ historical event  
→ source span  
→ document page  
Clearly label FACT, COMPUTED, and INFERRED information.  

### 8.6 Document viewer

Show:  
- Original page  
- Highlighted source span  
- Extracted fields  
- Confidence  
- Review status  

### 8.7 Review queue

Allow reviewers to:  
- Accept extraction  
- Correct extraction  
- Resolve alias conflicts  
- Correct units/depths  
- Quarantine an event  
Prioritize items affecting the active look-ahead.  

### 8.8 Simplified rig view

Show only:  
- Current/next formation  
- One important alert  
- Evidence sentence  
- Key live signals  
- Acknowledge control  
- “Why?” and source controls  

### 8.9 Validation page

Display:  
- Held-out replay results  
- Baseline comparisons  
- Alert counts  
- Hits and misses  
- Lead distance  
- Evidence coverage  

#### Completion criteria

A user can identify the active risk and understand its reason in approximately 20 seconds.  

## Phase 9 — Grounded “Ask NWIS”


#### Objective

Allow natural-language queries without making the language model responsible for risk calculations.  

#### What to build


### 9.1 Query planner

Convert a question into structured operations:  
Question  
→ intent  
→ wells/formations/events requested  
→ deterministic API calls  
→ source retrieval  

### 9.2 Deterministic tool layer

Provide tools for:  
- Well lookup  
- Formation lookup  
- Event filtering  
- Offset selection  
- Alignment  
- Evidence retrieval  
- Mitigation retrieval  
- Alert lookup  

### 9.3 Evidence retrieval

Query structured data first. Retrieve document passages only after identifying relevant records.  

### 9.4 Response format

Answers should separate:  
- Facts  
- Computed pattern  
- Interpretation  
- Gaps and uncertainty  
- Sources  

### 9.5 Numeric verification

Every number in an answer must be:  
- Returned by a deterministic tool, or  
- Directly present in cited source evidence.  

### 9.6 Refusal behavior

If evidence is insufficient, state what is missing instead of generating an answer.  

#### Completion criteria

- Questions return cited, grounded answers.  
- The LLM does not calculate core risk.  
- Unsupported numbers are rejected.  
- Insufficient evidence produces a clear limitation.  
- Prompt text inside uploaded documents cannot invoke tools.  

## Phase 10 — Validation, hardening, and final demonstration


#### Objective

Prove that the system behaves correctly, fails safely, and can be demonstrated repeatedly.  

#### What to build


### 10.1 Automated engineering tests

Cover:  
- Unit conversion  
- Datum handling  
- Formation aliases  
- Minimum-curvature calculations  
- 3D separation  
- Formation projection  
- Uncertainty propagation  
- Coverage rules  
- Transferability blockers  
- Freshness gating  
- Alert deduplication  
- Alert transitions  
- Provenance reconstruction  

### 10.2 Extraction gold set

Manually label 30–50 representative pages.  
Measure:  
- Event-type precision and recall  
- Depth extraction accuracy  
- Formation correctness  
- Mitigation/outcome extraction  
- Source-span grounding  
- Percentage requiring review  

### 10.3 Blind held-out replay

Procedure:  
1. Select a held-out active well.  
2. Hide its future events.  
3. Allow only offset-well history.  
4. Replay the active well.  
5. Record NWIS alerts.  
6. Reveal the hidden truth.  
7. Score hits, misses, and warning distance.  

### 10.4 Baselines

Compare against:  
1. Surface-nearest wells  
2. Same-formation equal weighting  
3. Fixed similarity weights  
4. Keyword/document retrieval  
Show both a visual case and aggregate results.  

### 10.5 Metrics

Prioritize:  
- Alert precision  
- Severe-event recall  
- Lead distance  
- Alerts per 1,000 metres  
- False negatives  
- Projected interval overlap  
- Evidence sufficiency  
- Source coverage  

### 10.6 Controlled failure scenario

Recommended demonstration:  
- Historical state is Elevated.  
- Flow-out becomes stale.  
- The replay continues.  
- NWIS refuses to escalate.  
- UI explains that live corroboration is incomplete.  
Alternative:  
- Remove a formation top.  
- Alignment uncertainty widens.  
- State drops to Lesson rather than showing false precision.  

### 10.7 Security and safety hardening

Verify:  
- Uploaded text is treated as untrusted  
- Extraction models have no tool access  
- No rig write-back exists  
- Sensitive data stays within configured storage  
- Important actions are audited  
- Model and rule versions are recorded  

### 10.8 Demo reset and packaging

Create:  
- One-command startup  
- Deterministic database seed  
- Replay reset  
- Demo-mode configuration  
- Backup video  
- Offline-safe dependencies  
- Claim ledger  
- Architecture diagram  
- Five-minute script  

#### Completion criteria

All 15 critical acceptance tests from the design document pass, including extraction grounding, downhole ranking, formation projection, evidence separation, warning escalation, stale-channel suppression, source traceability, and deterministic reset.  

## Additional Phase 0.5 — Documentation-style frontend

This additional phase was requested after Phase 0 and before Phase 1.

### Objective and full scope

Build a React frontend with Stripe-documentation structure/density and strictly black-on-white UI chrome.

- Tokens: white #FFFFFF background; #000000 headings; #111111 body; #6B6B6B secondary; #E5E5E5 borders; #F7F7F7 code/table headers. Black underlined links. At most one muted accent inside data only.
- Layout: bordered top bar with wordmark, search and command-key hint, utility links; approximately 260 px grouped/collapsible left navigation; approximately 680 px reading column; approximately 220 px sticky, scroll-aware contents rail; breadcrumbs and previous/next navigation.
- Where relevant, explanatory text beside a sticky request/code/response example.
- Components: light code blocks with language tabs and copy; inline code; white bordered Note/Warning callouts with black left rule; field/parameter tables; numbered steps with vertical rule; black primary and outlined secondary buttons; unfilled monospace status tags; empty/loading/error states.
- Typography: Inter/system UI and JetBrains Mono/monospace; 12/14/16/20/28/40 px scale; 400/500/600 weights; body 16 px at 1.6; title 40 px/600 with tight tracking.
- Spacing: 8/16/24/32/48/64 px scale; 1 px rules; radius at most 4 px.
- Screens: overview, next-interval brief, offsets/map, formation comparison, evidence/detail, documents/upload, review, Ask NWIS preview, validation preview, rig view and settings.
- Dense app tables: sticky headers, right-aligned monospace numerals, ordinary input filters.
- Responsive behavior: collapse right contents rail first, then left navigation into a menu.
- Semantic HTML, visible focus rings, WCAG AA contrast, keyboard operation and command-key search.
- Ban gradients, shadows, blur/glass, glows, neon, blobs/particles, colored UI palettes, emoji feature grids, large radii, marketing hero/hype copy, lorem ipsum and decorative animation. Only 100–150 ms color/border transitions are allowed.
- Deliver design brief, code with centrally reused tokens, and a banned-list self-review.

### Completion criteria

All screens render with meaningful NWIS content; actions and preview boundaries are honest; required components work; keyboard/responsive/contrast checks pass; design restrictions are verified. Backend engines are not part of Phase 0.5, but later integrations must retain this system.

# Part II — Implementation audit and completion roadmaps


## Phase 0 — Contracts and project foundation

**Status:** Partially implemented. The local FastAPI/React/SQLite skeleton works.

### Implemented evidence

Backend contracts/enums, configuration, health/meta routes, persistent records, seed/bootstrap, API client, frontend routing/tokens/states and Compose/PostGIS initialization exist. See [contracts](../backend/app/domain/contracts.py), [store](../backend/app/store.py), [Compose](../docker-compose.yml) and [unit/provenance notes](CONTRACTS.md).

### Missing work

- 0.2: complete canonical models for survey stations, aliases, coverage, operational/event context, transfer assessment, feedback and audit; full mirrored/generated TypeScript schema.
- 0.3: dedicated extraction-confidence and cause-type enums.
- 0.4: comprehensive density/pressure conversion and original-value/unit/datum/source records across entities.
- 0.5: version-tracked migration framework; domain-specific indexing beyond the generic record key and spatial index.
- 0.6: explicit versioned API compatibility strategy, unified application error envelope and structured application logging.
- Completion: CI lint/type/test/build pipeline and lint configuration.

### Partial work

Pydantic models cover selected entities while runtime modules also use dictionaries. Units are declared but conversion support is predominantly event depth. SQL initialization is not migration history. Repository responsibilities live largely within backend/app rather than the suggested modular directory tree; the example tree itself is not a functional acceptance failure.

### Unverified work

Clean Docker startup, PostgreSQL connection, PostGIS extension/index/trajectory persistence, migrations from zero and another-machine reproducibility. Optional Redis, document worker and pgvector are not mandatory omissions unless later architecture needs them.

### Roadmap and acceptance

1. Define every required entity and enum; add contract version and boundary validation; mirror frontend types and test schema parity.
2. Introduce a conversion/provenance service with declared density/pressure units and explicit datum handling; test originals and logged conversions.
3. Add tracked migrations and required indexes; test fresh creation, upgrades and data preservation on SQLite/PostgreSQL as applicable.
4. Standardize errors, request IDs, logging/redaction and API compatibility; add negative API tests.
5. Add CI and reproducible dependency setup; run lint, typecheck, tests and frontend build.
6. On a Docker-capable host, start the full stack from empty volumes, bootstrap, verify spatial records/indexes and render a seeded well.
7. Mark complete only with recorded clean-start evidence and reproducibility instructions.

## Phase 0.5 — Frontend

**Status:** Partially implemented; the major shell/screens are built.

### Implemented evidence

Central tokens, documentation layout, collapsible navigation, contents rail, command-key search, code-copy blocks, callouts, tables, responsive menu and screen states exist. Connected historical and simulation screens coexist with explicitly marked previews. See [design brief](PHASE_0_5_DESIGN.md), [App](../frontend/src/App.tsx) and [styles](../frontend/src/styles.css).

### Missing work

Interactive language tabs for code blocks (current blocks show a language label); a requirement-by-requirement component acceptance checklist.

### Partial work

Sticky split reading layouts and numbered-step presentation need comparison with the original brief across applicable screens. Some contents-rail anchor mappings need route-by-route verification. Later data integrations have not completed the full Phase 8 workflow.

### Unverified work

Formal WCAG AA, screen-reader, complete keyboard/focus, all breakpoint and every loading/empty/error-state acceptance. Existing visual/browser checks are not a comprehensive accessibility audit.

### Roadmap and acceptance

1. Audit each brief requirement against each applicable screen; finish tabs, sticky examples and step styling.
2. Check anchor targets and scroll-aware highlighting, menu/search focus, Escape behavior and focus restoration.
3. Exercise all states and responsive breakpoints, including dense table overflow.
4. Run contrast, keyboard and screen-reader checks; repair violations.
5. Repeat banned-list review and production build; attach screenshots and acceptance results.

## Phase 1A — Synthetic field generator

**Status:** Partially implemented.

### Implemented evidence

24 seeded wells, active held-out well, three structural domains, survey inputs, formation variation/uncertainty, casing/mud programmes, missing records, surface/downhole ranking swap, latent mud-loss generation, isolated truth, label-free replay and 12 watermarked PDFs (two scanned). See [generator](../backend/app/generator.py).

### Missing work

- 1A.4: planted stuck-pipe, kick/influx, torque dysfunction and cementing examples.
- 1A.6: separate held-out-event, expected-interval and generator-metadata manifests.
- 1A.7: structured report tables, WCR variety and controlled noise/format inconsistencies.
- Consistent specified synthetic_flag propagation, including nested records, exports and derived artifacts.

### Partial work

The hidden causal model is a mud-loss demonstration, not a broad multi-risk field model. Programmes/event operational context are sparse. Truth is one offline JSON file rather than the complete evaluation manifest.

### Unverified work

Coverage of the planned event/format matrix and deterministic generation of the future expanded dataset.

### Roadmap and acceptance

1. Expand configuration with multi-risk event and clean/missing cases plus pressure/mud/era/exposure context needed by Phase 3.
2. Preserve survey-first geometry; make all fixtures reproducible and visibly synthetic.
3. Emit separated truth/manifests with seed, version, expected intervals and held-out labels; keep runtime imports/storage access isolated.
4. Generate WCR/DDR narratives, tables, multiple units, abbreviations, noisy layouts and scans.
5. Test repeatability, >=20 wells, held-out exclusion, ranking swap, event/clean/missing populations, watermarking and inaccessible hidden truth.

## Phase 1B — Historical document intelligence

**Status:** Partially implemented.

### Implemented evidence

Native PDF/TXT/Markdown and local OCR ingestion, per-page/line bounding boxes, event-local MD extraction, feet conversion, bounded labeled event chains, review/quarantine, source spans and interval coverage exist. At least ten reports and a real OCR case are covered. See [ingestion](../backend/app/ingestion.py) and [tests](../backend/tests/test_ingestion.py).

### Missing work

- 1B.1: explicit public/private classification and reliable document-type metadata.
- 1B.3: structured headers, paragraphs, tables, operation sections, depth columns, remarks and summaries.
- 1B.4: comprehensive date, mud-weight, hole-size, well-name and abbreviation extraction.
- 1B.7: sourced formation gazetteer with basin/field, match confidence and reviewed fuzzy matches.
- 1B.9: date coverage alongside depth coverage.

### Partial work

Native quality routing largely uses text length, not robust quality/layout analysis. Narrative extraction is schema-backed but label-dependent. Numerical grounding is focused on depth rather than every extracted number/conversion. Unknown aliases enter review, but fuzzy resolution is absent.

### Unverified work

Generalization beyond the simple fixture formats; complete numerical provenance across tables/narratives. Gold-set metrics belong to Phase 10, but extraction acceptance fixtures are required now.

### Roadmap and acceptance

1. Extend upload metadata and source schemas with classification, dates, document type and structured layout.
2. Detect usable native text, tables/sections and mixed native/scanned pages while preserving coordinates.
3. Implement deterministic fields/abbreviation rules and typed event chains with event-specific context.
4. Validate every numeric field against an exact source token or logged conversion; quarantine unsupported values.
5. Add gazetteer and confidence-based review; preserve original names and reviewer decisions.
6. Add date/interval coverage with conservative verification; test contradictions and ambiguous negation.
7. Verify >=10 varied reports, OCR, grounded chains, unsupported-number rejection, quarantine exclusion and persistent coverage.

## Phase 2 — Geometry and stratigraphic alignment

**Status:** Partially implemented; core numerical functionality is tested.

### Implemented evidence

Minimum-curvature TVD/East/North, bounded interpolation, surface-radius API, sampled corresponding-formation 3D separation, fractional projection, top/base envelopes, fallback hierarchy and geological/datum blockers. See [geometry](../backend/app/geometry.py) and [tests](../backend/tests/test_geometry.py).

### Missing work

Quantitative datum-uncertainty propagation; consistent complete input/provenance records for every fallback. Exposed dogleg-severity diagnostics where useful are not provided.

### Partial work

Formation review quality must be explicitly enforced through the “verified top/base” hierarchy. Current uncertainty uses simplified formation uncertainty, not separately modeled top/base/datum components. Mean/minimum separation uses 21 corresponding-fraction samples; it is not an exact global closest-approach calculation (which the source plan does not require).

### Unverified work

PostGIS persistence and spatial-index execution; numerical robustness across broader surveys, datum uncertainties and degraded formation review states.

### Roadmap and acceptance

1. Model separate uncertainty/review fields and prohibit assumed verification.
2. Propagate datum uncertainty without converting unknown/mismatched datum into a safe match.
3. Retain inputs, source, algorithm version and fallback reasons for every result.
4. Expose dogleg diagnostics if needed; test known paths, degeneracies, boundaries and degraded formations.
5. Verify PostGIS LineStringZ persistence/indexing on the full stack.
6. Record passing ranking-swap, projection, widening uncertainty, absent-formation and provenance tests.

## Phase 3 — Analog and event transferability

**Status:** Partially implemented.

### Implemented evidence

Radius/formation/geometry/trusted-domain gates, explainable weights, hole/mud/ECD/operation/source factors, event policies and missing-data penalties. See [engine](../backend/app/evidence.py) and [tests](../backend/tests/test_evidence.py).

### Missing work

Pressure, technology-era and explicit mud-weight factors; event/target-interval inclination; stuck-pipe overbalance/exposure/stationary comparisons; kick pressure/mud-weight/gas-influx comparisons.

### Partial work

Candidate ranking emphasizes geometry/structure; operational/source comparisons occur mainly at transfer level. Stuck pipe uses terminal inclination and missing-factor penalties. Kick/cementing policies conservatively mark context unmodeled. Declaring unknowns is safe behavior, but not completion of the required comparisons.

### Unverified work

Acceptance of the completed policy matrix on positive/poor analog fixtures for every required event type; engineering review of thresholds and mechanism direction.

### Roadmap and acceptance

1. Add grounded event-specific context, pressure, era and exposure fields using Phases 0–1.
2. Evaluate inclination at the applicable interval/event depth.
3. Implement separate loss/stuck/kick comparisons with explicit blockers, penalties and unknowns.
4. Include operational/source quality in candidate/transfer explanation without unexplained score collapse.
5. Add positive/negative/missing-factor tests per risk; prove missing factors never strengthen transfer.
6. Version policies and expose every why/why-not factor in the interface.

## Phase 4 — Coverage-aware historical evidence

**Status:** Complete for the current core phase scope; upstream completeness and external validation are not implied.

### Implemented evidence

SUPPORT/COUNTER/UNKNOWN plus EXCLUDED populations, verified reverse-envelope clean coverage, one contribution per well, internal weighted statistics, Lesson/Elevated policy, deterministic sentence, look-ahead API and versioned snapshots. Warning is not generated by historical evidence alone.

### Missing work

No major missing core item identified in 4.1–4.5. Broader source coverage and complete transfer mechanisms are Phase 1/3 dependencies, not proof that the current data is complete.

### Partial work

Explicit clean-statement recognition is conservative and narrow; broader source-format support follows Phase 1B. Internal scores remain uncalibrated, not field probabilities.

### Unverified work

Real-report and field validity, multi-worker deployment and PostgreSQL execution. These are not established by current synthetic SQLite tests.

### Roadmap and acceptance

1. Preserve completed invariants during upstream changes.
2. Rerun clean/unknown, contradiction, duplicate, interval-envelope and snapshot regression tests on richer data.
3. Confirm separated populations, limited-evidence Lessons and no probability/safe claims in UI.
4. Defer field calibration claims until Phase 10 evaluation; record deployment verification separately.

## Phase 5 — Live replay and current context

**Status:** Partially implemented.

### Implemented evidence

Canonical Pydantic context; observed/computed/fallback precedence; source conflicts; replay/CSV/manual interfaces; bounded CSV; explicit replay clock; manual UTC timestamps; quality injection and history; frontend play/pause/resume/frame advance. See [adapters](../backend/app/live.py), [routes](../backend/app/live_routes.py) and [UI](../frontend/src/LiveWorkspace.tsx).

### Missing work

- 5.1: mud weight, WOB, RPM, torque, hookload, SPP and gas channels with units/source metadata.
- 5.4: backend playback state, deterministic reset, speed selection, seek and WebSocket streaming.
- 5.5: channel-specific configured/exposed freshness thresholds.
- 5.6: explicit distance to next top and structured formation uncertainty.

### Partial work

Play/pause is frontend-driven, not a server playback scheduler. New run is not a same-run reset. CSVAdapter shares ReplayAdapter implementation rather than a separately exercised ingestion path. Some resolved fields have field-source labels rather than uniform value/unit/source metadata. Current formation/next formation exist, but transitions and boundary semantics need full acceptance coverage.

### Unverified work

Deterministic reset, seek semantics, WebSocket reconnect/backpressure and server playback controls because these are not yet built; mark them missing until built, then test. Full formation-transition/per-channel acceptance remains unverified.

### Roadmap and acceptance

1. Add all required channels, bounds, canonical units, null semantics and originals to schemas, CSV/manual forms and fixtures.
2. Define backend playback state with start/pause/resume/speed/seek/reset; preserve simulation clock consistency.
3. Specify reset/seek audit and alert isolation so historical notifications are never silently rewritten.
4. Add WebSocket delivery/reconnect/state snapshots and retain a safe polling fallback.
5. Return per-channel thresholds and full resolved-field provenance.
6. Add next-top distance/uncertainty and test crossing tops, missing bases, uncertain boundaries and stale bit depth.
7. Verify deterministic reset, quality failures, source conflicts, speed/seek, reconnect and multi-client behavior.

## Phase 6 — Complete mud-loss vertical slice

**Status:** Partially implemented.

### Implemented evidence

Historical evaluation connected to canonical context, individual uncertainty-window proximity, fresh flow/pit corroboration, drilling/time-coherence/conflict gates, persisted lifecycle/audit, restricted re-notification, exact evidence retrieval and safe recommendations. Isolated API tests demonstrate Elevated -> Warning, deduplication, acknowledgement, snooze and resolution. All 18 required-channel/bad-quality combinations block Warning.

### Missing work

Full extracted historical severity/depth intervals/event-specific mud context; mud-weight trend; complete configurable look-ahead policy; ready-to-run frontend demonstration of the entire required sequence.

### Partial work

Historical state is evaluated immediately for a fixed monitor window; it is not a complete depth-triggered no-state/Lesson/Elevated workflow. ECD/change is displayed rather than a fully developed contextual mud-trend assessment. Policy values mix constants and hard-coded literals. Alert identity is run+risk+fixed monitor interval, not a fully canonical aligned-window active-alert identity across relevant runs. Evidence details exist but need complete end-to-end acceptance.

### Unverified work

Complete UI sequence with real connected evidence/source navigation and actions; engineering/calibration review; production transactional deduplication. Positive tests use isolated controlled history, not the default working field. Default NO_EVIDENCE is honest, not a failure to fabricate a Warning.

### Roadmap and acceptance

1. Complete Phase 1B/3/5 dependencies and event-specific severity/interval/context.
2. Define configurable historical approach and escalation policies; replace literals with validated versioned configuration.
3. Bind look-ahead presentation/activation to depth and aligned intervals; preserve historical evidence independent of live Warning.
4. Add mud trend with operation/quality gates; do not introduce autonomous operating commands.
5. Define canonical risk/interval alert scope, separate simulation namespaces intentionally and enforce deduplication transactionally.
6. Package an explicit, isolated synthetic demonstration dataset with disclosed reviews/assumptions; never alter user history to force results.
7. Run one frontend replay: historical concern -> approach -> fresh corroboration -> Warning -> evidence/source chain -> acknowledge -> resolve.
8. Repeat with stale flow-out, operation changes, missing data, conflicts and reset; show blocked gates.
9. Record reproducible UI/API evidence. Keep “uncalibrated” until justified calibration exists.

## Phase 7 — Secondary risk modules: separate roadmap

**Status:** Not started as complete modules. Existing historical retrieval/policies are partial prerequisites.

### Missing work

Functional stuck-pipe torque/hookload/SPP/stationary module; kick pit-gain/flow/gas module; torque residual/ROP-WOB-RPM module; cement-job planning intelligence and maturity presentation.

### Partial work

Event enums, some extraction phrases, common historical APIs and conservative stuck/kick/cement policies exist. They are not complete predictors or live engines.

### Unverified work

Integrated secondary-module behavior has not been verified. Existing historical tests do not establish the Phase 7 acceptance criteria.

### Scope and dependencies

Implement every 7.1–7.4 item in Part I. Depend on complete historical event/context extraction (1), geometry (2), event policies (3), common evidence (4), full telemetry (5) and Phase 6 safety/lifecycle patterns.

### Concrete roadmap

1. Add per-module required-channel/operation/maturity definitions and multi-risk fixtures.
2. Implement stuck-pipe indicators using applicable formation/inclination, overbalance, stationary exposure, torque, hookload and SPP.
3. Implement conservative kick evidence from pressure/mud history, pit gain, excess returns and gas; gate by operation/freshness.
4. Add torque residual/trend and ROP/WOB/RPM context; optional MSE must remain contextual, never a standalone stuck-pipe predictor.
5. Implement cement-job/casing/problem/remedial/outcome historical planning with source links; no fabricated live cementing model.
6. Reuse common evidence/audit, test missing/stale/operation cases and expose mechanism limitations.

### Completion criteria

All modules use common evidence and explicit maturity; reasons/sources are visible; no unsupported accuracy or black-box kick claim; mud loss remains the only fully polished vertical slice.

## Phase 8 — Dashboard/workflow integration: separate roadmap

**Status:** Partially implemented ahead of sequence, not “not started.”

### Missing work

Complete connected depth strip with tops/uncertainty/casing/event projections/current bit/windows/states; next-top distance and upcoming-window integration; real validation-results page; complete review prioritization/alias resolution; measured 20-second comprehension acceptance.

### Partial work

Real Next Interval Brief/Rig, offset map/radius/ranking, projection comparison, evidence, original-page highlights, upload and review screens exist. Compare is not a full aligned multiwell event/clean/mud/casing view. Brief is not the default landing page. Rig remains denser than the requested reduced interface. Validation is a preview.

### Unverified work

Complete alert-to-document provenance journey, all 8.1–8.9 workflows, comprehensive accessibility/responsiveness and timed usability acceptance.

### Scope and dependencies

Implement every 8.1–8.9 item in Part I. Depend on Phases 0.5–7 for real data/maturity; validation UI depends on Phase 10 results contracts. UI scaffolding may precede evaluation, but fixtures must remain labeled previews.

### Concrete roadmap

1. Make connected Brief the default; add distance ahead, upcoming intervals, counts, lessons, freshness and alerts.
2. Build a shared uncertainty-aware depth strip from backend geometry/formation data.
3. Finish map and aligned comparison with ranking-swap, clean crossings and programme context.
4. Standardize FACT/COMPUTED/INFERRED presentation and link alert -> snapshot -> transfer -> event -> span -> original page.
5. Finish field/alias/unit corrections, audit and look-ahead-impact review priority.
6. Reduce Rig to important alert, formations, key signals, acknowledgement and Why/source controls.
7. Integrate real held-out/baseline metrics when Phase 10 produces them.
8. Test all states, keyboard/mobile and timed comprehension with representative users.

### Completion criteria

A user identifies the active concern and its reason in approximately 20 seconds; all required screens use real data where claimed, preserve uncertainty and maturity, and navigate to original evidence.

## Phase 9 — Grounded Ask NWIS: separate roadmap

**Status:** Not started. Only a mock/preview question-answer screen exists.

### Missing work

Functional planner, constrained tool layer, structured-first retrieval, grounded response generation, numerical verification and insufficient-evidence refusal.

### Partial work

Underlying deterministic APIs and evidence/source storage are prerequisites; they are not a Q&A orchestration layer.

### Unverified work

No real grounded Q&A pipeline is available to verify; preview answers are not acceptance evidence.

### Scope and dependencies

Implement every 9.1–9.6 item in Part I. Depend on stable Phase 0 schemas/API compatibility and Phases 1–8 evidence/provenance. Hosted-model/provider selection, privacy and credentials must be explicitly configured if chosen. Semantic vectors are optional, not a prerequisite.

### Concrete roadmap

1. Define supported intents and typed planner output; validate well/formation/risk identifiers and ambiguous questions.
2. Create allowlisted read-only tools for well/formation/events/offsets/alignment/evidence/mitigation/alerts.
3. Retrieve structured records first, then authorized source passages; never consult hidden truth.
4. Keep risk calculation in deterministic engines; format facts, computed patterns, interpretations, gaps and citations separately.
5. Verify every generated number against tool/source output and conversions; reject unsupported claims.
6. Refuse insufficient evidence and keep uploaded instructions untrusted, unable to authorize tool use.
7. Test supported queries, ambiguity, empty/contradictory evidence, citation correctness, numeric mismatches and prompt injection.

### Completion criteria

Cited grounded answers, no LLM core-risk calculations, unsupported-number rejection, clear limitations and no document-driven tool invocation.

## Phase 10 — Validation/hardening/final demo: separate roadmap

**Status:** Partially implemented ahead of sequence through engineering tests and safety guards; the evaluation/demo programme is unfinished.

### Missing work

30–50-page extraction gold set; blind held-out runner/scoring; four baseline comparators; aggregate metrics; real validation UI integration; complete security/deployment assessment; deterministic replay reset; backup video, offline-safe packaging, claim ledger, architecture diagram and five-minute script.

### Partial work

60 tests cover many engineering/safety cases, generator output is deterministic, hidden truth is separated, review/alerts are audited and no rig write-back exists. Compose/bootstrap and failure injection exist. There is no complete acceptance matrix or scored validation report.

### Unverified work

All 15 original critical acceptance tests as a suite; production/multi-worker behavior; clean Docker/PostGIS deployment; sensitive-storage/privacy hardening; complete offline startup and deterministic end-to-end reset.

### Scope and dependencies

Implement every 10.1–10.8 item in Part I. Depend on completed Phases 0–9 and separate immutable evaluation truth. The original solution/design document supplies the exact 15 acceptance tests: transcribe and map them rather than inventing the missing list from memory.

### Concrete roadmap

1. Trace every requirement to code, fixture, test and result; add missing engineering/property/integration/browser tests.
2. Manually label 30–50 representative pages and score event precision/recall, depths, formations, chains, grounding and review rate.
3. Build blind replay that reads offset history only; record alerts before revealing isolated truth.
4. Run surface-nearest, equal-formation-weight, fixed-weight and keyword-retrieval baselines on the same held-out data without leakage.
5. Report precision, severe recall, lead distance, alerts/1,000 m, misses, overlap, sufficiency and source coverage with limitations.
6. Package Elevated + stale flow-out replay and degraded-alignment failure; record clear suppressed escalation.
7. Audit untrusted text, tool permissions, privacy/storage, action trails, versions, no write-back and deployment concurrency.
8. Finish one-command startup, seed/reset, demo mode, offline dependency strategy, video, diagrams, claims and script.
9. Execute all 15 acceptance tests from a clean environment and publish actual results, including failures.

### Completion criteria

All specified acceptance tests pass with reproducible evidence; blind evaluation and baselines are recorded; reset/demo repeat; no fabricated score or operational-accuracy claim.

# Cross-phase execution order

1. Close Phase 0 contracts/unit/migration/CI gaps.
2. Complete Phase 1A/1B fixtures and extraction, then Phase 2 uncertainty/provenance.
3. Complete Phase 3 policies and rerun Phase 4 regressions.
4. Finish Phase 5 channels/replay and Phase 6 configured end-to-end demonstration.
5. Finish Phase 0.5 accessibility/component acceptance alongside those integrations.
6. Only then advance functional development to Phase 7; finish Phase 8 workflow integration.
7. Implement Phase 9 grounding; complete Phase 10 evaluation/hardening/packaging. Test harness and metrics contracts may be developed earlier without claiming completed evaluation.

## Completion ledger rule

For each numbered requirement, record: implementation link, acceptance test, execution environment, result, remaining limitation and evidence artifact. Mark built-but-unexecuted items unverified, not complete. Update this file after actual implementation or verification; do not infer completion from a phase label, screenshot, mock page or total passing-test count.

## Source and maintenance notes

- Requirements source: C:/Users/omkud/OneDrive/Documents/Phase by Phase Implementation Plan 121.txt.
- Additional Phase 0.5 source: the user's black/white documentation-style frontend brief.
- Audit sources: backend/app, backend/tests, frontend/src, docker-compose.yml, backend/migrations and existing docs.
- Detailed implementation notes: [Phases 1–2](PHASE_1_2.md), [Phases 3–4](PHASE_3_4.md), [Phases 5–6](PHASE_5_6.md).
- Earlier notes describe their original delivery dates and can contain superseded “deferred” or “complete” wording. This file is the consolidated status baseline.
- No precise completion percentage is claimed: requirements differ substantially in size, and counting bullets would misrepresent progress.
