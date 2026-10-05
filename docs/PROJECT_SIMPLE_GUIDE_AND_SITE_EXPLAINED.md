# NWIS explained simply — the project plan and the website

Updated: 4 October 2026

This is the plain-language companion to [the detailed plan, status and roadmap](PROJECT_PHASE_PLAN_STATUS_ROADMAP.md). It explains the same project without assuming software or drilling knowledge, then explains the pages and controls in the current website.

This guide describes requirements and current behavior. It does not implement features or change data. The detailed document remains the requirement-by-requirement reference.

## Read this first

The project has working prototype features through Phase 6, but **Phases 0–6 are not all fully finished**. Some later-phase screens and tests were built early. A page appearing in the menu does not mean its engine has been implemented.

The current data is synthetic: invented for development and demonstration, not actual Oil India field data. The replay is a simulation, not a connection to a drilling rig. Warnings use uncalibrated demonstration rules, not proven field predictions. The site cannot control drilling equipment.

The latest recorded backend check passed 60 tests. This means those particular checks passed; it does not mean the complete project specification passed.

# Section 1 — What the project is trying to do

## The problem

Before drilling deeper, an engineer wants to know:

- Did nearby wells encounter problems in the rock we are about to enter?
- Were their drilling conditions similar enough for that experience to matter?
- What happened, what did they do, and what was the outcome?
- Do current measurements support the historical concern?
- Can we see the actual report behind the answer?

Those answers are usually spread across drilling reports, surveys and operational records. Nearby wells may bend away from one another underground. Rock layers can occur at different depths. A missing report does not mean an interval was trouble-free.

NWIS brings those records together. It is designed to help an engineer review evidence, not replace the engineer or automatically operate the rig.

## The intended journey

Historical report → extracted event → human review where needed → comparable nearby well → projected rock-layer interval → historical evidence → fresh simulated measurements → advisory with sources.

For example, suppose an older well recorded mud losses in the lower part of a rock layer. NWIS checks whether that well is a suitable comparison, estimates where the same part of the layer is in the active well, and shows the uncertainty. Only if the historical evidence is strong enough and valid current signals agree can the simulation escalate to Warning.

## Why the phases are separate

Each phase supplies information needed by the next one. A good-looking warning screen cannot compensate for incorrect depths, unreliable extraction or missing source evidence. The build order is intended to establish those foundations first.

## Important words in ordinary language

| Term | Simple meaning |
| --- | --- |
| Active well | The well we are currently planning or simulating drilling in. |
| Offset well | Another well used for comparison. |
| Formation | A named rock layer or geological unit. |
| Interval | A range, such as 2,460–2,580 metres, rather than one exact depth. |
| MD: measured depth | Distance along the well's path. A bending well has a longer path than its straight vertical depth. |
| TVD: true vertical depth | How far vertically below the reference point a position is. |
| Datum | The agreed reference point from which depth is measured. Different reference points can make apparently equal depths unequal. |
| CRS | The coordinate system used to describe positions. Coordinates cannot be compared safely without knowing their reference system. |
| Survey station | A recorded depth, tilt and direction used to reconstruct the well path. |
| Inclination / azimuth | How much the well tilts, and which direction it points. |
| Minimum curvature | A calculation that connects survey readings with smooth bends to estimate the underground path. |
| Analog / transferability | A useful comparison, and whether a particular historical event is relevant to the active well. |
| Coverage | Evidence that a report actually describes a particular depth range or date range. |
| Clean crossing | A relevant interval with verified reporting and an explicit no-event statement. It is not inferred from silence. |
| Provenance / source span | Where information came from, including the exact report passage or calculation. |
| OCR | Reading text from an image or scanned page. |
| WCR / DDR | Well Completion Report / Daily Drilling Report. |
| Mud loss | Drilling fluid is lost into the surrounding formation instead of all returning as expected. |
| Mud weight / ECD | Fluid density, and equivalent circulating density: density-equivalent pressure while fluid is circulating. They are related but not interchangeable. |
| WOB / RPM / ROP | Weight on bit / rotation speed / rate of penetration. |
| Torque / hookload / SPP | Rotational load / load supported by the hook / standpipe pressure. |
| Pit volume / flow in and out | Fluid held in tanks, and fluid going into and returning from the well. |
| Kick / influx | Formation fluid enters the well. |
| Overbalance | Well pressure exceeds formation pressure. |
| Casing / cementing | Steel pipe installed in the well, and cement used to secure/seal it. |
| Hidden truth / held-out well | Known answers kept apart from the application so evaluation can test it fairly. |
| Backend / frontend / API | The data and calculation service / the website / the agreed way they communicate. |
| Database / migration / CI | Stored records / controlled changes to database structure / automatic checks when code changes. |
| SQLite / PostgreSQL / PostGIS | The current local database / the planned server database / its spatial-data extension. |
| WebSocket | A connection that lets the server continuously send updates instead of the page repeatedly asking. |

## What the status words mean

- **Complete:** the stated scope has been built and checked. Phase 4 is complete for its current core scope, not proof of a fully completed project.
- **Partially implemented:** useful work exists, but some requirements are absent or incomplete.
- **Not started:** the functional feature has not been built. A mock page does not count.
- **Missing:** not built yet.
- **Partial:** built in a smaller or unfinished form.
- **Unverified:** built or configured, but the relevant test or deployment has not been confirmed. This does not automatically mean it is broken.

# Section 2 — Every phase explained

