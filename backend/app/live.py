"""Label-free replay/CSV/manual adapters and canonical current-context resolution."""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
import csv
import io
import math
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .geometry import position, trajectory
from .domain.contracts import CurrentWellContext
from .domain.enums import OperationState
from .domain.units import enrich, normalize
from .config import get_settings

VERSION = "current-context/2.0"
OPS = {state.value for state in OperationState}
CHANNELS = {"bit_md_m": ("m", 0, 15000), "hole_md_m": ("m", 0, 15000),
            "flow_in_l_min": ("L/min", 0, 10000), "flow_out_l_min": ("L/min", 0, 10000),
            "pit_volume_m3": ("m3", 0, 10000), "ecd_sg": ("sg", .5, 3),
            "tvd_m": ("m", 0, 15000), "inclination_deg": ("deg", 0, 180),
            "hole_section_in": ("in", 1, 50)}
FRESHNESS_SECONDS = 30
CHANNELS["standpipe_pressure_kpa"] = ("kPa", 0, 100000)
CHANNELS.update({"mud_weight_sg": ("sg", .5, 3), "wob_kn": ("kN", 0, 2000),
                 "rpm": ("rpm", 0, 1000), "torque_kn_m": ("kN.m", 0, 500),
                 "hookload_kn": ("kN", 0, 10000), "gas_pct": ("%", 0, 100)})
CHANNELS["rop_m_h"] = ("m/h", 0, 1000)


def freshness_threshold(name):
    return get_settings().channel_freshness_s.get(name, FRESHNESS_SECONDS)


def utc_now(): return datetime.now(timezone.utc)


def stamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if result.tzinfo is None: raise ValueError("Channel timestamp must include a UTC offset")
    return result.astimezone(timezone.utc)


