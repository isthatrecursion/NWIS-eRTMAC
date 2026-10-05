"""Shared storage contracts. Extensions remain available for versioned engine outputs."""
from pydantic import BaseModel, ConfigDict, Field, model_validator
from datetime import datetime
from typing import Literal
from .enums import CauseType, EventType, ExtractionConfidence, OperationState, ReviewStatus, CoverageStatus, EvidenceState, EvidenceRole, AlertLifecycle
from .units import Measurement
from .contracts import ContextHistory


class RuntimeRecord(BaseModel):
    model_config = ConfigDict(extra="allow", allow_inf_nan=False)
    id: str
    synthetic_flag: bool = False
    measurements: dict[str, Measurement] = Field(default_factory=dict)


class SurveyStation(BaseModel):
    model_config = ConfigDict(extra="allow", allow_inf_nan=False)
    md_m: float = Field(ge=0)
    incl_deg: float = Field(ge=0, le=180)
    azi_deg: float = Field(ge=0, lt=360)


class RuntimeFormation(BaseModel):
    model_config = ConfigDict(extra="allow", allow_inf_nan=False)
    formation_id: str
    name: str
    top_md_m: float = Field(ge=0)
    base_md_m: float | None
    uncertainty_m: float = Field(ge=0)
    datum: str


class MudProgramme(BaseModel):
    model_config = ConfigDict(extra="allow")
    mud_system: str | None = None
    ecd_sg: float | None = None
    hole_section_in: float | None = None
    mud_weight_sg: float | None = Field(default=None, gt=0)
    measurements: dict[str, Measurement] = Field(default_factory=dict)


class CasingSection(BaseModel):
    model_config = ConfigDict(extra="allow")
    size_in: float
    setting_md_m: float
    measurements: dict[str, Measurement] = Field(default_factory=dict)


class OperatingContext(BaseModel):
    model_config = ConfigDict(extra="allow")
    pore_pressure_kpa: float | None = Field(default=None, ge=0)
    overbalance_kpa: float | None = None
    mud_weight_sg: float | None = Field(default=None, gt=0)
    stationary_exposure_h: float | None = Field(default=None, ge=0)
    permeability_md: float | None = Field(default=None, gt=0)
    gas_pct: float | None = Field(default=None, ge=0, le=100)
    influx_volume_m3: float | None = Field(default=None, ge=0)


class RuntimeWell(RuntimeRecord):
    name: str
    field: str
    status: Literal["ACTIVE", "OFFSET"]
    x_m: float
    y_m: float
    crs: str
    datum: str
    survey: list[SurveyStation]
    formations: list[RuntimeFormation]
    mud_program: MudProgramme = Field(default_factory=MudProgramme)
    casing_program: list[CasingSection] = Field(default_factory=list)
    held_out: bool = False
    coverage_expected: bool = False
    structural_domain: str | None = None
    structural_quality: str | None = None
    pressure_context: OperatingContext = Field(default_factory=OperatingContext)
    operating_context: OperatingContext = Field(default_factory=OperatingContext)
    drilled_year: int | None = Field(default=None, ge=1850, le=2200)
    drilling_technology: str | None = None


class GroundedFieldSource(BaseModel):
    model_config = ConfigDict(extra="allow")
    page: int
    text: str
    bbox: list[float] | None = None
    char_start: int | None = None
    char_end: int | None = None


class NumericalField(BaseModel):
    model_config = ConfigDict(extra="allow")
    value: float
    measurement: Measurement
    source: GroundedFieldSource
    requires_review: bool = False


class FormationMatch(BaseModel):
    model_config = ConfigDict(extra="allow")
    raw: str | None
    basin: str
    formation_id: str | None
    gazetteer_version: str
    confidence: float = Field(ge=0, le=1)
    method: str
    requires_review: bool