## Phase 0 — Give the whole project a common foundation

**In one sentence:** make every part of the system agree on what records mean and how to exchange them.

### What the numbered items mean

- **0.1 Repository structure:** organize the code into understandable areas for the website, server, document reading, fake-data generator, tests and deployment. The example folder names are suggestions, not the main goal.
- **0.2 Shared contracts:** define standard record shapes for wells, surveys, formations and aliases, formation boundaries, documents and passages, coverage, events and event conditions, mitigation/outcome, current context, comparisons, evidence, alerts, feedback and audit history. Both the server and website must understand the same fields.
- **0.3 Shared labels:** use agreed choices for event type, operation, evidence strength, alert stage, data freshness, extraction confidence, origin, coverage, cause and review status. This prevents two modules from using different words for the same thing.
- **0.4 Units and reference points:** convert depths to metres, keep MD separate from TVD, agree density/pressure units, declare coordinates, use UTC timestamps, and retain original measurements and sources.
- **0.5 Database:** set up PostgreSQL/PostGIS, controlled database upgrades, starting data, lookup indexes and local report storage. Vector search is optional and only useful when semantic retrieval is added.
- **0.6 Application skeletons:** start FastAPI and React, connect them, show a seeded well, provide health checks, consistent errors, logging, API compatibility, routes, shared styling and loading/error states.
- **0.7 Development setup:** package the server, website and database with Docker Compose so another developer can run the same stack. Workers/Redis are optional when needed, not compulsory decoration.

### Current position and how to finish

**Partially implemented.** The local website/server/SQLite system runs. Some record definitions and unit conversions are incomplete. Tracked migrations, comprehensive logging/errors/versioning and automatic lint/test CI remain unfinished. Docker/PostGIS are configured but unverified on this machine.

Finish the shared records and conversions, introduce tracked database upgrades, add automatic checks, then prove that a fresh computer can start the stack and display a well. This phase is finished when that clean start is reproducible—not merely when the existing local instance runs.

## Phase 0.5 — Build an understandable website shell

**In one sentence:** make the project usable before all its engines are ready.

This extra phase came from the user's frontend request. The site should feel like calm technical documentation: white background, black text, grey borders, narrow reading areas, top search, grouped left navigation and right-hand page contents.

The brief also requires reusable typography/spacing, code-copy blocks with language tabs, field tables, numbered steps, plain callouts, black/outlined buttons, status labels, responsive menus, keyboard navigation and designed empty/error/loading states. Gradients, shadows, decorative animation and marketing-style layouts are banned. Colour belongs only in data, with at most one muted accent.

**Partially implemented.** The shell and major pages exist. Language tabs and some presentation acceptance remain unfinished; full keyboard, screen-reader and accessibility checks are unverified. Backend functionality is not required to finish the original visual shell, but previews must be labeled honestly.

Finish the component checklist, links and focus behavior, test every screen size/state, check contrast and accessibility, then repeat the design restrictions review.

## Phase 1A — Create realistic practice data

**In one sentence:** build an invented field that lets us test the system without pretending to have real field data.

- **1A.1 Field configuration:** make 20–40 wells with active/historical roles, locations, structural regions, curved paths, uncertain rock boundaries, hole sizes, casing/mud plans, events and intentionally missing records. Every synthetic record must be clearly identified.
- **1A.2 Surveys:** generate depth, tilt and direction readings. Calculate the underground coordinates later, so the geometry engine gets a real test.
- **1A.3 Geology:** vary layer depths and thicknesses across wells; include uncertainty and optionally a layer that disappears or structural boundaries.
- **1A.4 Events:** include mud loss, stuck pipe, kick/influx, torque dysfunction and cementing issues, with mud loss receiving the richest detail.
- **1A.5 Hidden generator:** create events from factors such as weak zones, ECD interaction, location, operating conditions and random variation. Keep those hidden factors away from the application.
- **1A.6 Truth files:** keep expected events, intervals and generator settings separately for evaluation. Runtime APIs must not expose them.
- **1A.7 Reports:** generate watermarked WCR/DDR-style documents with narratives, tables, depths, actions, outcomes, messy formatting and at least one scan.

**Partially implemented.** There are 24 wells, 12 reports including two scans, survey/geology variation, missing records and isolated mud-loss truth. The full event mix, richer reports, separate truth manifests and consistent nested synthetic flags are missing or partial.

Finish those fixtures, then verify repeated generation gives the same results, the active future stays hidden, and the nearest surface well differs from the nearest underground well in the intended example.

## Phase 1B — Turn reports into traceable records

**In one sentence:** read a report and extract useful facts without inventing them.

- **1B.1 Ingestion:** accept PDF/text, associate it with a well, and record its title, type, pages, scan status and synthetic/public/private designation.
- **1B.2 Text or OCR:** use selectable text where usable; otherwise render that page and read its image. A document can contain both kinds.
- **1B.3 Layout:** distinguish headings, paragraphs, tables, daily operations, depth columns, remarks and event summaries. Retain page locations so the user can check the original.
- **1B.4 Rule-based fields:** read dates, depths, units, well and formation names, mud weight, hole size and abbreviations using predictable rules first.
- **1B.5 Event chain:** link what was noticed, which event occurred, a stated cause, the response and the outcome. Missing causes must stay unknown.
- **1B.6 Number checks:** every extracted number must appear in the report or come from a recorded conversion. Unsupported numbers are rejected.
- **1B.7 Formation names:** match aliases against a sourced list of accepted formation names and basin/field information. Uncertain spelling matches require review.
- **1B.8 Review:** mark records verified, automatically accepted, needing review or quarantined. Quarantined events cannot influence risk alerts.
- **1B.9 Coverage:** record which depths and dates a report really covers, and whether that coverage is verified, probable or unknown.

