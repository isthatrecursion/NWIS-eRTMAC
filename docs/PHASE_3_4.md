# Phase 3 — analog selection and transferability

The candidate cascade checks surface radius, formation presence, coordinate reference/datum, target-interval geometry, and trusted structural domain. Both domain labels must be trusted before mismatch becomes a hard gate. Synthetic trusted labels are demonstration assumptions, not geological fault interpretation. Unknown structure reduces relevance. Missing formation bounds use penalized surface-distance relevance, not fabricated target geometry.

Relevance is `1 / (1 + distance_km)`, multiplied by 0.7 for unknown structure and 0.5 when target geometry is unavailable. Transfer weight is relevance × alignment × precondition match × source quality. Moderate formation alignment uses 0.8; low-confidence fallback uses 0.35. Minimum included weight is 0.08. Every decision exposes factors, supporting reasons, penalties, unknowns and hard blockers.

Quarantined/unreviewed events, absent formation, unknown/mismatched datum, missing source provenance, incompatible operation/hole section and strong mud-loss ECD difference block transfer. Auto-accepted native extraction is usable with a source-quality penalty; human-verified extraction avoids that penalty. Missing mud/context fields reduce scores, never become positive matches. Current context comes from stored well programmes and explicit planning inputs; no live sensor assumptions are made.

Mud loss has an absolute ECD-difference penalty and blocks differences over 0.15 sg. Kick does not reuse loss-pressure direction: missing pressure/overbalance modeling is explicit. Stuck pipe carries terminal-inclination similarity plus missing permeability/overbalance/exposure penalties. Cementing carries missing placement/programme penalties. These secondary policies are conservative scaffolding, not complete mechanistic risk modules. Technology era and pressure data are not available in the fixture and are not invented.

# Phase 4 — coverage-aware evidence

Evaluation is scoped to a requested formation, risk, MD interval, radius and planning operation. Source events are projected with Phase 2 uncertainty. Only included events whose projected envelope overlaps the requested interval support it. Each well contributes the maximum applicable event weight once, regardless of duplicate reports. The active and held-out wells and superseded reports are excluded.

A counter record requires human-verified coverage containing the complete reverse-projected source uncertainty envelope, matching datum, compatible context, and an explicit risk-specific no-event statement on the covered page. Incomplete/fallback alignment cannot prove a clean crossing. Any same-risk event record on that well conservatively prevents a clean claim until the contradiction is resolved. Missing, probable or ambiguous coverage stays UNKNOWN. Candidate blockers yield EXCLUDED, distinct from unknown evidence.

The clean-statement parser currently recognizes explicit `No mud loss observed during the covered drilling interval` (and equivalent explicit risk phrases). It is not a general narrative/table absence detector. Reviewer confirmation covers interval coverage; it is not an assertion that arbitrary extraction is exhaustive.

Internal statistics:

- `p_hat = (sum support weights + 1) / (sum usable weights + 2)`.
- `n_eff = sum(weights)^2 / sum(weights^2)`.
- Unknown/excluded records do not enter either statistic.
- Empty usable population: NO_EVIDENCE, null p_hat.
- Counter-only population: INSUFFICIENT_EVIDENCE, never a safe label.
- Supporting history: LESSON.
- ELEVATED: at least two supporting wells, n_eff ≥ 3, p_hat ≥ 0.45.

Thresholds are transparent **uncalibrated prototype policy**. They have not been backtest-calibrated. p_hat is displayed only inside an internal-statistics disclosure, not as field event probability. WARNING is forbidden in this engine. Live corroboration and alert lifecycle are deferred.

Versioned input-derived evaluations and transfer results persist as snapshots with content-derived IDs, timestamps, policy version, event inputs, programmes, formation inputs, source spans and individual decisions. Reviews change the next evaluation; earlier differing snapshots remain available in storage. No hidden truth is imported into runtime decision modules.

# API and interface

- `GET /api/wells/{id}/analogs?formation=TIPAM&radius_km=3`: ranked candidates and why/why-not reasons, including out-of-radius exclusions.
- `POST /api/transferability/event`: active_well_id, event_id, radius_km, operation_state. Returns persisted explainable event decision.
- `GET /api/wells/{id}/lookahead`: formation, risk, md_from_m, md_to_m, radius_km, operation_state. Returns evidence population, state, internal statistics and snapshot provenance.

Evidence and Next interval brief use the real engine in SYNTHETIC/API modes. The interval form is explicit planning input. Role filters, per-well details, event source quotations, original-report links, factors and clean-source evidence are connected. Offset wells exposes candidate reasons separately from event relevance. MOCK mode retains the clearly separated Phase 0.5 preview.

# Verification and limits

Tests exercise candidate radius/formation/structure gates, missing-field penalties, risk-specific unknowns, event review/datum/operation/provenance blockers, reviewed clean intervals, uncertainty coverage boundaries, explicit negation, duplicate suppression, superseded reports, interval filtering, weighted statistics and unknown exclusion. A controlled ingestion → coverage review → evaluation test demonstrates ELEVATED and then LESSON after quarantining supporting history, preserving the previous snapshot. No live WARNING is possible.

SQLite is the verified local persistence path. Existing Docker/PostGIS setup remains unverified on this machine. Only synthetic fixtures have been used. No review decisions or structural assumptions are changed to force an Elevated display in the working dataset.