class RuntimeEvent(RuntimeRecord):
    severity: Literal["UNKNOWN", "MINOR", "PARTIAL", "MODERATE", "SEVERE", "TOTAL"] = "UNKNOWN"
    md_to_m: float | None = Field(default=None, ge=0)
    event_md_interval_m: tuple[float, float] | None = None
    well_id: str
    event_type: EventType
    md_from_m: float | None = Field(default=None, ge=0)
    formation_id: str | None = None
    cause_kind: CauseType = CauseType.UNKNOWN
    operation_state: OperationState = OperationState.UNKNOWN
    review_status: ReviewStatus = ReviewStatus.NEEDS_REVIEW
    extraction_confidence: ExtractionConfidence = ExtractionConfidence.UNKNOWN
    datum: str = "UNKNOWN"
    document_id: str | None = None
    source_span_id: str | None = None
    symptom: str | None = None
    cause_text: str | None = None
    mitigation: str | None = None
    outcome: str | None = None
    original_value: float | None = None
    original_unit: str | None = None
    depth_reference: str = "UNKNOWN"
    confidence: float = Field(default=0, ge=0, le=1)
    review_reasons: list[str] = Field(default_factory=list)
    numerical_fields: dict[str, NumericalField] = Field(default_factory=dict)
    context_values: dict[str, float | str] = Field(default_factory=dict)
    field_evidence: dict[str, GroundedFieldSource] = Field(default_factory=dict)
    formation_match: FormationMatch | None = None
    event_date: str | None = None


class LayoutRegion(BaseModel):
    model_config = ConfigDict(extra="allow")
    kind: str
    line_index: int
    source: GroundedFieldSource


