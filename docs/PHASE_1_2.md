# Phases 1 and 2

## Phase 1A: synthetic field

The offline generator produces 24 wells using seed 121. It stores surface coordinates in a declared local ENU metric grid, 100 m survey stations, formation tops/bases with uncertainty, mud programmes, three synthetic structural domains, and missing-coverage cases.

The active well is held out. Its future event is written only to `storage/evaluation/truth.json`. Application APIs import neither the generator nor the truth manifest. Generated historical documents exclude the held-out well.

The generator also emits a label-free `storage/runtime/replay.csv` sensor fixture for the future replay adapter, and stores synthetic casing setting depths beside the mud programmes.

The loss generator uses latent zone weakness, ECD interaction, spatial region and stochastic noise. Geometry and alignment engines do not use that equation. This validates software behavior, not field prediction accuracy.

Twelve reports include ten native PDFs and two image-only scanned equivalents. All source pages carry the synthetic watermark. PDF output is byte-deterministic. Repeat bootstrap preserves reviews and excludes superseded fixture versions.

## Phase 1B: ingestion

Uploads support PDFs and UTF-8 TXT/Markdown, up to 20 MB and 100 pages. PyMuPDF extracts native text and bounding boxes. Pages without usable native text render locally and pass through RapidOCR/ONNX.

A Pydantic-constrained deterministic parser identifies positive operational events, event-local MD depths, formation aliases, operation state, symptoms, stated causes, mitigations and outcomes. Each event chain is bounded by the next depth-specific event so unrelated mitigations do not cross between events. It preserves original numeric values and units; feet use the logged conversion factor 0.3048. It tolerates missing OCR spaces without changing source text. TVD values never silently become MD.

Each event has source page, text span, bounding box where available, extractor version and confidence. OCR events, unknown aliases, ambiguous depths and impossible values require review or quarantine. Source fields remain traceable after human correction. Extraction has no tool access and never executes document text.

Coverage starts as PROBABLE only when an explicit valid MD interval exists; otherwise UNKNOWN. Review can verify coverage. Missing data never counts as a clean crossing.

The parser handles explicit labels and common event phrases. Broad narrative/table extraction across arbitrary historical formats is not yet calibrated, and ambiguous records require human review. No hosted LLM or Oil India dataset is used.

## Phase 2: geometry

Survey input is validated for increasing MD, valid finite angles and a surface station at zero. Minimum curvature yields East/North/TVD coordinates. Linear interpolation is bounded to the surveyed interval. SQLite persists computed paths as records; PostgreSQL additionally stores `LineStringZ` in PostGIS via the spatial migration. Synthetic coordinates use SRID 0 and retain a named CRS rather than falsely assigning a geographic EPSG code.

Surface radius selects candidates. Target separation samples 21 corresponding fractions through the selected formation and reports mean and minimum 3D separation. It is a formation-correspondence metric, not a global closest-approach or collision calculation.

The seeded ranking swap is visible: SYN-NHK-01 is closest at surface but farther downhole than SYN-NHK-02.

## Phase 2: alignment

An event's relative formation position is projected through the target formation thickness. A conservative corner envelope varies source and target formation tops/bases over their uncertainty.

Fallback order:

1. Complete formation top/base.
2. Top and approximate thickness, with wide low-confidence uncertainty.
3. Approximate TVD matching within survey coverage.
4. Raw MD last resort, explicitly low confidence with a wide interval.

Absent formations, unknown/mismatched event datum, mismatched formation datum, quarantined events and out-of-formation depths block projection. Results include inputs, algorithm version, source span and computation timestamp. This simplified stratigraphic correspondence is not a validated geological correlation model.

## Connected frontend

- Offset wells: generated surface positions, radius and formation filters, calculated target separation.
- Formation compare: source-event selection, target selection, calculated projection and fallback demonstration.
- Documents: upload, OCR/native confidence, original page, highlighted evidence and coverage ledger.
- Review: accept, correct or quarantine an event/coverage record with persisted reviewer and audit history.

Risk, replay and Q&A pages remain explicit workflow previews.

## API

| Route | Purpose |
| --- | --- |
| `GET /api/meta` | Field and document counts, implemented capabilities |
| `GET /api/wells` | Synthetic well population |
| `GET /api/wells/{id}/survey` | Calculated trajectory |
| `GET /api/wells/{id}/formations` | Formation tops/bases |
| `GET /api/wells/{id}/events` | Extracted historical events |
| `GET /api/wells/{id}/coverage` | Coverage ledger |
| `GET /api/wells/{id}/offsets/at-depth` | Surface filter and downhole separation |
| `POST /api/alignment/project-event` | Uncertainty-aware projection |
| `POST /api/documents/ingest` | Multipart upload and local ingestion |
| `GET /api/documents/{id}/events` | Events with exact source spans |
| `GET /api/documents/{id}/source` | Original retained report |
| `GET /api/documents/{id}/pages/{page}/image` | Rendered page |
| `GET /api/review` | Pending event and coverage review |
| `POST /api/review/{id}` | Persist reviewed/corrected/quarantined record |

## Verification

Tests cover known minimum-curvature cases, interpolation bounds, invalid surveys, ranking swap, projection envelopes, pinch-out, datum guards, fallback uncertainty, extraction source grounding, OCR without spaces, feet conversion, negative statements, TVD/MD separation, untrusted text, real scan OCR, review persistence, hidden-truth isolation and byte-deterministic generated PDFs.

The local frontend build and SQLite-backed API have been exercised. Docker/PostGIS is configured but unverified on this machine.