class Sample(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: float | str | None
    timestamp: datetime
    quality_status: Literal["VALID", "SUSPECT", "MISSING"] = "VALID"
    unit: str | None = None
    datum: str = "UNKNOWN"
    reference: str = "UNKNOWN"

    @field_validator("timestamp")
    @classmethod
    def aware(cls, value): return stamp(value)

    @field_validator("value")
    @classmethod
    def finite(cls, value):
        if isinstance(value, float) and not math.isfinite(value): raise ValueError("Non-finite channel value")
        return value


def channel(name, sample, now, source):
    unit, low, high = CHANNELS.get(name, ("state", None, None))
    value = sample.get("value") if sample else None
    measurement = None
    quantity = "density" if name.endswith("_sg") else "pressure" if name.endswith("_kpa") else "depth" if name in ("bit_md_m", "hole_md_m", "tvd_m") else None
    if not quantity and sample and sample.get("unit") not in (None, unit):
        sample = {**sample, "quality_status": "SUSPECT"}
    if quantity and isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        try:
            measurement = normalize(value, sample.get("unit") or unit, quantity, sample.get("datum", "UNKNOWN"),
                sample.get("reference") if sample.get("reference") not in (None, "UNKNOWN") else "TVD" if name == "tvd_m" else "MD" if "md" in name else "UNKNOWN", source).model_dump()
            value = measurement["value"]
            if quantity == "depth" and measurement["reference"] not in ("UNKNOWN", "TVD" if name == "tvd_m" else "MD"):
                sample = {**sample, "quality_status": "SUSPECT"}
                value = None
        except ValueError:
            sample = {**sample, "quality_status": "SUSPECT"}
            value = None
    timestamp = stamp(sample["timestamp"]) if sample else None
    age = (now-timestamp).total_seconds() if timestamp else None
    quality = "MISSING" if value is None else "SUSPECT" if sample.get("quality_status") == "SUSPECT" else "FRESH"
    if sample and sample.get("quality_status") == "MISSING": quality = "MISSING"; value = None
    if value is not None:
        if name == "operation_state":
            if value not in OPS: quality = "SUSPECT"
        elif not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not low <= value <= high:
            quality = "SUSPECT"
            if isinstance(value, (int, float)) and not math.isfinite(value): value = None
        if age is not None and age < -1: quality = "SUSPECT"
        elif quality == "FRESH" and age is not None and age > freshness_threshold(name): quality = "STALE"
    return {"value": value, "unit": unit, "timestamp": timestamp.isoformat() if timestamp else None,
            "source": source, "quality_status": quality, "age_s": age, "freshness_threshold_s": freshness_threshold(name), "provenance_type": "FACT", "measurement": measurement}


def parse_csv(content):
    if len(content) > 1024*1024: raise ValueError("Replay CSV exceeds 1 MB")
    try: reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    except UnicodeDecodeError as exc: raise ValueError("CSV must be UTF-8") from exc
    required = {"elapsed_s", "bit_md_m", "operation_state"}
    if not reader.fieldnames or not required <= set(reader.fieldnames): raise ValueError("CSV requires elapsed_s, bit_md_m and operation_state")
    if set(reader.fieldnames)-required-set(CHANNELS): raise ValueError("Unknown CSV columns; event labels are not allowed in telemetry")
    rows = []
    try:
        for raw in reader:
            if len(rows) >= 5000: raise ValueError("CSV exceeds 5000 frames")
            elapsed = float(raw["elapsed_s"])
            if not math.isfinite(elapsed) or not 0 <= elapsed <= 604800 or (rows and elapsed <= rows[-1]["elapsed_s"]):
                raise ValueError("elapsed_s must be finite, within seven days and strictly increasing")
            if raw["operation_state"] not in OPS: raise ValueError("Unknown operation_state")
            values = {name: float(raw[name]) if raw.get(name) not in (None, "") else None for name in CHANNELS if name in raw}
            for name, value in values.items():
                if value is not None and (not math.isfinite(value) or not CHANNELS[name][1] <= value <= CHANNELS[name][2]):
                    raise ValueError(f"Invalid {name} value")
            if values.get("bit_md_m") is None: raise ValueError("bit_md_m is required in every frame")
            rows.append({"elapsed_s": elapsed, "values": {**values, "operation_state": raw["operation_state"]}})
    except (TypeError, KeyError) as exc: raise ValueError("Malformed CSV row") from exc
    if not rows: raise ValueError("CSV contains no frames")
    return rows


def resolve_context(well, samples, now, source, clock="UTC", history=None):
    channels = {name: channel(name, samples.get(name), now, source) for name in (*CHANNELS, "operation_state")}
    conflicts, missing, origins = [], [], {}
    def observed(name):
        item = channels[name]
        return item["value"] if item["quality_status"] == "FRESH" else None
    depth = observed("bit_md_m")
    hole = observed("hole_md_m")
    if hole is None and depth is not None:
        # Bit depth is not known hole depth, particularly while tripping.
        missing.append("hole depth unavailable; bit depth is not substituted")
    if hole is not None and depth is not None and depth > hole+1: conflicts.append("bit depth exceeds observed hole depth")
    tvd, inclination, current, next_formation = None, None, None, None
    next_top_distance, uncertainty = None, {"status": "UNKNOWN", "candidate_formation_ids": [], "boundary_overlap": False}
    if depth is not None:
        try:
            survey = trajectory(well["survey"], well["x_m"], well["y_m"])
            computed = position(survey, depth)["tvd_m"]
            tvd = observed("tvd_m")
            if tvd is not None and abs(tvd-computed) > 25: conflicts.append("observed TVD differs from survey by more than 25 m")
            if tvd is None: tvd = computed; origins["tvd_m"] = "COMPUTED minimum curvature"
            else: origins["tvd_m"] = source
            for a, b in zip(well["survey"], well["survey"][1:]):
                if a["md_m"] <= depth <= b["md_m"]:
                    inclination = a["incl_deg"]+(b["incl_deg"]-a["incl_deg"])*(depth-a["md_m"])/(b["md_m"]-a["md_m"]); break
            live_inc = observed("inclination_deg")
            if live_inc is not None:
                if inclination is not None and abs(live_inc-inclination) > 5: conflicts.append("observed inclination conflicts with survey")
                inclination = live_inc; origins["inclination_deg"] = source
            else: origins["inclination_deg"] = "COMPUTED survey interpolation"
        except (ValueError, KeyError) as exc: conflicts.append(f"survey context unavailable: {exc}")
        formations = sorted(well.get("formations", []), key=lambda f: f["top_md_m"])
        matches = [f for f in formations if f.get("base_md_m") is not None and f["top_md_m"] <= depth < f["base_md_m"]]
        if len(matches) > 1: conflicts.append("overlapping formation intervals")
        elif matches:
            current = matches[0]["formation_id"]
            upcoming = [f for f in formations if f["top_md_m"] >= matches[0]["base_md_m"]]
            next_formation = upcoming[0]["formation_id"] if upcoming else None
            next_top_distance = upcoming[0]["top_md_m"]-depth if upcoming else None
            boundary = min(abs(depth-matches[0]["top_md_m"]), abs(depth-matches[0]["base_md_m"])) <= matches[0].get("uncertainty_m", 0)
            candidates = [f["formation_id"] for f in formations if f.get("base_md_m") is not None and f["top_md_m"]-f.get("uncertainty_m", 0) <= depth <= f["base_md_m"]+f.get("uncertainty_m", 0)]
            uncertainty = {"status": "BOUNDARY_OVERLAP" if boundary else "CONFIGURED", "candidate_formation_ids": candidates,
                "boundary_overlap": boundary, "current_uncertainty_m": matches[0].get("uncertainty_m", 0),
                "next_top_interval_m": [upcoming[0]["top_md_m"]-upcoming[0].get("uncertainty_m", 0), upcoming[0]["top_md_m"]+upcoming[0].get("uncertainty_m", 0)] if upcoming else None}
            if min(abs(depth-matches[0]["top_md_m"]), abs(depth-matches[0]["base_md_m"])) <= matches[0].get("uncertainty_m", 0):
                missing.append("formation boundary uncertainty overlaps bit depth")
        else: missing.append("formation cannot be confirmed at bit depth")
    else: missing.append("fresh bit depth unavailable")
    section = observed("hole_section_in")
    if section is None:
        section = well.get("mud_program", {}).get("hole_section_in"); origins["hole_section_in"] = "FALLBACK stored programme"
    else:
        origins["hole_section_in"] = source
        programmed = well.get("mud_program", {}).get("hole_section_in")
        if programmed is not None and abs(section-programmed) > .5: conflicts.append("observed hole section conflicts with programme")
    result = {"well_id": well["id"], "timestamp": now.isoformat(), "clock": clock, "source": source,
            "simulation": True, "bit_md_m": depth, "hole_md_m": hole, "tvd_m": tvd,
            "inclination_deg": inclination, "formation_id": current, "next_formation_id": next_formation,
            "distance_to_next_top_m": next_top_distance, "formation_uncertainty": uncertainty,
            "hole_section_in": section, "operation_state": observed("operation_state") or "UNKNOWN",
            "channels": channels, "context_conflict": bool(conflicts), "conflicts": conflicts,
            "missing": missing, "field_sources": origins, "algorithm_version": VERSION, "history": history or []}
    return CurrentWellContext.model_validate(enrich(result,
        well.get("synthetic_flag", well.get("synthetic", False)), well.get("datum", "UNKNOWN"))).model_dump(mode="json")


class LiveDataAdapter(ABC):
    @abstractmethod
    async def get_current_context(self, well_id): ...

    @abstractmethod
    def stream_updates(self, well_id): ...


class ReplayAdapter(LiveDataAdapter):
    def __init__(self, well, frames, session):
        self.well, self.frames, self.session = well, frames, session

    def context_at(self, cursor=None):
        cursor = self.session["cursor"] if cursor is None else cursor
        frame = self.frames[cursor]
        now = stamp(self.session["epoch"])+timedelta(seconds=frame["elapsed_s"])
        samples = {key: {"value": value, "timestamp": now.isoformat(), "quality_status": "VALID"} for key, value in frame["values"].items()}
        for key, failure in self.session.get("failures", {}).items():
            if key not in samples: continue
            if failure == "STALE": samples[key]["timestamp"] = (now-timedelta(seconds=freshness_threshold(key)+1)).isoformat()
            elif failure == "MISSING": samples[key]["value"] = None
            elif failure == "SUSPECT": samples[key]["quality_status"] = "SUSPECT"
        history = []
        for index, previous in enumerate(self.frames[:cursor]):
            if 0 < frame["elapsed_s"]-previous["elapsed_s"] <= get_settings().mud_loss_policy.trend_max_s:
                at = stamp(self.session["epoch"])+timedelta(seconds=previous["elapsed_s"])
                quality = next((item["failures"] for item in reversed(self.session.get("quality_events", [])) if item["cursor"] <= index), {})
                required_bad = any(name in quality for name in ("bit_md_m", "operation_state", "flow_in_l_min", "flow_out_l_min", "pit_volume_m3", "ecd_sg"))
                history.append({"timestamp": at.isoformat(), "values": previous["values"], "channel_quality": dict(quality),
                                "quality_status": "SUSPECT" if required_bad else "VALID"})
        return resolve_context(self.well, samples, now, "REPLAY_CSV", "REPLAY_SIMULATION", history)

    async def get_current_context(self, well_id):
        if well_id != self.well["id"]: raise ValueError("Adapter well mismatch")
        return self.context_at()

    async def stream_updates(self, well_id):
        if well_id != self.well["id"]: raise ValueError("Adapter well mismatch")
        for index in range(self.session["cursor"], len(self.frames)):
            yield self.context_at(index)


class CSVAdapter(ReplayAdapter):
    """Validated uploaded CSV uses the same replay clock and interface."""


class ManualAdapter(LiveDataAdapter):
    def __init__(self, well, samples, history=None): self.well, self.samples, self.history = well, samples, history

    def context_at(self, now=None): return resolve_context(self.well, self.samples, now or utc_now(), "MANUAL", history=self.history)

    async def get_current_context(self, well_id):
        if well_id != self.well["id"]: raise ValueError("Adapter well mismatch")
        return self.context_at()

    async def stream_updates(self, well_id):
        yield await self.get_current_context(well_id)
