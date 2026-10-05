# Claim ledger

| Claim | Evidence | Status / limit |
|---|---|---|
| Ask responses are grounded in deterministic tools | `backend/app/ask.py`, numeric rejection and source injection tests | Implemented; limited grammar, no external LLM |
| Documents cannot invoke tools | Separate question planner, extraction parsing/OCR, prompt-injection test | Verified locally; not a production penetration test |
| Mud-loss Warning requires fresh corroboration | Same-run stale-flow/recovery API tests and demo trace | Synthetic decision support; not event probability |
| Historical support excludes active future events | Held-out runtime exclusion tests and blind prediction freeze | Authored eight-case benchmark; shared offset history |
| Validation exposes failure | Aggregate reports, false warnings and missed event shown in UI | No field-accuracy claim |
| Extraction reference covers 40 pages | Authored PDF, labels, scorer, rendered-page review UI and normalized bbox contract | Workflow verified; 0/40 pages have independent human sign-off, so certification remains pending |
| Every engineering test result is measured | JUnit XML and SHA-linked report | SQLite; see published counts rather than this document |
| Secondary risk modules are extensible | Common evidence framework and visible maturity | Partial support; no complete stuck/kick classifier, MSE not standalone predictor |
| No rig write-back | Simulation APIs; route checks; no actuation integration | Local prototype only |
| Offline demo can repeat | Prebuilt frontend, wheel cache, isolated seed, reset controls, backup video | Windows x64 Python 3.12; prepared assets required |
| Sources stay in configured storage | Resolved path checks and rejection test | Classification does not enforce user authorization |
| PostgreSQL/PostGIS deployment works from clean start | `storage/validation/docker-postgis.json`; isolated `nwis-verify` Compose build and in-container smoke | Verified locally on Docker Desktop 4.93.0 with fresh named volumes; not production deployment certification |
| PostgreSQL API tolerates bounded local concurrency | `storage/validation/production-assessment.json`; 300 reads at 32 workers and 60 Ask audit writes at 8 workers | Zero failures locally; single-host probe, not stress-to-failure or production capacity certification |
| System is production-ready | Local security/concurrency assessment | **Not claimed**: authn/authz, TLS, secrets, rate limiting, backup/failover, SCA and penetration testing are open |
| Field policy is validated and calibrated | Versioned external manifest and leakage-safe scorer | **Not claimed**: no independent field dataset or domain sign-off has been supplied |
| Dashboard can explain risk quickly | Brief, evidence sentence, Why/source links, simplified rig view, timed participant workflow | 0/5 participants; twenty-second criterion remains unverified |
