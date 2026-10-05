"""Auditable prototype context comparisons; missing inputs reduce transfer weight."""
import math
from .config import get_settings
from .geometry import inclination_at, position, trajectory

VERSION = "risk-context/2.0"
POLICY = {"version": VERSION, "missing_factor": .85, "inclination_tolerance_deg": 15,
          "pressure_tolerance_kpa": 5000, "mud_weight_tolerance_sg": .15, "era_tolerance_years": 10,
          "stationary_tolerance_h": 2, "gas_tolerance_pct": 2, "influx_tolerance_m3": 1,
          "basis": "uncalibrated similarity policy for synthetic demonstration"}


def number(value):
    return value if isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) else None


def values(well, event=None):
    result = {}
    for context in (well.get("mud_program", {}), well.get("pressure_context", {}), well.get("operating_context", {})):
        result.update({name: value for name, value in context.items() if value is not None})
    if event:
        result.update(event.get("context_values", {}))
    return result


def year(well, event=None):
    raw = (event or {}).get("event_date") or well.get("drilled_year")
    if raw is None:
        return None
    try:
        value = int(str(raw)[:4])
        return value if 1850 <= value <= 2200 else None
    except (ValueError, TypeError):
        return None


def compare_context(active, offset, risk=None, event=None, projection=None, formation_id=None, include_common=True):
    a, b = values(active), values(offset, event)
    comparisons, support, penalties, unknowns, blockers = [], [], [], [], []
    factor = 1.
    def compare(name, av, bv, tolerance, categorical=False):
        nonlocal factor
        if av is None or bv is None:
            weight, status, delta = POLICY["missing_factor"], "UNKNOWN", None
            unknowns.append(f"missing {name} comparison inputs")
        else:
            delta = 0 if categorical and av == bv else 1 if categorical else abs(av-bv)
            weight = 1. if delta <= tolerance else max(POLICY["missing_factor"], tolerance/max(delta, 1e-9))
            status = "SIMILAR" if delta <= tolerance else "DIFFERENT"
            (support if status == "SIMILAR" else penalties).append(f"{name} comparison: {status.lower()} (difference {delta:.3f})")
        factor *= weight
        comparisons.append({"name": name, "active_value": av, "offset_value": bv, "difference": delta,
                            "tolerance": tolerance, "status": status, "factor": weight, "policy_version": VERSION})
    def mid(well):
        interval = next((item for item in well.get("formations", []) if item["formation_id"] == formation_id), None)
        return (interval["top_md_m"]+interval["base_md_m"])/2 if interval and interval.get("base_md_m") is not None else None
    offset_md = event.get("md_from_m") if event else mid(offset)
    bounds = projection.get("projected_md_interval_m") if projection else None
    active_md = sum(bounds)/2 if bounds else mid(active) if not event else None
    active_inc, offset_inc = inclination_at(active.get("survey", []), active_md), inclination_at(offset.get("survey", []), offset_md)
    if include_common or risk in ("STUCK_PIPE", "TORQUE_DYSFUNCTION"):
        compare("event/target inclination_deg", active_inc, offset_inc, POLICY["inclination_tolerance_deg"])
    if include_common or risk == "KICK":
        compare("pore pressure_kpa", number(a.get("pore_pressure_kpa")), number(b.get("pore_pressure_kpa")), POLICY["pressure_tolerance_kpa"])
    if include_common:
        compare("technology era_year", year(active), year(offset, event), POLICY["era_tolerance_years"])
        compare("drilling technology", active.get("drilling_technology"), offset.get("drilling_technology"), 0, True)
    elif event and event.get("event_date"):
        compare("event technology era_year", year(active), year(offset, event), POLICY["era_tolerance_years"])
    def overbalance(well, inputs, md):
        explicit = number(inputs.get("overbalance_kpa"))
        if explicit is not None:
            return explicit, {"method": "stated", "overbalance_kpa": explicit}
        density, pressure = number(inputs.get("mud_weight_sg")), number(inputs.get("pore_pressure_kpa"))
        if density is None or density <= 0 or pressure is None or md is None:
            return None, {"method": "unknown", "mud_weight_sg": density, "pore_pressure_kpa": pressure, "md_m": md}
        try:
            tvd = position(trajectory(well["survey"]), md)["tvd_m"]
        except (ValueError, KeyError):
            return None, {"method": "survey_unavailable"}
        result = density*9.80665*tvd-pressure
        return result, {"method": "hydrostatic-minus-pore-pressure", "mud_weight_sg": density,
                        "tvd_m": tvd, "pore_pressure_kpa": pressure, "gravity_m_s2": 9.80665}
    derived = {}
    if risk in ("STUCK_PIPE", "KICK"):
        av, ai = overbalance(active, a, active_md)
        bv, bi = overbalance(offset, b, offset_md)
        derived["overbalance"] = {"active": ai, "offset": bi}
        compare("overbalance_kpa", av, bv, POLICY["pressure_tolerance_kpa"])
        if av is not None and bv is not None and av*bv < 0:
            blockers.append("opposite_overbalance_regime")
    if risk == "STUCK_PIPE":
        compare("stationary exposure_h", number(a.get("stationary_exposure_h")), number(b.get("stationary_exposure_h")), POLICY["stationary_tolerance_h"])
        av, bv = number(a.get("permeability_md")), number(b.get("permeability_md"))
        compare("log10 permeability_md", math.log10(av) if av and av > 0 else None, math.log10(bv) if bv and bv > 0 else None, 1.)
    if risk in ("KICK", "MUD_LOSS"):
        compare("mud weight_sg", number(a.get("mud_weight_sg")), number(b.get("mud_weight_sg")), get_settings().mud_loss_policy.mud_weight_tolerance_sg if risk == "MUD_LOSS" else POLICY["mud_weight_tolerance_sg"])
    if risk == "KICK":
        compare("gas_pct", number(a.get("gas_pct")), number(b.get("gas_pct")), POLICY["gas_tolerance_pct"])
        compare("influx volume_m3", number(a.get("influx_volume_m3")), number(b.get("influx_volume_m3")), POLICY["influx_tolerance_m3"])
    return {"factor": factor, "comparisons": comparisons, "derived_inputs": derived, "depth_inputs": {"active_md_m": active_md, "offset_md_m": offset_md},
            "support": support, "penalties": penalties, "unknowns": unknowns, "blockers": blockers, "policy": POLICY}
