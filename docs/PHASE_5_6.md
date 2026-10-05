# Phase 5 — current context and adapters

`app/live.py` defines `LiveDataAdapter.get_current_context` and the async `stream_updates` iterator. ReplayAdapter reads bounded, label-free frames; CSVAdapter shares this validated replay implementation. ManualAdapter accepts per-channel timestamped samples. API playback uses explicit persisted cursor advancement; the iterator is a finite in-process adapter interface, not a deployed WebSocket or rig stream.

CSV input is UTF-8, maximum 1 MB and 5,000 frames. `elapsed_s`, `bit_md_m`, and `operation_state` are required. Elapsed time must strictly increase within seven days. Known optional fields have declared canonical units and physical plausibility bounds. Unknown columns, including event labels, are rejected. Blank optional values remain missing. The generated 181-frame fixture contains no runtime event labels; hidden truth is never imported by runtime decision modules.

Each replay run pins its dataset, UTC epoch, cursor, monitoring formation/interval and radius. The simulation clock is epoch plus the frame's elapsed seconds. Pausing also pauses that clock. A fresh replay value is not a fresh rig measurement. Manual samples use actual UTC, and the frontend reevaluates them every five seconds so elapsed-age changes become visible.

The Pydantic-validated CurrentWellContext holds nulls for missing values, observed bit/hole depth, computed TVD/inclination, current/next formation, operation and channel values. An observed fresh field takes precedence over a computed value, which takes precedence over a labeled programme fallback. Bit depth is never silently substituted for hole depth. TVD deviation over 25 m, inclination mismatch over 5 degrees, hole-section mismatch, bit deeper than the observed hole, overlapping formations and survey failures are exposed as conflicts; they block warnings. These tolerances are prototype policy, not survey QC standards.

Every channel carries value, timestamp, unit, source, age and quality: FRESH / STALE / MISSING / SUSPECT. Freshness limit is 30 seconds. Future timestamps over one second and implausible values are suspect. Stale/missing values are not returned as fresh observed context fields. Explicit replay failures are audited and retained in a quality timeline so trend calculations cannot bridge failed acquisition periods. Manual updates reject out-of-order timestamps and preserve timestamps on channels that were not updated.

# Phase 6 — mud-loss corroboration

All downstream evaluation reads the canonical context. Fresh ECD and resolved hole-section context feed historical transferability; absent ECD remains unknown rather than an observed match. The selected monitoring interval is fixed for a run. Supporting event uncertainty envelopes are used individually for proximity, not replaced by an unsafe union over gaps.

Simulated WARNING requires every gate:

1. Historical state is ELEVATED under the existing uncalibrated evidence policy.
2. Fresh bit depth is within an included event envelope or at most 100 m before it.
3. Bit depth, operation, flow in, flow out, pit volume and ECD are all FRESH.
4. Samples are time-coherent within 10 seconds, operation is DRILLING, and context has no conflict.
5. Return deficit is at least max(30 L/min, 5% of flow in), sustained over three distinct observations and at least 20 seconds, without acquisition gaps over 30 seconds.
6. Pit volume drops at least 0.5 m³ over a continuous valid 30–120 second drilling trend.

ECD value/change is exposed as context; ECD alone never triggers a warning. Duplicate measurements, bad channels, operation changes and acquisition gaps cannot establish sustained corroboration. Recovery rebuilds a new continuous valid trend. Live-like signals alone cannot bypass historical evidence. Batch advancement processes intermediate frames so escalation cannot be skipped by a larger step.

These thresholds are **uncalibrated synthetic demonstration policy**. Tank transfers, instrument-specific corrections and real rig operational validation are not modeled. This is not an autonomous operational alarm or equipment controller. The historical population is not automatically reviewed or modified to force an Elevated/Warning display.

# Alert lifecycle and provenance

One persistent alert per simulation run, risk and fixed stratigraphic monitoring interval. Separate replay runs are intentionally separate simulation scopes. Repeated unchanged evaluation never creates duplicates or notification spam. Notifications are recorded in the in-app audit ledger only; no email/SMS integration exists.

- CREATED when supporting historical history first exists.
- ACKNOWLEDGED records an actor without clearing current signals.
- SNOOZED suppresses ordinary notifications until expiry on the context clock.
- ESCALATED occurs for a new peak evidence state, overriding snooze.
- RESOLVED is an explicit actor action or automatic passage beyond the monitored interval using fresh bit depth.

Re-notification is restricted to new peak escalation, meaningful evidence changes (roles, selected events, review/depth/projection/response changes), or snooze expiry. A downgrade caused by stale corroboration updates the current evidence state without increasing notification count; peak state remains historical audit information. Manually resolved intervals are latched for that run, not silently reopened. Start a new run to revisit them.

Alert payloads retain evidence snapshot ID, counts/sentence, individual aligned uncertainty windows, corroboration/missing channels, historical mitigations/outcomes and original source references. Exact historical snapshots are retrievable. The frontend separates current state from recorded peak/resolution state and shows why/why-not factors. Recommendations only ask the engineer to verify, review and prepare approved contingencies. Historical mitigation text is quoted as past experience, not a direct instruction or numeric operating prescription.

Writes are serialized with a process lock for the verified **single-worker prototype**. SQLite persistence survives reopening. Multi-worker/production transactional deduplication and real notification dispatch require additional hardening. PostgreSQL/PostGIS remains configured but unverified on this machine.

# API

| Route | Purpose |
| --- | --- |
| POST /api/replay/datasets | Validate bounded label-free CSV |
| POST /api/replay/sessions | Create REPLAY or MANUAL run with fixed monitoring interval |
| GET /api/replay/sessions/{id} | Read persisted session and fresh-resolved context |
| POST /api/replay/sessions/{id}/advance | Evaluate 1–100 intermediate replay frames |
| POST /api/replay/sessions/{id}/evaluate | Recompute evidence, gates and alert |
| POST /api/replay/sessions/{id}/quality | Inject/clear replay channel quality, with audit |
| POST /api/replay/sessions/{id}/manual | Submit partial timestamped manual observations |
| GET /api/alerts?session_id=... | Run-scoped persisted alerts |
| POST /api/alerts/{id}/transition | Acknowledge, snooze or resolve with actor |
| GET /api/evidence/snapshots/{id} | Retrieve exact evidence behind a decision |

# Interface and verification

Next interval brief and Rig view consume the real backend simulation engine. They share a saved run, playback controls, current context, engineering corroboration, evidence provenance, alert actions and per-channel freshness. Q&A and validation scorecards remain explicitly preview-only. The black/white docs visual system is preserved.

Tests include adapter iteration, CSV bounds/unit plausibility/label rejection, timestamp boundaries, computed/observed conflicts, manual partial updates and ordering, audited Elevated → Warning escalation, repeated-evaluation deduplication, acknowledgement, snooze expiry, escalation through snooze, manual/automatic resolution, intermediate-frame processing, meaningful review changes, reopened SQLite records and exact snapshot retrieval. All 18 combinations of six required channels × stale/missing/suspect block Warning. Additional guards cover live-only signals, proximity, time skew, operation state, duplicate measurements and recovery after acquisition failure. The positive-warning population is an isolated controlled test fixture; real working fixture reviews remain untouched.

No real Oil India data, confirmed eRTMAC protocol or operational calibration is claimed. Work stops after Phase 6.
# Completion update

The earlier implementation notes below are superseded by [Replay and mud-loss completion](REPLAY_MUD_LOSS_COMPLETION.md): backend playback controls and streaming, channel-specific freshness, depth activation, sourced severity/intervals, cross-run deduplication and a complete frontend demo are implemented.