**Partially implemented.** PDF/text/OCR, source highlighting, grounded depths, labeled event chains, reviews and depth coverage work. Tables/sections, dates, richer operating fields, full number validation, a complete formation dictionary and public/private metadata are incomplete. Performance on varied real report formats is unverified.

Finish the parser and review records, test varied reports/scans, and prove that poor extraction is reviewed, unsupported values are rejected and event/response/outcome remain linked.

## Phase 2 — Find wells underground and compare equivalent rock

**In one sentence:** compare the same geological interval, not just the same surface location or depth number.

- **2.1 Trajectories:** calculate vertical depth and east/north displacement from surveys; save the 3D path. Where useful, show how sharply it bends.
- **2.2 Surface radius:** first find wells within the requested distance from the active well at the surface.
- **2.3 At-depth distance:** compare their relevant underground segments and return underground distance separately from surface distance.
- **2.4 Formation alignment:** locate an event within its source layer, then use that relative position in the active layer.
- **2.5 Uncertainty:** uncertain tops/bases/reference points, missing bases and weak alignment must widen the projected depth range.
- **2.6 Fallbacks:** use reliable top/base first; then top plus estimated thickness; then vertical-depth comparison; only lastly raw MD, clearly labeled low quality.
- **2.7 Blockers:** if the target layer is absent, do not project the event as though it exists.

Example: an event halfway through a layer from 2,000 to 2,400 m projects halfway through a target layer from 2,200 to 2,600 m—around 2,400 m before uncertainty is added. Equal raw depths would miss that relationship.

**Partially implemented, with the main numerical calculations tested.** Datum uncertainty and consistent fallback input records need completion. Spatial database execution is unverified. Finish those details, verify known paths/ranking changes/wider uncertainty and preserve the inputs and calculation version for every result.

## Phase 3 — Decide which comparisons deserve attention

**In one sentence:** a nearby event only matters if the well and event conditions are relevant.

- **3.1 Candidate cascade:** narrow wells by radius, layer availability, underground distance, trusted structure, operating context and record quality.
- **3.2 Factors:** compare separation, formation, alignment, hole size, inclination, mud system, mud weight/ECD, pressure, technology era and source quality.
- **3.3 Separate policies:** mud loss uses layer/hole/mud/ECD/alignment/source comparisons; stuck pipe uses inclination, overbalance, operation, hole section and stationary exposure; kick uses pressure/mud/gas/influx and trusted structure. One rule must not be reused blindly for all risks.
- **3.4 Reasons:** return positive reasons, penalties, unknowns and hard blockers separately. A missing field must never improve a comparison.
- **3.5 Explainability:** answer why this well, why not another, why this event, what is missing and what blocked it.

**Partially implemented.** Explainable geometry/context/source gates work. Pressure/era/mud-weight comparisons and complete stuck/kick mechanisms are missing. Some policies currently penalize missing information instead of evaluating a built mechanism.

Finish grounded event conditions and separate policies; test good, poor and incomplete comparisons for each risk. Historical policies are required here even though full secondary live modules belong to Phase 7.

## Phase 4 — Combine evidence without treating silence as safety

**In one sentence:** separate events, documented clean intervals and missing information.

- **4.1 Groups:** SUPPORT means a relevant event; COUNTER means verified comparable clean coverage; UNKNOWN means information is insufficient. The application also shows EXCLUDED for blocked comparisons.
- **4.2 Weighting:** let more relevant/reliable records contribute more. Count each well once rather than boosting evidence by duplicating reports. Unknown records do not count as clean results.
- **4.3 State:** a relevant event can justify a Lesson; sufficient comparable evidence can justify Elevated. Historical evidence alone cannot produce Warning.
- **4.4 Summary sentence:** describe how many supporting, clean and unknown wells exist in plain terms.
- **4.5 Look-ahead response:** return layer, projected range, strength, events, clean crossings, unknowns, reasons, uncertainty and past responses.

The internal weighted statistic is a summary of this evidence, **not the chance of a field incident**. The effective well count describes how balanced the usable contributions are; it is not just the number of reports uploaded.

**Complete for the current core scope.** Wider report interpretation and full comparisons still depend on earlier phases. Real-field accuracy is unverified. Preserve the evidence rules and rerun tests whenever upstream data or policies change.

## Phase 5 — Keep one trustworthy picture of the current operation

**In one sentence:** every screen and engine should use the same current measurements and quality information.

- **5.1 Current context:** combine well/time, bit/hole MD, TVD, current/next formation, hole section, inclination, operation, mud weight/ECD, WOB/RPM/torque, hookload/SPP, flow, pit volume and gas, with units and sources.
- **5.2 Precedence:** prefer trusted current observations, then deterministic calculations, then clearly labeled estimates. Serious disagreements must be exposed.
- **5.3 Adapters:** define one interface for reading current state and updates, with replay, CSV and manual versions. Real REST/database/WITSML/ETP integrations are future adapters, not existing rig connections.
- **5.4 Playback:** support start, pause, resume, reset, speed, seek, failure injection, state reading and WebSocket updates.
- **5.5 Freshness:** show value, unit, timestamp, source, quality and age limit per channel. Classify fresh, stale, missing and suspect.
- **5.6 Formation:** identify current/next layer, distance to the next top and boundary uncertainty.

