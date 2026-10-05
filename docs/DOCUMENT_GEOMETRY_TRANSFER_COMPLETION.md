# Phase 1B–3 completion pass

This pass addresses the document intelligence, geometry/alignment and analog/transferability gaps supplied after the Phase 0/1A completion.

## Document intelligence

- Uploads accept explicit `PUBLIC` or `PRIVATE` classification, defaulting to private. Source confidentiality markings prevent public classification. Classification is document metadata; the existing local prototype does not provide an authenticated multi-user access-control system.
- Report type is declared by the uploader or detected from document content. Filenames no longer decide it. Unknown or conflicting types enter document review. The upload UI exposes classification and report type, and the library displays both.
- Each page stores detected headers, sections, tables, rows and MD/TVD depth columns with original page/line/cell references and bounding boxes where available. Detection supports pipe/tabular text and native PDF columns aligned by bounding boxes. These are deterministic layout heuristics, not a universal visual document model.
- Dates, explicit date coverage, well identity, mud weight, ECD, hole size, pressure, overbalance, stationary exposure, permeability, gas, influx volume, loss rate, torque and LCM volume are extracted with quantity/unit provenance. Mixed-number hole sizes are supported. Conflicting or out-of-range values require review and cannot silently enter event context.
- Well names are compared against the associated well ID/name/declared aliases. Mismatches create document review, prevent historical evidence use and require explicit identity confirmation. Missing names are recorded as unknown.
- Event chains support labeled text and bounded narrative action/cause/outcome patterns. Drilling abbreviations include DRLG, RIH, POOH, CIRC, RMG, CMTG, WOC, LC and stick-slip notation. Ambiguous SP requires review. Table event depths use the declared depth column rather than an unrelated number.
- The basin-scoped gazetteer contains 19 named units, aliases, basin identifiers, source citations, version and match confidence. Exact registered matches are accepted; fuzzy candidates retain a null formation ID until corrected through review. It covers the named Assam-Arakan units in the curated sources, not every formation worldwide.
- Coverage records preserve per-page date bounds, source evidence and independent date verification status. New date metadata on retained sources requires a fresh coverage review, even if depth coverage was previously verified. Ambiguous numerical dates are flagged for review.
- `python -m app.upgrade_documents` enriches retained source pages and creates an audit entry while preserving human-reviewed event depths and source records. Bootstrap invokes this upgrade too.

Gazetteer sources:

- [DGH / National Data Repository, Assam-Arakan Basin](https://www.ndrdgh.gov.in/NDR/?page_id=617).
- [Oil India, expected formation tops, section 4.3 / Table 4](https://www.oil-india.com/files/oldtender/global/NIT_CDG4898P21.pdf), supporting the Namsang entry.

## Geometry/alignment

- Survey points expose dogleg angle and dogleg severity in degrees per 30 m; the survey endpoint includes maximum severity and station count.
- Alignment retains the event, source/target formation data and supplied survey paths for every method, including blocked calculations and all fallbacks.
- Configured source/target/event datum uncertainty expands the projected interval conservatively. Event-depth uncertainty is scaled by the source/target thickness ratio. TVD fallback converts vertical datum margin to an approximate MD margin using target inclination, with a near-horizontal bound.
- Downhole separation exposes an uncertainty interval for configured datum error. Analog ranking uses its upper distance bound so added uncertainty cannot improve relevance.
- Unknown datums and mismatched datums block projection. Unspecified uncertainty bounds are reported as unspecified; values are not invented and no datum transformation is implied. The margins are conservative prototype envelopes, not calibrated confidence intervals.

## Analog/transferability

- Candidate assessments compare pore pressure, technology era, drilling technology and formation-interval inclination.
- Stuck-pipe comparisons use source event depth and projected target depth for inclination, plus stated/derived overbalance, stationary exposure and permeability. Terminal survey inclination is no longer used as an event-depth substitute.
- Kick comparisons include pore pressure, mud weight, overbalance, gas percentage and influx volume. Hydrostatic overbalance calculations retain mud weight, TVD, pore pressure, gravity and method inputs. Opposite overbalance regimes block transfer.
- Per-comparison outputs retain both values, differences, tolerance, state, weight and policy version. Missing inputs remain unknown and do not improve the comparison factor. Generic and event-specific comparisons remain visible separately.
- Event-local quantities override source programme context where explicitly extracted. No extraction is copied into the active well programme as a new fact.
- These comparisons are uncalibrated similarity policies. Implemented comparisons can still report unknown on real records lacking the necessary observations. Missing pressure/exposure/gas data is not inferred from hidden synthetic truth. Cement-specific programme comparison and secondary live risk engines remain outside this supplied scope.

## Verification

Local checks include the existing suite plus regression cases for metadata/type classification, date verification, well mismatches, narrative and native-table numerical grounding, fuzzy/basin matching, conflicting quantities, all geometry fallback inputs, uncertainty widening, dogleg severity, event-depth inclination, risk-specific comparisons, missing-data penalties and reviewed-source upgrade repeatability.

On 4 October 2026, all 90 backend tests passed. Ruff correctness lint, generated-contract drift checks, frontend TypeScript checks and the production build passed. A smoke check against the refreshed SQLite database verified document classification/layout metadata, the 19-entry gazetteer, the 35-station survey diagnostic, stuck-pipe historical evaluation and the review API. Bootstrap completed repeatedly with 24 wells and 12 current generated reports, including two scanned reports. The library retains 18 active sources because reviewed historical versions are preserved alongside new fixtures.

The pre-update SQLite backup is `backend/nwis.pre-document-geometry-completion.db`. The metadata upgrade initially enriched 36 retained sources, with subsequent enrichment tracked by intelligence version and audit records. Source spans, reviewed event depths, declared classifications and reviewed date interpretations remain preserved.

PostgreSQL/PostGIS trajectory persistence remains locally unverified: Docker is unavailable on this machine. The clean-stack CI smoke check added in the previous completion pass remains the verification path on a Docker-capable runner.
