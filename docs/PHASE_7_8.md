# Phase 7–8: secondary support and integrated workflows

Build 0.8.0 adds backend engines and connected frontend views. Mud loss remains the only polished simulated vertical slice. Secondary modules never create automated Warning alerts and publish no accuracy or probability claim.

## Secondary modules

All four use the existing common evidence evaluator: geometry, formation alignment, event-specific transferability, support/counter/unknown/excluded populations, immutable snapshots, reviewed source spans and historical lessons.

- Stuck pipe: partial decision support, operation binding, torque change, hookload deviation, SPP change, observed depth stationarity, formation and inclination context. The baseline is a contiguous same-operation observation window, not a mechanical model. Stationarity is limited to the observed 120-second window and does not prove stationary pipe exposure.
- Kick/influx: conservative pit gain, sustained excess returns, gas rise, fresh mud weight, stored pressure context, and drilling/circulating gates. Combined indicators require fresh, time-coherent channels. No black-box classifier or real-time pressure prediction.
- Torque/dysfunction: observed torque residual, ROP/WOB/RPM trends, optional MSE with explicit inputs and formula. MSE is informational and never triggers a stuck-pipe prediction. Missing ROP/hole size or zero ROP produces Unknown.
- Cementing: sourced historical job/problem/remedial-action/outcome records. Extracted job intervals stay Unknown when absent. Casing intervals inferred from the stored programme are labeled INFERRED separately from extracted event locations. No real-time cementing model.

Indicator thresholds in `backend/app/secondary.py` are versioned, transparent, uncalibrated prototype values. Baselines reject gaps, operation changes, stale/suspect channels and duplicate acquisitions. MSE terminology follows the [SLB glossary](https://glossary.slb.com/en/terms/m/mechanical_specific_energy); its dimensional formula is covered by a numeric test.

## Dashboard and workflow

Next Interval Brief is the default route. It puts well/depth/current and next formation/distance ahead, mud-loss state, evidence sentence and freshness near the top; replay setup collapses after loading a session. Existing warning/acknowledge/snooze/resolve controls remain audited. Load full mud-loss demo supplies reviewed isolated fixture history.

The depth strip shows tops, uncertainty bands, casing points, current bit and inferred event envelopes. Office planning evaluates full formation intervals, so its support/counter counts can differ from the narrow live mud-loss monitoring interval. Planning snapshots show their simulation timestamp, refresh on paused depth changes or every five playing frames, and provide an explicit refresh after reviews. Secondary cards expose maturity and missing indicators.

The map shows the selected active well, radius, offsets, surface and target distances, and relevance decisions. Ranking swaps use actual computed geometry. When the isolated demo has identical trajectories, the original divergent field can be inspected as a separately labeled ranking example without changing the active well.

Formation comparison normalizes each top to 0% and base to 100%, retaining absolute depths, formation uncertainty, source-linked events, mud/casing context and verified coverage. Clean crossings require explicit reviewed risk negation and coverage of the uncertainty envelope; coverage alone is not called clean.

Evidence links preserve the exact snapshot and selected event. Trace to source page exposes Alert → evidence → transfer → historical event → source span → original document page, with FACT/COMPUTED/INFERRED labels. The document view highlights the source and shows numerical fields, original units, extraction confidence and review status. Review supports accept/correct/quarantine, aliases and unit/depth corrections, prioritizing potential impact on the active formation and nearby wells. This priority is potential impact, not an asserted event overlap.

Rig view contains current/next formation, one mud-loss advisory, evidence sentence, key channel freshness, operator acknowledgement and Why/source controls.

## Offline validation

From `backend`, run:

```powershell
.venv\Scripts\python.exe -m app.validate_replay
```

The offline evaluator alone reads held-out manifests. It publishes typed aggregate reports; runtime validation endpoints never read hidden truth. The dashboard compares radius-only, raw-depth, formation-evidence and the mud-loss slice, showing alert counts, hits/misses, false alerts, lead distance and usable evidence coverage. Policy snapshots, generator version/seed, input hash and repository review-state hash support reproduction.

The current 181-frame held-out run contains one positive mud-loss case and no independent negatives. All four methods missed it because the current repository has zero usable reviewed historical wells for that case. This is displayed as an evidence gap; sources are not auto-accepted to improve the score. Specificity and accuracy are unavailable. The separate complete mud-loss demo is an acceptance fixture, not a held-out accuracy experiment. Secondary modules are not scored as complete predictors.

## Verification and boundaries

Backend tests cover secondary gating, dimensions, stale/duplicate samples, cementing source retrieval, versioned endpoints, immutable chain membership, actual ranking reversal, explicit clean crossings, reviewed unit correction and published offline aggregation. Frontend TypeScript and production build checks pass; browser checks cover brief, evidence/source navigation, validation and rig/office views.

The layout is designed for rapid risk identification, but the approximately 20-second criterion has not been measured in a human usability study. Local verification uses SQLite and single-worker replay; clean Docker/PostgreSQL/PostGIS verification remains a separate environment limitation. Real rig connectivity, field calibration and grounded Q&A remain deferred.
