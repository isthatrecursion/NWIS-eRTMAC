# NWIS prototype architecture

```mermaid
flowchart TD
  PDFs[Untrusted DDR / WCR pages] --> Extract[Local OCR and deterministic extraction]
  Extract --> Review[Source spans / unit provenance / review queue]
  Review --> Store[(Versioned SQLite or PostgreSQL records)]
  Store --> Geometry[Trajectory / datum / formation projection]
  Geometry --> Transfer[Risk-specific transferability]
  Transfer --> Evidence[Support / counter / unknown evidence snapshots]
  Replay[Simulation frames and per-channel freshness] --> Gates[Deterministic mud-loss corroboration]
  Evidence --> Gates
  Gates --> Alerts[Audited alert lifecycle]
  Question[User question only] --> Plan[Allowlisted deterministic query plan]
  Plan --> Tools[Read-only structured tools]
  Store --> Tools
  Evidence --> Tools
  Alerts --> Tools
  Tools --> Sources[Record-selected source passages]
  Sources --> Verify[Numeric provenance verification]
  Tools --> Verify
  Verify --> Answer[Facts / computed / interpretation / gaps / citations]
  Answer --> UI[Brief / rig / map / compare / evidence / document / Ask]
  Alerts --> UI
  Offline[Offline held-out evaluator] --> Frozen[Freeze predictions before truth reveal]
  Frozen --> Reports[Measured aggregate reports]
  Gold[Authored gold references with human sign-off pending] --> Reports
  Reports --> Validation[Validation dashboard]
```

Documents have no tool execution path. Hidden labels belong to offline evaluation; no runtime route serves the truth files. Live signals are replay/manual simulation channels. There is no rig actuation edge. The offline package serves API and prebuilt React assets from one loopback origin with a separate demo database.
