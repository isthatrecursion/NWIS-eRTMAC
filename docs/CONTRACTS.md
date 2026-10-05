# NWIS Phase 0 contracts

## Provenance

Every conclusion exposed to a user is typed as one of:

- `FACT`: copied from a source record.
- `COMPUTED`: produced by a deterministic, versioned calculation.
- `INFERRED`: a policy, model, or human interpretation.

## Depth and units

- Canonical depth unit: metres.
- `MD` and `TVD` are never interchangeable.
- Original value, unit, datum, and source remain available when normalization occurs.
- API field names include units where ambiguity is possible, for example `bit_md_m`.

## Evidence population

- `SUPPORT`: transferable analog with an event.
- `COUNTER`: transferable analog with verified interval coverage and no event.
- `UNKNOWN`: insufficient coverage; never treated as safe.

## Evidence ladder

- `LESSON`
- `ELEVATED`
- `WARNING`

The historical engine computes LESSON/ELEVATED using transparent, uncalibrated prototype thresholds. NO_EVIDENCE and INSUFFICIENT_EVIDENCE prevent unsupported safe claims. Phase 6 can produce simulated WARNING only after the historical and fresh-channel mud-loss gates all pass. These states are not calibrated Oil India probabilities.

Current context allows null fields for missing observations. Channel values carry `quality_status`, source timestamp, source, unit and age. Replay uses an explicit simulation clock; manual samples use UTC. Serious observed/computed conflicts remain visible and block warnings. Historical snapshot IDs allow exact evidence retrieval.

## Safety invariants

1. Missing information never improves confidence.
2. A stale corroborating channel never increases an alert level.
3. Quarantined extraction cannot drive a warning.
4. No endpoint controls rig equipment.
5. Synthetic and mock data remain visibly labeled.