**Partially implemented.** Replay/manual context, source disagreements, age checks and failure injection work. Several channels, backend playback controls, real reset/seek/speed/WebSockets, per-channel age settings and next-top details are missing. Starting a new run is not the same as a completed reset feature.

Finish all channels and controls, then test layer transitions, exact reset, stale inputs, conflicts and reconnect behavior. Paused replay time is simulation time; manual values age against actual UTC.

## Phase 6 — Connect the complete mud-loss story

**In one sentence:** show historical concern, fresh corroboration and a traceable engineer-managed alert together.

- **6.1 History:** use layer, severity, event interval, hole/mud conditions, mitigation, outcome and report evidence.
- **6.2 Approach:** activate the historical concern as the bit approaches the projected interval, using configurable rules. Keep the label uncalibrated until calibration is actually done.
- **6.3 Corroboration:** assess return-flow deficit, falling pit volume, ECD/mud trends and data quality only during meaningful operating states.
- **6.4 Warning:** require Elevated history, applicable depth, agreeing live indicators and fresh valid required channels. Live signals alone must not bypass the history requirement.
- **6.5 Lifecycle:** create, acknowledge, snooze, escalate and resolve alerts. Avoid duplicates; notify again only for escalation, materially changed evidence or snooze expiry.
- **6.6 Full explanation:** show risk/state/layer/range/uncertainty, support/clean/unknown records, current signals, reasons, gaps, responses and sources.
- **6.7 Safe wording:** ask engineers to verify, review, prepare or consider; do not issue numeric drilling-control commands.

**Partially implemented.** Isolated API tests show Warning and lifecycle behavior. Complete event context, mud-weight trend, configurable depth-driven presentation and a packaged full frontend demonstration are unfinished. The default field may honestly show no usable evidence.

Finish dependencies and policies, use a disclosed isolated demo dataset, and demonstrate history → approach → fresh signals → Warning → original evidence → acknowledge → resolve. Repeat with bad data and prove escalation is blocked. Do not secretly approve reports to manufacture a Warning.

## Phase 7 — Add other risks without overstating maturity

**In one sentence:** reuse the evidence system for additional problems, while showing their limitations.

- **7.1 Stuck pipe:** combine history/formation/path/operation with torque, hookload, pressure and stationary duration. Present partial decision support, not a complete predictor.
- **7.2 Kick/overpressure:** combine historical pressure/mud context with pit gain, excess returns and gas rise, gated by operation. Do not claim a black-box kick classifier.
- **7.3 Torque dysfunction:** show torque residuals and trends alongside drilling progress, bit weight and rotation. Optional MSE describes drilling energy; it is not a standalone stuck-pipe predictor.
- **7.4 Cementing:** present past cement jobs, casing intervals, problems, remedies and outcomes for planning. A fabricated real-time cementing model is unnecessary.

**Not started as complete modules.** Historical scaffolding exists. Finish Phases 1/3/5/6 dependencies, implement risk-specific indicators, test missing/bad data and show maturity labels. Completion means all modules use the common evidence system without unsupported accuracy claims; mud loss remains the most polished slice.

## Phase 8 — Make the tools one coherent workflow

**In one sentence:** let an engineer find a concern, understand it and reach its source quickly.

- **8.1 Brief:** make it the default page with depth, layers, distance ahead, upcoming concerns, evidence counts, freshness, lessons and alerts.
- **8.2 Depth strip:** draw formations, uncertainty, casing, historical projections, bit position and risk windows together.
- **8.3 Map:** show radius, wells, surface/underground distances and relevance, including the ranking-change example.
- **8.4 Comparison:** align rock layers and show events, clean crossings, mud/casing context and uncertainty.
- **8.5 Evidence explorer:** follow alert → evidence → comparison → event → exact text → original page, distinguishing copied facts, calculations and interpretations.
- **8.6 Documents:** display original pages, highlighted passages, extracted values, confidence and review status.
- **8.7 Reviews:** accept/correct/quarantine, resolve names/units/depths and prioritize items affecting the current look-ahead.
- **8.8 Rig view:** keep current/next layer, important alert, summary, key signals, acknowledgement and Why/source access.
- **8.9 Validation:** show measured replay/baseline results, alerts, hits/misses, lead distance and coverage.

**Partially implemented ahead of sequence.** Several connected screens exist; the complete strip, comparisons, review priority, default Brief and real validation results do not. Depend on finished engines and actual evaluation results. Finish integration and test whether a user can identify the concern and its reason in roughly 20 seconds.

## Phase 9 — Answer questions using evidence, not improvisation

**In one sentence:** give a useful natural-language answer while leaving calculations to tested code.

- **9.1 Planner:** translate the question into an intent and requested wells/formations/events.
- **9.2 Tools:** allow controlled well, formation, event, offset, alignment, evidence, mitigation and alert lookups.
- **9.3 Retrieval:** identify structured records first, then fetch their report passages.
- **9.4 Answer format:** separate facts, computed patterns, interpretation, gaps and sources.
- **9.5 Numbers:** accept only numbers returned by tools or present in cited evidence, including logged conversions.
- **9.6 Refusal:** say what is missing instead of inventing an answer. Uploaded document text cannot grant tool permissions.

