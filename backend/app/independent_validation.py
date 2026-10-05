"""Human-only validation workflows. These endpoints never manufacture sign-off."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from threading import Lock
from uuid import uuid4

import fitz
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field, model_validator

from .paths import DATA_ROOT

router = APIRouter(prefix="/api/validation", tags=["independent-validation"])
_file_lock = Lock()


def _gold_dir() -> Path:
    direct = DATA_ROOT / "gold"
    shared = DATA_ROOT.parent / "gold"
    return direct if direct.exists() or not shared.exists() else shared


def _validation_dir() -> Path:
    direct = DATA_ROOT / "validation"
    shared = DATA_ROOT.parent / "validation"
    return direct if direct.exists() or not shared.exists() else shared


def _read(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_atomic(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


class Box(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def within_page(self):
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("Bounding box must remain within the page")
        return self


class EventAnnotation(BaseModel):
    event_index: int = Field(ge=0)
    source_bbox: Box
    comment: str = Field(default="", max_length=1000)


class GoldReview(BaseModel):
    reviewer: str = Field(min_length=2, max_length=120)
    independent_human_attestation: bool
    decision: str = Field(pattern="^(ACCEPTED|CORRECTED)$")
    annotations: list[EventAnnotation] = Field(default_factory=list)
    comment: str = Field(default="", max_length=4000)


def _labels():
    path = _gold_dir() / "labels.json"
    if not path.exists():
        raise HTTPException(503, "Gold reference has not been generated")
    return _read(path, {})


def _reviews():
    return _read(_gold_dir() / "human_reviews.json", {"version": "human-gold-review/1.0", "reviews": {}})


def _summary(labels, reviews):
    pages = labels.get("pages", [])
    accepted = 0
    boxes = 0
    expected_boxes = sum(len(page.get("events", [])) for page in pages)
    reviewers = set()
    for page in pages:
        review = reviews.get("reviews", {}).get(page["id"])
        if review and review.get("decision") in {"ACCEPTED", "CORRECTED"}:
            accepted += 1
            boxes += len(review.get("annotations", []))
            reviewers.add(review["reviewer"])
    complete = bool(pages) and accepted == len(pages) and boxes == expected_boxes
    return {
        "status": "INDEPENDENT_HUMAN_SIGNOFF_COMPLETE" if complete else "HUMAN_REVIEW_PENDING",
        "page_count": len(pages), "reviewed_pages": accepted,
        "expected_event_boxes": expected_boxes, "completed_event_boxes": boxes,
        "reviewer_count": len(reviewers), "independent_human_signoff": complete,
        "scope": "Synthetic authored extraction reference; sign-off is separate from extractor output",
    }


@router.get("/gold/pages")
def gold_pages():
    labels, reviews = _labels(), _reviews()
    return {
        "summary": _summary(labels, reviews),
        "pages": [{
            "id": page["id"], "page": page["page"], "scanned": page.get("scanned", False),
            "text": page.get("text", ""), "events": page.get("events", []),
            "review": reviews.get("reviews", {}).get(page["id"]),
            "image_url": f"/api/validation/gold/pages/{page['page']}/image",
        } for page in labels.get("pages", [])],
    }


@router.get("/gold/pages/{page_number}/image")
def gold_page_image(page_number: int):
    labels = _labels()
    if not 1 <= page_number <= len(labels.get("pages", [])):
        raise HTTPException(404, "Gold page not found")
    with fitz.open(_gold_dir() / "representative_pages.pdf") as pdf:
        pixmap = pdf[page_number - 1].get_pixmap(matrix=fitz.Matrix(1.3, 1.3), alpha=False)
        return Response(pixmap.tobytes("png"), media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/gold/pages/{page_id}/review")
def save_gold_review(page_id: str, request: GoldReview):
    if not request.independent_human_attestation:
        raise HTTPException(422, "Independent human attestation is required")
    if re.search(r"\b(ai|bot|automation|codex|chatgpt|model)\b", request.reviewer, re.I):
        raise HTTPException(422, "Reviewer must identify the independent human who performed the review")
    labels = _labels()
    page = next((item for item in labels.get("pages", []) if item["id"] == page_id), None)
    if page is None:
        raise HTTPException(404, "Gold page not found")
    expected = len(page.get("events", []))
    indices = [item.event_index for item in request.annotations]
    if len(indices) != expected or sorted(indices) != list(range(expected)):
        raise HTTPException(422, "Provide exactly one bounding box for every expected event")
    now = datetime.now(timezone.utc).isoformat()
    record = request.model_dump(mode="json") | {"page_id": page_id, "reviewed_at": now, "id": uuid4().hex}
    with _file_lock:
        reviews = _reviews()
        reviews["reviews"][page_id] = record
        reviews["updated_at"] = now
        _write_atomic(_gold_dir() / "human_reviews.json", reviews)
    return {"review": record, "summary": _summary(labels, reviews)}


class UsabilityResult(BaseModel):
    participant_code: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    independent_human_attestation: bool
    elapsed_seconds: float = Field(gt=0, le=600)
    identified_risk: str = Field(min_length=2, max_length=100)
    identified_reason: str = Field(min_length=5, max_length=1000)
    reason_choice: str = Field(pattern="^(HISTORICAL_OFFSET_LOSSES_PROJECTED_AHEAD|LOW_BATTERY|WEATHER_FORECAST|UNKNOWN)$")
    opened_source: bool
    expected_risk: str = Field(default="MUD_LOSS", pattern="^MUD_LOSS$")


def _usability_summary(rows):
    valid = [row for row in rows if row.get("independent_human_attestation")]
    passes = [row for row in valid if row["correct"] and row["elapsed_seconds"] <= 20]
    enough = len({row["participant_code"] for row in valid}) >= 5
    return {
        "status": "MEASURED" if enough else "PARTICIPANTS_REQUIRED",
        "participant_count": len({row["participant_code"] for row in valid}),
        "minimum_participants": 5,
        "within_20_seconds_and_correct": len(passes),
        "success_rate": round(len(passes) / len(valid), 4) if valid else None,
        "criterion_verified": enough and len(passes) / len(valid) >= 0.8,
        "criterion": "At least 80% of five or more independent participants identify the active risk and reason within 20 seconds",
    }


@router.get("/usability")
def usability_status():
    document = _read(_validation_dir() / "usability-results.json", {"version": "brief-usability/1.0", "results": []})
    return {"summary": _usability_summary(document["results"]), "results": document["results"]}


@router.post("/usability")
def record_usability(request: UsabilityResult):
    if not request.independent_human_attestation:
        raise HTTPException(422, "Human participant attestation is required")
    if re.search(r"\b(ai|bot|automation|codex|chatgpt|model)\b", request.participant_code, re.I):
        raise HTTPException(422, "Participant code must represent an independent human participant")
    record = request.model_dump(mode="json")
    record["correct"] = (request.identified_risk.strip().upper().replace(" ", "_") == request.expected_risk
                         and request.reason_choice == "HISTORICAL_OFFSET_LOSSES_PROJECTED_AHEAD")
    record["recorded_at"] = datetime.now(timezone.utc).isoformat()
    with _file_lock:
        path = _validation_dir() / "usability-results.json"
        document = _read(path, {"version": "brief-usability/1.0", "results": []})
        document["results"] = [row for row in document["results"] if row["participant_code"] != request.participant_code]
        document["results"].append(record)
        _write_atomic(path, document)
    return {"result": record, "summary": _usability_summary(document["results"])}


@router.get("/external-status")
def external_status():
    validation = _validation_dir()
    return {
        "docker_postgis": _read(validation / "docker-postgis.json", {"status": "NOT_RUN"}),
        "production_assessment": _read(validation / "production-assessment.json", {"production_readiness": "NOT_ASSESSED"}),
        "field_validation": _read(validation / "field-validation.json", {"status": "PENDING_EXTERNAL_FIELD_DATA"}),
    }
