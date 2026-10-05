from enum import StrEnum


class ExtractionConfidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class CauseType(StrEnum):
    STATED = "stated"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class ProvenanceType(StrEnum):
    FACT = "FACT"
    COMPUTED = "COMPUTED"
    INFERRED = "INFERRED"


class EvidenceState(StrEnum):
    NO_EVIDENCE = "NO_EVIDENCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    LESSON = "LESSON"
    ELEVATED = "ELEVATED"
    WARNING = "WARNING"


class EvidenceRole(StrEnum):
    EXCLUDED = "EXCLUDED"
    SUPPORT = "SUPPORT"
    COUNTER = "COUNTER"
    UNKNOWN = "UNKNOWN"


class Freshness(StrEnum):
    FRESH = "FRESH"
    STALE = "STALE"
    MISSING = "MISSING"
    SUSPECT = "SUSPECT"


class OperationState(StrEnum):
    TRIPPING = "TRIPPING"
    DRILLING = "DRILLING"
    REAMING = "REAMING"
    CIRCULATING = "CIRCULATING"
    CONNECTION = "CONNECTION"
    TRIPPING_IN = "TRIPPING_IN"
    TRIPPING_OUT = "TRIPPING_OUT"
    CEMENTING = "CEMENTING"
    LOGGING = "LOGGING"
    STATIC = "STATIC"
    UNKNOWN = "UNKNOWN"


class EventType(StrEnum):
    MUD_LOSS = "MUD_LOSS"
    STUCK_PIPE = "STUCK_PIPE"
    KICK = "KICK"
    TORQUE_DYSFUNCTION = "TORQUE_DYSFUNCTION"
    CEMENTING_ISSUE = "CEMENTING_ISSUE"


class AlertLifecycle(StrEnum):
    CREATED = "CREATED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    SNOOZED = "SNOOZED"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"


class CoverageStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PROBABLE = "PROBABLE"
    UNKNOWN = "UNKNOWN"


class ReviewStatus(StrEnum):
    VERIFIED = "VERIFIED"
    AUTO_ACCEPTED = "AUTO_ACCEPTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    QUARANTINED = "QUARANTINED"