**Not started.** The current Ask NWIS page is a preview. Finish stable records/tools, choose an explicitly configured model/provider if needed, implement source/number validation and test empty/contradictory evidence and malicious document instructions. Completion requires real cited answers and safe refusals—not a convincing sample paragraph.

## Phase 10 — Prove the claims and package the demonstration

**In one sentence:** test the whole product fairly and make its results repeatable.

- **10.1 Engineering tests:** check units, datums, aliases, paths, distances, projections, uncertainty, coverage, blockers, freshness, alerts and source reconstruction.
- **10.2 Gold set:** manually label 30–50 report pages and measure event/depth/formation/response extraction, grounding and review needs.
- **10.3 Blind replay:** hide the active well's future, use only offset history, record alerts, then reveal the truth and score them.
- **10.4 Baselines:** compare against surface-nearest, equal same-formation weights, fixed similarity weights and keyword retrieval under the same conditions.
- **10.5 Metrics:** measure precision, severe-event recall, warning distance, alerts per 1,000 m, missed events, interval overlap, evidence sufficiency and source coverage.
- **10.6 Failure demo:** show Elevated history with stale flow-out and refused escalation; or degraded geology with wider uncertainty and weaker concern.
- **10.7 Safety/security:** check untrusted documents, limited tool access, no rig control, configured private storage, action history and recorded versions.
- **10.8 Packaging:** provide one-command start, repeatable seed/reset, demo mode, offline dependencies, backup video, truthful claim list, architecture diagram and a five-minute script.

Precision asks “how many alerts were justified?” Recall asks “how many real events did we catch?” Lead distance asks “how far before the event did we warn?” They must be measured, not filled with illustrative numbers.

**Partially implemented early through tests and safety guards.** Gold-set scoring, blind evaluation, baseline metrics and final packaging remain missing. Complete earlier phases, build the evaluation harness, run the exact 15 acceptance tests from the original design document and publish actual results. Do not invent the unspecified test list or claim field accuracy from synthetic results.

## What should happen next

Close foundation/data/extraction gaps first, finish geometry and historical policies, protect Phase 4 with regressions, finish replay and the complete mud-loss demonstration, then proceed to secondary risks, integrated workflows, grounded Q&A and final evaluation. Accessibility and test infrastructure can improve throughout.

A phase is finished when its required features and acceptance evidence are recorded. A phase number in the sidebar, screenshot or total passing-test count is not enough.

# Section 3 — The current website, page by page

## A quick map

These links work while the local frontend and backend are running on this computer. They are not publicly hosted links.