class LayoutSection(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: str
    line_index: int
    source: GroundedFieldSource


class TableRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    cells: list[str]
    source: GroundedFieldSource


class TableColumn(BaseModel):
    model_config = ConfigDict(extra="allow")
    index: int
    header: str
    reference: str
    unit: str


class DetectedTable(BaseModel):
    model_config = ConfigDict(extra="allow")
    headers: list[str]
    depth_columns: list[TableColumn]
    rows: list[TableRow]
    source: GroundedFieldSource


class PageLayout(BaseModel):
    model_config = ConfigDict(extra="allow")
    version: str
    regions: list[LayoutRegion]
    tables: list[DetectedTable]
    method: str
    headers: list[LayoutRegion] = Field(default_factory=list)
    sections: list[LayoutSection] = Field(default_factory=list)


class PageLine(BaseModel):
    model_config = ConfigDict(extra="allow")
    text: str
    bbox: list[float] | None


class DocumentPage(BaseModel):
    model_config = ConfigDict(extra="allow")
    page: int
    text: str
    is_scan: bool
    confidence: float
    lines: list[PageLine]
    layout: PageLayout | None = None


class DateCoverage(BaseModel):
    model_config = ConfigDict(extra="allow")
    date_from: str
    date_to: str
    status: CoverageStatus
    source: GroundedFieldSource


class WellIdentity(BaseModel):
    model_config = ConfigDict(extra="allow")
    raw: str
    matches_associated_well: bool
    source: GroundedFieldSource


class ExtractedDate(BaseModel):
    model_config = ConfigDict(extra="allow")
    value: str | None
    raw: str
    source: GroundedFieldSource
    requires_review: bool


class RuntimeDocument(RuntimeRecord):
    well_id: str
    title: str
    doc_type: str
    pages: int = Field(ge=0)
    is_scan: bool
    ocr_confidence: float = Field(ge=0, le=1)
    review_status: ReviewStatus
    event_ids: list[str]
    coverage_ids: list[str]
    page_data: list[DocumentPage] = Field(default_factory=list)
    path: str | None = None
    extractor_version: str | None = None
    classification: Literal["PUBLIC", "PRIVATE"] = "PRIVATE"
    doc_type_source: Literal["DECLARED", "CONTENT", "UNKNOWN"] = "UNKNOWN"
    numerical_fields: dict[str, NumericalField] = Field(default_factory=dict)
    date_coverage: DateCoverage | None = None
    date_coverages: list[DateCoverage] = Field(default_factory=list)
    well_identity_status: Literal["MATCHED", "MISMATCHED", "UNKNOWN"] = "UNKNOWN"
    well_identity: list[WellIdentity] = Field(default_factory=list)
    dates: list[ExtractedDate] = Field(default_factory=list)


class RuntimeCoverage(RuntimeRecord):
    well_id: str
    document_id: str
    page: int = Field(ge=1)
    md_interval: tuple[float, float] | None
    coverage_status: CoverageStatus
    datum: str
    date_from: str | None = None
    date_to: str | None = None
    date_coverage_status: CoverageStatus = CoverageStatus.UNKNOWN
    date_source: GroundedFieldSource | None = None


class RuntimeSourceSpan(RuntimeRecord):
    document_id: str
    page: int = Field(ge=1)
    text: str
    bbox: list[float] | None
    char_start: int
    char_end: int


class RuntimeTrajectory(RuntimeRecord):
    points: list[SurveyStation]
    crs: str
    datum: str


class RuntimeReview(RuntimeRecord):
    kind: Literal["event", "coverage", "document"]
    entity_id: str
    document_id: str
    status: Literal["PENDING", "RESOLVED"]
    reason: str
    priority: Literal["HIGH", "MEDIUM", "LOW"]


class Projection(BaseModel):
    model_config = ConfigDict(extra="allow")
    decision: Literal["PROJECTED", "BLOCKED"]
    projected_md_interval_m: tuple[float, float] | None
    algorithm_version: str | None = None
    reason: str | None = None


class RuntimeAlignment(RuntimeRecord, Projection):
    event_id: str
    active_well_id: str
    formation: str
    source_span_id: str
    computed_at: datetime


class AnalogAssessment(BaseModel):
    model_config = ConfigDict(extra="allow", allow_inf_nan=False)
    well_id: str
    decision: str
    relevance: float
    support: list[str]
    penalties: list[str]
    unknowns: list[str]
    blockers: list[str]


class TransferAssessment(AnalogAssessment):
    event_id: str
    event_type: EventType
    document_id: str | None
    source_span_id: str | None
    weight: float
    projection: Projection | None
    factors: dict[str, float]


class RuntimeTransfer(RuntimeRecord, TransferAssessment):
    computed_at: datetime


class EvidenceRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    well_id: str
    role: EvidenceRole
    weight: float
    reason: str
    analog: AnalogAssessment
    transfers: list[TransferAssessment]


class EvidenceStatistics(BaseModel):
    p_hat: float | None
    n_eff: float
    sum_weights: float


class RuntimeEvidence(RuntimeRecord):
    active_well_id: str
    formation: str
    risk: EventType
    md_interval_m: tuple[float, float]
    operation_state: OperationState
    state: EvidenceState
    sentence: str
    support_count: int
    counter_count: int
    unknown_count: int
    excluded_count: int
    internal_statistics: EvidenceStatistics
    rows: list[EvidenceRow]
    policy_version: str
    context_source: str
    computed_at: datetime


class ReplayFrame(BaseModel):
    model_config = ConfigDict(extra="allow")
    elapsed_s: float
    values: dict[str, float | str | None]


class RuntimeDataset(RuntimeRecord):
    frames: list[ReplayFrame]
    frame_count: int
    source: str
    simulation: bool


class StoredSample(BaseModel):
    model_config = ConfigDict(extra="allow")
    value: float | str | None
    timestamp: datetime
    quality_status: Literal["VALID", "SUSPECT", "MISSING"] = "VALID"
    unit: str | None = None
    datum: str = "UNKNOWN"
    reference: str = "UNKNOWN"


class QualityEvent(BaseModel):
    cursor: int
    failures: dict[str, str]


class RuntimeSession(RuntimeRecord):
    episode_active: bool = True
    playback_elapsed_s: float | None = None
    playing: bool = False
    speed: float = Field(default=1, gt=0, le=100)
    generation: int = Field(default=0, ge=0)
    wall_anchor: datetime | None = None
    elapsed_anchor: float | None = None
    well_id: str
    adapter: Literal["REPLAY", "MANUAL"]
    dataset_id: str | None
    cursor: int
    frame_count: int
    formation: str
    md_interval_m: tuple[float, float]
    radius_km: float
    epoch: datetime
    simulation: bool
    failures: dict[str, str]
    quality_events: list[QualityEvent]
    samples: dict[str, StoredSample]
    history: list[ContextHistory]


class RuntimeAlertAudit(RuntimeRecord):
    event: str
    actor: str
    timestamp: datetime
    notified: bool
    alert_id: str
    simulation_timestamp: datetime | None = None


class AlertHistory(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    event: str
    actor: str
    timestamp: datetime
    notified: bool


class RuntimeAlert(RuntimeRecord):
    session_ids: list[str] = Field(default_factory=list)
    restart_pending: bool = False
    session_id: str
    well_id: str
    risk_type: EventType
    formation: str
    md_interval_m: tuple[float, float]
    lifecycle: AlertLifecycle
    evidence_state: EvidenceState
    peak_state: EvidenceState
    simulation: bool
    notification_count: int
    history: list[AlertHistory]
    created_at: datetime
    snoozed_until: datetime | None
    resolved_at: datetime | None
    evidence_snapshot_id: str

    @model_validator(mode="after")
    def sessions(self):
        if self.session_id not in self.session_ids: self.session_ids.append(self.session_id)
        return self


class RuntimeSimulationAudit(RuntimeRecord):
    session_id: str
    channel: str
    quality: str
    timestamp: datetime


class RuntimeAudit(RuntimeRecord):
    timestamp: datetime
    reviewer: str
    action: str
    entity_id: str
    before: RuntimeEvent | RuntimeCoverage | RuntimeDocument
    after: RuntimeEvent | RuntimeCoverage | RuntimeDocument


class ReplayScore(BaseModel):
    model_config = ConfigDict(extra="allow", allow_inf_nan=False)
    alert_count: int = Field(ge=0)
    hits: int = Field(ge=0)
    misses: int = Field(ge=0)
    false_alerts: int = Field(ge=0)
    lead_distance_m: list[float]
    evaluated_frames: int = Field(ge=0)
    negative_case_count: int = Field(ge=0)
    specificity: float | None = None
    accuracy: float | None = None


class HeldOutResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    well_id: str
    risk: EventType
    expected_event_count: int = Field(ge=0)
    evidence_coverage_wells: int = Field(ge=0)
    source_status: str = ""
    baselines: dict[str, ReplayScore]


class RuntimeValidationReport(RuntimeRecord):
    version: str
    generated_at: datetime
    generator_version: str
    seed: int
    input_sha256: str
    repository_sha256: str = ""
    results: list[HeldOutResult]
    policies: dict[str, dict]
    limitations: list[str]


class SecondaryIndicator(BaseModel):
    model_config = ConfigDict(extra="allow", allow_inf_nan=False)
    name: str
    value: float | None
    baseline: float | None = None
    change: float | None = None
    available: bool
    triggered: bool
    provenance_type: Literal["COMPUTED"]
    interpretation: str | None = None
    formula: str | None = None
    inputs: dict[str, float | None] | None = None


class SecondaryModule(BaseModel):
    model_config = ConfigDict(extra="allow", allow_inf_nan=False)
    risk_type: EventType
    maturity: Literal["PARTIAL_DECISION_SUPPORT", "CONSERVATIVE_INDICATORS", "SUPPORTING_INDICATORS", "HISTORICAL_PLANNING_ONLY"]
    status: Literal["HISTORICAL_PLANNING", "CORROBORATING_INDICATORS", "SIGNALS_FOR_REVIEW", "CONTEXT_ONLY"]
    warning_allowed: Literal[False]
    historical: RuntimeEvidence
    operation_state: str
    operation_bound: bool
    indicators: list[SecondaryIndicator]
    limitations: list[str]
    simulation: Literal[True]
    algorithm_version: str


MODELS = {"well": RuntimeWell, "event": RuntimeEvent, "document": RuntimeDocument,
          "coverage": RuntimeCoverage, "source_span": RuntimeSourceSpan, "trajectory": RuntimeTrajectory,
          "review": RuntimeReview, "alignment": RuntimeAlignment, "transferability": RuntimeTransfer,
          "evidence_snapshot": RuntimeEvidence, "replay_dataset": RuntimeDataset, "live_session": RuntimeSession,
          "alert": RuntimeAlert, "alert_audit": RuntimeAlertAudit, "audit": RuntimeAudit,
          "simulation_audit": RuntimeSimulationAudit, "validation_report": RuntimeValidationReport}


def validate_record(kind, record):
    model = MODELS.get(kind)
    return model.model_validate(record).model_dump(mode="json") if model else record
