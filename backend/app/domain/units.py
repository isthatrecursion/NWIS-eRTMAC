"""Canonical conversions retaining the source quantity and its reference system."""
import math
from typing import Literal
from pydantic import BaseModel


class Measurement(BaseModel):
    value: float
    unit: str
    original_value: float
    original_unit: str
    datum: str = "UNKNOWN"
    reference: str = "UNKNOWN"
    source: str = "UNKNOWN"
    algorithm_version: str = "units/1.0"
    synthetic_flag: bool | None = None


FACTORS = {
    "depth": ("m", {"m": 1., "metres": 1., "meters": 1., "ft": .3048, "feet": .3048}),
    "density": ("sg", {"sg": 1., "g/cm3": 1., "kg/m3": .001, "ppg": .119826427316}),
    "pressure": ("kPa", {"kPa": 1., "Pa": .001, "MPa": 1000., "bar": 100., "psi": 6.894757293168}),
}


def normalize(value: float, unit: str, quantity: Literal["depth", "density", "pressure"],
              datum="UNKNOWN", reference="UNKNOWN", source="UNKNOWN") -> Measurement:
    canonical, factors = FACTORS[quantity]
    if isinstance(value, bool) or not math.isfinite(value):
        raise ValueError("Measurement must be finite")
    if unit not in factors:
        raise ValueError(f"Unsupported {quantity} unit: {unit}")
    return Measurement(value=value*factors[unit], unit=canonical, original_value=value,
                       original_unit=unit, datum=datum, reference=reference, source=source)


def enrich(record, inherited_flag=None, datum="UNKNOWN"):
    """Annotate canonical numeric fields without discarding existing raw measurements."""
    if isinstance(record, list):
        return [enrich(item, inherited_flag, datum) for item in record]
    if not isinstance(record, dict):
        return record
    flag = record.get("synthetic_flag", record.get("synthetic", inherited_flag))
    datum = record.get("datum", datum)
    result = {key: value if key in ("values", "failures", "field_sources", "factors", "channel_timestamps", "channel_quality", "gates", "context_values") else
              {name: enrich(item, flag, datum) for name, item in value.items() if name not in ("synthetic_flag", "synthetic", "measurements")} if key in ("samples", "channels", "numerical_fields", "field_evidence", "baselines", "policies", "metrics", "event_types", "rules") and isinstance(value, dict) else
              enrich(value, flag, datum) for key, value in record.items()
              if key != "measurements"}
    if flag is not None:
        result["synthetic_flag"] = bool(flag)
    measurements = dict(record.get("measurements", {}))
    for key, value in record.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        quantity, unit = ("depth", "m") if key.endswith("_m") and key != "torque_kn_m" else ("density", "sg") if key.endswith("_sg") else ("pressure", "kPa") if key.endswith("_kpa") else (None, None)
        if quantity and key not in measurements:
            measurements[key] = normalize(value, unit, quantity, datum,
                "TVD" if "tvd" in key else "MD" if "md" in key else "UNKNOWN").model_dump()
    if measurements:
        if flag is not None:
            measurements = {key: {**item, "synthetic_flag": bool(flag)} if isinstance(item, dict) else item
                            for key, item in measurements.items()}
        result["measurements"] = measurements
    return result
