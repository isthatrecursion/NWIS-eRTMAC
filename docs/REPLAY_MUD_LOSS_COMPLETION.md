# Phase 5–6 completion

The current context exposes mud weight, WOB, RPM, torque, hookload, standpipe pressure and gas, alongside the existing depth, flow, pit and ECD channels. CSV and timestamped manual adapters support all these channels. Density and pressure conversions preserve original values and units; unsupported torque/force units require review rather than being misread as depth.

Each channel carries `freshness_threshold_s`; configure overrides with `NWIS_CHANNEL_FRESHNESS_S` JSON. Unspecified channels default to 30 seconds. Quality injection supports every channel, and optional-channel failures do not invalidate unrelated flow/pit trends. Mud-weight trends explicitly become unknown when their own measurements are invalid.

Current formation uses half-open intervals, with distance to the next formation top and structured uncertainty: candidate formation IDs, boundary overlap, current boundary uncertainty and the next top's bounded interval. Exact transitions are acceptance-tested.

## Backend replay controls

Versioned routes (legacy `/api` aliases remain):

- `POST /api/v1/replay/demo` installs isolated, explicitly synthetic acceptance documents and telemetry and returns a session.
- `POST /api/v1/replay/sessions/{id}/control` accepts `action`: `play`, `pause`, `speed`, `reset`, or `seek`; `speed` is positive up to 100, and `cursor` is a zero-based frame index.
- `WS /api/v1/replay/sessions/{id}/stream` delivers context, assessment and alert updates.
- `GET /api/v1/replay/config` returns channel bounds/units/freshness and the effective historical and mud-loss policies.

The server owns playback, following recorded elapsed time at the chosen speed. It advances without frontend timers or WebSocket subscribers, evaluates every intermediate frame and retains fractional playback time when speed changes. Pausing stops progression. Process restarts pause stored sessions rather than fast-forwarding downtime. Manual frame advancement requires paused playback.

Reset preserves the session ID, dataset and simulation epoch; clears quality injections/history; pauses playback; and returns to frame zero. Seek resets and replays every intermediate frame to rebuild alert transitions. Both explicitly restart the **shared well/formation/interval simulation episode**, pause and deactivate previous sessions on that interval, and preserve the append-only audit ledger. Context and assessment are deterministic; audit timestamps and cumulative notification counts deliberately remain historical.

## Historical mud-loss extraction and policy

Explicit minor/partial/moderate/severe/total losses retain their sourced severity; unsupported severity remains unknown. Event MD ranges retain both endpoints, original units and source offsets. Alignment projects the entire range, including endpoint/formation/datum uncertainty. The reviewer can correct interval endpoints and severity. Reviewed original depth edits remain authoritative during metadata upgrades; conflicts with newly extracted intervals create review tasks.

Extracted event mud weight, ECD, hole size and mud system override stored offset programmes. Transfer results identify `FACT_EXTRACTED_EVENT`, `STORED_PROGRAMME_FALLBACK` or `UNKNOWN` for each mud-context field. The live comparison uses fresh observed active mud weight/ECD, retaining missing telemetry as unknown. Historical lessons expose severity, interval and extracted mud context.

Configure `NWIS_MUD_LOSS_POLICY` and `NWIS_HISTORICAL_POLICY` as JSON; `.env.example` supplies examples. Historical aggregation, inclusion thresholds, look-ahead/approach distances, ECD/mud-weight/hole-size tolerances, flow sample count/duration, acquisition gap, sample skew and pit trend thresholds are configurable, validated and returned with the assessment. Policies remain uncalibrated demonstration assumptions.

Activation uses projected event windows: distant has no active advisory; within the lesson distance (default 300 m) activates Lesson; within approach distance (100 m) permits the available historical Elevated state. Warning additionally requires the existing corroboration gates. Live signals alone cannot warn. ECD and mud-weight changes are displayed independently. Passing the monitored interval resolves the alert.

Deduplication uses well, risk, formation and canonical monitoring bounds across runs. Existing run-scoped active alerts are audited and retired when encountered. Other runs share the canonical alert and cannot rewind its state with an older simulation timestamp. Resolution remains latched until an explicit reset/seek restarts the episode.

## Run the complete frontend demo

Start the backend and frontend using the README commands. Open **Next interval brief**, select **Load full mud-loss demo**, choose **10×** or **20×**, then select **Play replay**.

The isolated `SYN-DEMO-ACTIVE` scenario progresses through Namsang → Tipam → Barail and distant → Lesson → Elevated → Warning → Resolved. It has two sourced supporting events and two verified clean crossings, all seven added operational channels, a flow deficit and a falling pit trend. Only the literal synthetic acceptance fixture reports are verified by its named fixture verifier; regular generated field reports and uploaded documents retain their review gates.

For frame-by-frame inspection (one-based frames):

| Frame | Bit MD | Expected behavior |
| --- | --- | --- |
| 1 | 2050 m | Distant; no activated advisory |
| 3 | 2250 m | Lesson |
| 7 | 2430 m | Elevated; live warning gates blocked |
| 11 | 2480 m | Warning; sustained flow deficit and pit decline |
| 15 | 2530 m | Interval passed; Resolved |
| 16 | 2580 m | Exact transition to Barail |

At Warning, enter an operator name and exercise acknowledge, snooze and resolve; inspect the audit trail. Inject stale flow-out data to block warning; restore fresh data and advance to rebuild valid trend continuity. **Reset same run** and the seek slider allow reproducible playback.

`python -m app.upgrade_mud_events` enriches existing retained mud-loss source records without replacing reviewed observations. A SQLite backup was retained at `backend/nwis.pre-replay-mud-loss-completion.db` before applying the upgrade.

The replay scheduler and alert lock are intended for the documented single-worker prototype. Multi-worker distributed playback and real rig connectivity remain outside phases 0–6. PostgreSQL/PostGIS clean-start verification still requires Docker, unavailable on this host.