| Page | Why it exists | Current functionality |
| --- | --- | --- |
| [Overview](http://127.0.0.1:5173/#overview) | Introduce the system and evidence rules | Explanatory content and backend field overview |
| [Next interval brief](http://127.0.0.1:5173/#brief) | Combine current context, historical concern and simulated signals | Connected replay/manual workflow; incomplete full Phase 6 scope |
| [Offset wells](http://127.0.0.1:5173/#offsets) | Find useful nearby comparisons | Connected map, distance filtering/ranking and reasons |
| [Formation compare](http://127.0.0.1:5173/#compare) | Place historical events in the active geology | Connected event projection and uncertainty |
| [Evidence explorer](http://127.0.0.1:5173/#evidence) | Explain the historical state | Connected planning evaluation, groups, reasons and sources |
| [Historical documents](http://127.0.0.1:5173/#documents) | Read the original evidence | Connected upload/extraction, page view, highlights and coverage |
| [Review queue](http://127.0.0.1:5173/#review) | Correct uncertain records before trusting them | Connected accept/correct/quarantine and audit |
| [Ask NWIS](http://127.0.0.1:5173/#ask) | Intended question-answer shortcut | Preview only; no grounded Q&A engine |
| [Validation](http://127.0.0.1:5173/#validation) | Intended proof of quality | Illustrative scorecards/baselines and mock controls |
| [Rig view](http://127.0.0.1:5173/#rig) | Read the active simulation with less setup | Connected shared session, evidence, channels and alert actions |
| [Settings](http://127.0.0.1:5173/#settings) | Explain/select data mode and policies | Provider switching/status; units/policies mainly informational |

This table describes SYNTHETIC/API mode. MOCK mode uses older browser-local demonstration screens and should never be interpreted as persisted backend results.

## 1. Overview — understand what NWIS is

It explains the purpose, evidence model, operating flow and basic record concepts. The backend overview supplies field information where connected.

**Why it is there:** users need to know what the system claims before trusting a concern or score. It solves the “what am I looking at?” problem.

Read the synthetic/prototype boundary first. An explanation of an intended feature is not proof that the feature is implemented.

## 2. Next interval brief — the main simulation workspace

### Set up a run

- **Adapter:** choose CSV replay or manually entered samples.
- **Monitor from/to MD:** choose the depth range to inspect in the active formation. This is the monitoring scope, not the current bit position.
- **Start new run:** create a separate saved simulation. It does not reset every earlier alert or the whole database.
- **Use another label-free CSV:** upload time/depth/operation and supported measurements. Validate CSV checks expected columns, numeric bounds and increasing elapsed time. It rejects extra event-label columns.
- **Use generated fixture:** return to the built-in telemetry for the next run.

These controls solve the problem of reproducing a measurement sequence without needing a rig connection. The current input range and formation are prototype-specific, not a general unlimited field configuration.

### Current well context

The grid shows well ID, bit MD, TVD, current/next formation and operation. The source, clock and timestamp indicate where the values came from and which time is being used.

TVD can be computed from surveys. Missing observed hole depth remains missing: the bit's position is not substituted for the deepest drilled hole, particularly when the bit is being moved upward.

**Why it is there:** the engine and engineer must agree on the current location and operation. Otherwise a concern could be displayed for the wrong interval or activity.

### Playback and manual controls

- **Play/Pause:** advance replay automatically or stop it. The frontend advances a recorded frame per second; recorded elapsed time controls the simulation clock.
- **Advance one/10 frames:** inspect the sequence in steps. The backend checks intermediate frames rather than skipping possible transitions.
- **Frame count:** shows progress through the recording.
- **Refresh context and evidence:** request a new assessment at the current state; it is not a new sensor reading.
- **Manual samples:** submit supported values with UTC timestamps. Repeated unchanged sample timestamps must not count as a new sustained trend. Manual values can become stale while you wait.

There is no complete speed selector, seek bar, same-run reset or WebSocket stream yet. A CSV recording may contain repeated values; its timestamps still matter.

### Mud-loss look-ahead

This area combines the historical state with the current simulated assessment. It shows the monitoring range, separate projected event windows, evidence summary, flow deficit, pit-volume drop and ECD.

- A **flow deficit** means less fluid is returning than entering.
- A **pit drop** means tank volume fell over the eligible trend window.
- **ECD** supplies circulating-pressure context.

These can have explanations other than mud loss. The prototype is not a calibrated physical diagnosis. That is why they cannot automatically override weak history or bad data.

### Warning gates

PASS/BLOCKED rows show whether history is Elevated, the bit is near the event, required channels are fresh, operation is drilling, context agrees, flow deficit is sustained, pit volume is falling and timestamps agree sufficiently.

**Why it is there:** a user can see why Warning is withheld, rather than mistaking a missing warning for a safe interval. Current thresholds are explicitly demonstration values, not recommended operating limits.

### Evidence behind this simulation snapshot

Expand this to see the exact supporting/clean/unknown/excluded records used for this assessment, their weights and why/why-not details, quotations and report links. The JSON link opens the stored machine-readable result.

The separate **planning evidence explorer** can evaluate a different interval or operation. Its result is not automatically the exact evidence behind the active simulation alert. Use the simulation snapshot disclosure for that exact decision.

### Alerts and past responses

If an alert exists, the page shows lifecycle, current or resolved evidence, peak state and local notification count. An operator name is required for actions.

- **Acknowledge:** record that someone reviewed it. It does not remove the signal or declare safety.
- **Snooze 60 seconds:** temporarily suppress ordinary re-notification using the context clock. A new peak escalation can override it. A paused replay also pauses its clock.
- **Resolve:** close the interval alert for this run. It stays closed; start a new run to revisit it. Resolution does not prove a physical problem was repaired.
- **Audit trail:** see actions and actors. Notifications here are recorded events, not email/SMS messages.
- **Historical response:** show what an older well did and its recorded outcome. This is past experience, not a command to copy a treatment or numeric setting.

### Channel freshness and simulated failures

The table shows each channel's value, unit, source, quality, age and timestamp. The current common freshness limit is 30 seconds.

Choose a required channel and inject STALE, MISSING or SUSPECT; choose FRESH to clear the injected failure. This changes simulated acquisition quality, not a rig sensor. It demonstrates that bad data blocks escalation. The computed/fallback disclosure explains where estimates came from.

**What this page solves overall:** connecting history, location, current evidence and engineer review in one place, while making limitations visible.

## 3. Offset wells — proximity is not relevance

Use radius and formation filters to inspect the generated field. The map represents surface positions, not a complete 3D underground view. The table reports surface distance and calculated target-layer separation separately. Selecting a well shows mean/minimum sampled separation and geometry details, with analog reasons where available.

Positive reasons, penalties, unknowns and blockers explain whether a candidate deserves further attention. Geometric closeness alone does not prove a particular event transfers.

**Why it is there:** two nearby surface wells may bend apart underground. A more distant surface well can be closer at the formation of interest. This page prevents choosing history using surface distance alone.

**Limit:** structural labels and coordinates are synthetic; absent/missing geology must remain explicit. The map is not a surveyed real-field GIS or collision-avoidance tool.

## 4. Formation compare — where would an older event be here?

Select a source document, its extracted event and a target well, then click **Project event**. The result gives a projected MD range, method, confidence and algorithm version—or a reason projection is blocked.

The source/target tracks show their layer boundaries, original event and projected interval on a common depth scale. The uncertainty section explains widened fallbacks and missing-layer examples.

**Why it is there:** “losses happened at 2,500 m” in one well does not imply the same rock is at 2,500 m in another. Relative layer position is more meaningful.

**Limit:** this is currently an event projection explorer, not the complete multiwell comparison of events, clean intervals, mud/casing and uncertainty required by Phase 8. A wide interval means uncertainty, not precise forecasting.

## 5. Evidence explorer — why is the historical state what it is?

Choose risk, from/to MD, radius and operation, then **Evaluate interval**. The page evaluates historical records, not the live replay stream.

Counts and filters separate SUPPORT, COUNTER, UNKNOWN and EXCLUDED. Selecting a well opens analog reasons, event transfer decisions, projected ranges, weights, source quotations and original-report links. Clean evidence shows its verified coverage and explicit no-event statement.

The policy/provenance section explains one contribution per well and exposes the snapshot/version. Internal statistics appear behind a disclosure so they are not confused with field incident probability.

**Why it is there:** a simple risk label can hide missing data or poor comparisons. This page lets an engineer challenge the reason rather than blindly accept the label.

**Limits:** secondary-risk choices expose historical scaffolding, not complete live predictors. This page cannot generate a live Warning on its own. UNKNOWN and counter-only results are not declarations of safety.

## 6. Historical documents — see where the numbers came from

### Library and upload

Select the associated well, choose a PDF/TXT/Markdown report, set its synthetic designation correctly and click **Upload and extract**. In this local prototype, the original report is stored by the backend and extraction/review records are added.

The report table shows native text or OCR, extraction confidence and review state. Choose a report to inspect it. Confidence concerns reading/extraction quality, not the likelihood of a drilling incident; a native-text reading value is not proof that the entire parser understood the report perfectly.

### Original page and events

Open the original report, select a page, and inspect highlighted event passages on PDF pages. Extracted events show depth/layer, source quote, symptom, mitigation/outcome, original units and review status.

“No positive event extracted” means the parser found no usable positive event. It does not prove that nothing happened.

### Coverage ledger

This lists known report depth intervals, verification state and reviewer. Probable coverage needs review; unknown coverage cannot become clean evidence just because there is no event row. The current ledger can include other retained records associated with the same well; read the document/source identifiers carefully.

**Why it is there:** users can check the original material instead of trusting an invisible extraction process. It also preserves evidence for correcting an error.

**Limit:** broader arbitrary tables/narratives and private-data handling are unfinished. Do not assume a prototype synthetic checkbox is a complete privacy/security system or that every uploaded report will parse correctly.

## 7. Review queue — humans resolve uncertain extraction

The queue contains event and coverage items with reasons. Select an item, compare its source, enter the reviewer, and choose an action.

- **Accept:** confirm the current extraction or stated coverage after checking it.
- **Save correction:** for event items, correct supported MD/formation fields. Original evidence is retained and the reviewer is recorded.
- **Quarantine:** exclude an unreliable item from usable risk evidence.

These are real saved data changes in connected mode, not just visual toggles. Accepting coverage can change whether clean evidence is usable. Corrections/quarantine can change later assessments; earlier snapshots preserve their recorded decisions.

**Why it is there:** OCR and rules are fallible. A review step prevents uncertain records silently influencing alerts.

**Limit:** full alias resolution, general unit/date correction and prioritization by current look-ahead impact are unfinished. Do not accept reviews solely to get a stronger demonstration state.

## 8. Ask NWIS — currently an illustration

The textarea and **Run grounded query** button demonstrate the intended question-and-answer layout: facts, computed pattern, interpretation, gaps and sources.

**Current truth:** the screen returns a canned example, not a real answer computed from your question or current database. The word “grounded” in the button is intended behavior, not proof of an implemented engine. Example names/numbers/citations should not be interpreted as live findings.

**Why it is there:** eventually users should ask ordinary questions instead of manually navigating every filter. Phase 9 must build the actual planner, tools, numeric checks and refusal behavior first.

## 9. Validation — planned evidence of quality, not current measured performance

The scorecard, baseline table and held-out timeline illustrate how evaluation will look. The stale-channel button on this preview changes mock state; use the connected Brief for real backend simulated failure injection.

**Current truth:** displayed precision, recall and lead values are illustrative—not results from a completed held-out run. This preview must not be used as a project accuracy claim.

**Why it is there:** developers and reviewers need measured evidence that the system is better than simple alternatives and fails safely. Phase 10 must produce those measurements and replace the placeholders.

## 10. Rig view — read the same run with less setup

Rig view restores the saved session created in Brief. It shows current context, replay progress, mud-loss assessment, gate results, evidence details, alerts/actions and channel quality.

Run creation, CSV selection, manual entry and failure injection are mainly in Brief; Rig is intended for reading and acting on the same run. The saved session is shared in the same browser, not a proven organization-wide real-time coordination service.

**Why it is there:** the person watching current operations should not have to perform document setup to read the concern and its reason.

**Limits:** it is still a simulation and denser than the final simplified rig workflow. Opening the page does not connect to equipment. If there is no active session, start one in Brief.

## 11. Settings — know what mode you are using

- **MOCK:** older browser-local illustrative data and behavior. It does not represent backend evidence or saved reviews.
- **SYNTHETIC:** the connected generated field, extracted reports and simulated telemetry; the default.
- **API:** the configured backend, including supported uploaded reports. This is not automatically a different server, real rig feed or real field dataset.

Backend status shows counts/connectivity. Build/schema labels identify versions; “phase 6” identifies the implementation boundary, not proof every phase is finished.

The units table and policy rows explain conventions: unknown coverage stays unknown, stale data cannot strengthen warnings, and rig write-back is absent. They are primarily informational. The current screen does not provide editable engineering thresholds, a full unit-conversion settings engine or a rig connection configuration just because those concepts are listed.

**Why it is there:** users should know which source they are viewing and should not confuse a mock with a connected assessment.

# Section 4 — Shared website controls and labels

## Navigation and presentation

- **Wordmark/home:** returns to the overview.
- **Left groups:** organize introduction, operations, knowledge and system pages; groups can collapse to reduce visual clutter.
- **Active page marker:** shows where you are.
- **Search / Cmd+K or Ctrl+K:** opens navigation search. It currently searches page titles/descriptions, not all well records or uploaded reports. The empty-state wording may suggest broader search than is implemented.
- **Menu on small screens:** opens the navigation when the sidebar cannot fit.
- **Breadcrumb:** tells you the page's area.
- **On this page:** shortcuts to sections; active highlighting helps reading. Some route/anchor mappings still require complete verification.
- **Previous/Next:** move between pages; they do not advance a replay.
- **Filters:** narrow a view or submit an evaluation, depending on the labeled form. They are not drilling commands.
- **Disclosure sections:** hide technical detail until needed; expanding them does not automatically change evidence.
- **Code/JSON and Copy:** show/copy structured examples or recorded outputs. They are not executed by the page. Language labels exist; full interactive language tabs remain unfinished.
- **Loading/error/empty messages:** distinguish a pending result, failed request and lack of data. An unavailable assessment should never be interpreted as a safe result.
- **Black/white styling:** favors reading and comparison over decoration. Monospace IDs/numbers and thin table rules help scan precise data.

## Evidence state is different from alert lifecycle

| Evidence state | Meaning |
| --- | --- |
| NO_EVIDENCE | No usable historical population for this evaluation; not “no risk.” |
| INSUFFICIENT_EVIDENCE | The available evidence cannot justify a supported historical concern; not a safe label. |
| LESSON | Some relevant historical experience exists, but evidence is limited. |
| ELEVATED | Historical evidence meets the prototype's strength rules. |
| WARNING | Elevated history and all relevant fresh simulated corroboration gates pass. |

The lifecycle answers a different question: was the alert created, acknowledged, snoozed, escalated or resolved? An acknowledged alert can still have Warning evidence. A recorded peak can remain Warning while the current evidence weakens. A resolved alert shows its resolution record, not proof that a physical hazard disappeared.

## Quality, review, coverage and origin are different things

- **FRESH / STALE / MISSING / SUSPECT:** whether a current channel is recent and plausible enough to use.
- **VERIFIED / AUTO_ACCEPTED / NEEDS_REVIEW / QUARANTINED:** whether an extraction has been checked or needs attention. Auto-accepted does not mean human-verified.
- **VERIFIED / PROBABLE / UNKNOWN coverage:** whether the report's described range is confirmed. Coverage alone does not establish clean crossing without the other evidence checks.
- **FACT / COMPUTED / INFERRED:** copied source information / a calculation / a policy interpretation. A copied report fact is still subject to source quality; “FACT” does not certify field truth.
- **Support / penalties / unknowns / blockers in explanations:** positive comparisons, reasons to reduce confidence, missing factors, and reasons not to transfer. Do not confuse “supporting reasons” with a SUPPORT event count.

These distinctions solve a central problem: a single reassuring label can hide whether the underlying data is old, unreviewed, missing or only an estimate.

# Section 5 — Practical reading order and common questions

## To inspect historical experience

1. Start with Overview to understand the boundaries.
2. Use Offset wells to choose a layer/radius and inspect geometry.
3. Use Formation compare to understand event projection.
4. Evaluate an interval in Evidence explorer.
5. Open original reports in Documents.
6. Review only those records you can genuinely verify in Review queue.

## To inspect the simulation

1. In Settings, use SYNTHETIC/API rather than the old mock workflow.
2. In Brief, choose a replay/manual adapter and monitoring interval; start a run.
3. Advance the recording or submit timestamped samples.
4. Read both the historical state and Warning gates.
5. Inspect exact snapshot/source evidence before taking a review action.
6. Use Rig view for the same saved session.
7. Try an explicit simulated stale channel in Brief to inspect safe suppression.

These steps do not guarantee Warning: valid historical evidence must exist first.

## Why do I see NO_EVIDENCE or no alert?

The relevant history may be missing, unreviewed, outside the chosen interval, incompatible or blocked by geology/context. The system should display that limitation rather than invent a concern. Fresh flow/pit signals alone cannot create a historical mud-loss Warning.

## Why is a Warning gate blocked even though the numbers look concerning?

A channel may be stale/missing/suspect; history may not be Elevated; the bit may be outside the applicable window; the operation may not be drilling; the trend may be too short; timestamps may disagree; or sources may conflict. Read the individual gate instead of assuming a software fault or a safe well.

## Does “Resolve” fix anything on the rig?

No. It closes a prototype alert record. There is no equipment control path. Actual decisions remain with qualified personnel and approved procedures.

## Is the project finished because all the pages exist?

No. Some pages are connected, some are previews, and several connected engines are partial. Use the detailed roadmap for acceptance evidence and remaining work.

## Can I trust the percentages in Validation?

Not as performance evidence. Those are illustrative. Internal evidence statistics elsewhere are also not field event probabilities. Actual quality requires the measured Phase 10 evaluation.

## What has this guide changed?

Only documentation. It does not fill the implementation gaps, change review decisions or make unverified features verified.

## Related documents

- [Full requirements, implementation audit and completion roadmap](PROJECT_PHASE_PLAN_STATUS_ROADMAP.md)
- [Frontend design brief](PHASE_0_5_DESIGN.md)
- [Technical implementation notes: Phases 1–2](PHASE_1_2.md)
- [Technical implementation notes: Phases 3–4](PHASE_3_4.md)
- [Technical implementation notes: Phases 5–6](PHASE_5_6.md)

This guide reflects the inspected source and the existing status baseline, not a new full browser acceptance run. Update it when actual functionality changes. Earlier technical notes can contain delivery-time wording superseded by the consolidated roadmap.
