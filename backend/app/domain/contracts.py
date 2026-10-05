from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from .units import Measurement

from .enums import (
    AlertLifecycle,
    CoverageStatus,
    EventType,
    EvidenceRole,
    EvidenceState,
    Freshness,
    OperationState,
    ProvenanceType,
    ReviewStatus,
)


Metres = Annotated[float, Field(description="Canonical metres")]


class SourceRef(BaseModel):
    document_id: str
    page: int = Field(ge=1)
    span_id: str
    excerpt: str


class ProvenanceItem(BaseModel):
    id: str
    type: ProvenanceType
    label: str
    value: str
    source: SourceRef | None = None
    algorithm_version: str | None = None


class FormationInterval(BaseModel):
    id: str
    name: str
    top_md_m: Metres
    base_md_m: Metres
    uncertainty_m: float = Field(ge=0)
    color: str


class WellSummary(BaseModel):
    id: str
    name: str
    field: str
    latitude: float
    longitude: float
    surface_x_km: float
    surface_y_km: float
    status: Literal["ACTIVE", "OFFSET"]
    synthetic: bool = True


class ChannelValue(BaseModel):
    value: float | str | None
    unit: str
    timestamp: datetime | None
    source: str
    quality_status: Freshness = Field(validation_alias=AliasChoices("quality_status", "freshness"))
    age_s: float | None = None
    freshness_threshold_s: float = Field(default=30, gt=0)
    provenance_type: ProvenanceType = ProvenanceType.FACT
    measurement: Measurement | None = None
    synthetic_flag: bool = False


class ContextHistory(BaseModel):
    model_config = ConfigDict(extra="allow")
    timestamp: datetime
    values: dict[str, float | str | None]
    quality_status: Literal["VALID", "SUSPECT", "MISSING"] = "VALID"
    channel_timestamps: dict[str, datetime] = Field(default_factory=dict)
    channel_quality: dict[str, str] = Field(default_factory=dict)


class FormationUncertainty(BaseModel):
    status: Literal["UNKNOWN", "CONFIGURED", "BOUNDARY_OVERLAP"] = "UNKNOWN"
    candidate_formation_ids: list[str] = Field(default_factory=list)
    boundary_overlap: bool = False
    current_uncertainty_m: float | None = Field(default=None, ge=0)
    next_top_interval_m: tuple[float, float] | None = None


class CurrentWellContext(BaseModel):
    well_id: str
    synthetic_flag: bool = False
    measurements: dict[str, Measurement] = Field(default_factory=dict)
    timestamp: datetime
    bit_md_m: Metres | None
    hole_md_m: Metres | None
    tvd_m: Metres | None
    formation_id: str | None
    next_formation_id: str | None
    distance_to_next_top_m: float | None = None
    formation_uncertainty: FormationUncertainty = Field(default_factory=FormationUncertainty)
    hole_section_in: float | None
    inclination_deg: float | None
    operation_state: OperationState
    channels: dict[str, ChannelValue]
    context_conflict: bool = False
    source: str = "UNKNOWN"
    clock: str = "UTC"
    simulation: bool = True
    conflicts: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    field_sources: dict[str, str] = Field(default_factory=dict)
    algorithm_version: str = "current-context/1.0"
    history: list[ContextHistory] = Field(default_factory=list)


class OffsetAssessment(BaseModel):
    well: WellSummary
    surface_distance_km: float
    target_distance_km: float
    relevance: Literal["HIGH", "MEDIUM", "LOW", "EXCLUDED"]
    decision: Literal["INCLUDED", "PENALIZED", "EXCLUDED"]
    support: list[str]
    penalties: list[str]
    unknowns: list[str]


class EvidenceRecord(BaseModel):
    id: str
    role: EvidenceRole
    well_id: str
    well_name: str
    event_type: EventType | None
    formation: str
    historical_md_m: float | None
    projected_interval_m: tuple[float, float]
    summary: str
    coverage: CoverageStatus
    source: SourceRef | None


class RiskInterval(BaseModel):
    id: str
    risk_type: EventType
    formation: str
    interval_from_m: Metres
    interval_to_m: Metres
    uncertainty_m: float
    evidence_state: EvidenceState
    evidence_sentence: str
    support_count: int
    counter_count: int
    unknown_count: int
    evidence: list[EvidenceRecord]


class Alert(BaseModel):
    id: str
    well_id: str
    risk_type: EventType
    evidence_state: EvidenceState
    lifecycle: AlertLifecycle
    formation: str
    interval_from_m: Metres
    interval_to_m: Metres
    title: str
    message: str
    created_at: datetime


class DocumentSummary(BaseModel):
    id: str
    well_id: str
    well_name: str
    title: str
    doc_type: Literal["WCR", "DDR", "MUD_LOG", "CEMENT_REPORT"]
    pages: int
    is_scan: bool
    ocr_confidence: float = Field(ge=0, le=1)
    review_status: ReviewStatus
    synthetic: bool = True


class ReviewItem(BaseModel):
    id: str
    document_id: str
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    reason: str
    extracted_value: str
    source_excerpt: str
    review_status: ReviewStatus


class ValidationMetric(BaseModel):
    label: str
    value: str
    trend: str


class DashboardPayload(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data_mode: Literal["MOCK", "SYNTHETIC", "API"] = "API"
    active_well: WellSummary
    context: CurrentWellContext
    formations: list[FormationInterval]
    offsets: list[OffsetAssessment]
    risks: list[RiskInterval]
    alerts: list[Alert]
    provenance: list[ProvenanceItem]
