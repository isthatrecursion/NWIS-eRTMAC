# Independent validation protocols

## Gold-set review

Open **Validation → Independent gold-set review**. A domain reviewer who did not build the extractor inspects all 40 rendered pages, checks each reference field against the page, draws or enters one normalized bounding box per expected event, and records their controlled reviewer ID and attestation. Hard-negative pages are explicitly accepted with zero boxes. The application writes `storage/gold/human_reviews.json`; it does not alter the authored labels. Sign-off becomes complete only when all 40 pages and every expected event box are present.

Corrections should be described in the review comment and incorporated into a new version of the reference labels by a separate curator. Re-run `python -m app.gold_set score` after that version is frozen. Codex, extraction models, and automated tests cannot supply the human attestation.

## Field validation and calibration

Copy `storage/validation/field-manifest-template.json` into controlled private storage. Pre-register the well population and policy version, replay without future events, freeze predictions, then reveal truth and obtain an independent domain review. Do not place sensitive field data in the demo package.

Run:

```powershell
python -m app.field_validation --manifest <controlled-manifest.json> --output <controlled-report.json>
```

The scorer rejects temporal leakage, measures precision, event recall, severe-event recall and lead distance, and never changes policy automatically. Calibration is eligible for discussion only with at least 10 wells and 30 truth events. A field owner and an independent reviewer must approve any production claim.

## 20-second comprehension study

Recruit at least five users from the intended rig and office roles. On **Validation → 20-second comprehension study**, assign a non-identifying participant code and start the timer. The participant opens the Next Interval Brief and records the active risk, its reason, and whether they opened “Why?” or a source. A passing trial requires the correct risk and reason within 20 seconds. The criterion is verified only if at least 80% of five or more independent participants pass.

Record observations separately: role, confusing labels, first click, and requested changes. Do not coach participants during a timed trial.

## Production security and concurrency

With the PostgreSQL Compose stack running, execute:

```powershell
python -m app.production_assessment --base-url http://127.0.0.1:8000
```

This creates `storage/validation/production-assessment.json`. The local concurrency probe is engineering evidence only. Authentication and authorization, TLS, external secrets, rate limiting, backup/restore, failover, dependency scanning and an independent penetration test remain release gates.
