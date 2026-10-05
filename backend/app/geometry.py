"""Minimum curvature and bounded interpolation in a declared local metric CRS."""
import math

VERSION = "minimum-curvature/1.1"


def trajectory(stations, x0=0., y0=0.):
    if not stations or stations[0]["md_m"] != 0:
        raise ValueError("Survey must start at MD 0; local origin cannot be assumed mid-well")
    result = []
    x, y, z = x0, y0, 0.
    previous = None
    for station in stations:
        dogleg, severity = 0., 0.
        md, inc, azi = (station[k] for k in ("md_m", "incl_deg", "azi_deg"))
        if not all(math.isfinite(v) for v in (md, inc, azi)) or not 0 <= inc <= 180 or not 0 <= azi < 360:
            raise ValueError("Invalid survey angles or non-finite values")
        if previous:
            delta = md - previous["md_m"]
            if delta <= 0:
                raise ValueError("Survey MD must strictly increase")
            i1, a1, i2, a2 = map(math.radians, [previous["incl_deg"], previous["azi_deg"], inc, azi])
            dogleg = math.acos(max(-1., min(1., math.cos(i1)*math.cos(i2) + math.sin(i1)*math.sin(i2)*math.cos(a2-a1))))
            if dogleg >= math.pi - 1e-6:
                raise ValueError("Antipodal survey directions are ambiguous")
            ratio = 1. if dogleg < 1e-8 else 2*math.tan(dogleg/2)/dogleg
            severity = math.degrees(dogleg)*30/delta
            x += delta/2*(math.sin(i1)*math.sin(a1)+math.sin(i2)*math.sin(a2))*ratio
            y += delta/2*(math.sin(i1)*math.cos(a1)+math.sin(i2)*math.cos(a2))*ratio
            z += delta/2*(math.cos(i1)+math.cos(i2))*ratio
        result.append({**station, "x_m": x, "y_m": y, "tvd_m": z, "algorithm_version": VERSION,
                       "dogleg_angle_deg": math.degrees(dogleg), "dogleg_severity_deg_per_30m": severity})
        previous = station
    return result


def position(path, md):
    if not path or not path[0]["md_m"] <= md <= path[-1]["md_m"]:
        raise ValueError("Depth outside survey coverage")
    for a, b in zip(path, path[1:]):
        if a["md_m"] <= md <= b["md_m"]:
            t = (md-a["md_m"])/(b["md_m"]-a["md_m"])
            return {k: a[k]+t*(b[k]-a[k]) for k in ("x_m", "y_m", "tvd_m")}
    return {k: path[-1][k] for k in ("x_m", "y_m", "tvd_m")}


def separation(active_path, offset_path, active_interval, offset_interval, datum_uncertainty_m=0.):
    # Compare corresponding stratigraphic fractions, not arbitrary intersecting depths.
    distances = []
    for step in range(21):
        fraction = step/20
        a = position(active_path, active_interval[0]+fraction*(active_interval[1]-active_interval[0]))
        b = position(offset_path, offset_interval[0]+fraction*(offset_interval[1]-offset_interval[0]))
        distances.append(math.sqrt(sum((a[k]-b[k])**2 for k in ("x_m", "y_m", "tvd_m"))))
    if isinstance(datum_uncertainty_m, bool) or not math.isfinite(datum_uncertainty_m) or datum_uncertainty_m < 0:
        raise ValueError("Invalid datum uncertainty")
    nominal = sum(distances)/len(distances)
    return {"target_distance_m": round(nominal, 2), "datum_uncertainty_m": datum_uncertainty_m,
            "target_distance_interval_m": [round(max(0, nominal-datum_uncertainty_m), 2), round(nominal+datum_uncertainty_m, 2)],
            "minimum_distance_m": round(min(distances), 2), "samples": 21,
            "method": "mean separation at corresponding formation fractions", "algorithm_version": VERSION}


def inclination_at(stations, md):
    if md is None or not stations or md < stations[0]["md_m"] or md > stations[-1]["md_m"]:
        return None
    for first, second in zip(stations, stations[1:]):
        if first["md_m"] <= md <= second["md_m"]:
            fraction = (md-first["md_m"])/(second["md_m"]-first["md_m"])
            return first["incl_deg"]+fraction*(second["incl_deg"]-first["incl_deg"])
    return stations[-1]["incl_deg"]


def project_event(event, source, target, source_path=None, target_path=None):
    bounds = event.get("event_md_interval_m")
    if bounds:
        if len(bounds) != 2 or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in bounds) or not 0 <= bounds[0] <= bounds[1]:
            raise ValueError("Invalid event MD interval")
        endpoint_event = {k: v for k, v in event.items() if k != "event_md_interval_m"}
        endpoints = [project_event({**endpoint_event, "md_from_m": depth}, source, target, source_path, target_path) for depth in bounds]
        blocked = next((result for result in endpoints if result["decision"] == "BLOCKED"), None)
        result = dict(blocked or endpoints[0])
        if not blocked:
            result["projected_md_interval_m"] = [min(r["projected_md_interval_m"][0] for r in endpoints), max(r["projected_md_interval_m"][1] for r in endpoints)]
        result["inputs"] = {**result["inputs"], "event": event, "event_md_interval_m": bounds, "endpoint_projections": endpoints}
        return result
    inputs = {"event": event, "source": source, "target": target,
              "event_depth_m": event.get("md_from_m"), "source_path": source_path, "target_path": target_path}
    if source is None or event.get("md_from_m") is None:
        return {"decision": "BLOCKED", "reason": "source_or_event_depth_unknown", "projected_md_interval_m": None,
                "inputs": inputs, "algorithm_version": "formation-envelope/2.0"}
    if isinstance(event["md_from_m"], bool) or not math.isfinite(event["md_from_m"]) or event["md_from_m"] < 0:
        raise ValueError("Event depth must be finite and non-negative")
    for record in (event, source, target or {}):
        for key in ("uncertainty_m", "datum_uncertainty_m", "depth_uncertainty_m"):
            value = record.get(key, 0.)
            if value is None or isinstance(value, bool) or not math.isfinite(value) or value < 0:
                raise ValueError(f"Invalid {key}")
    result = _project_event(event, source, target, source_path, target_path)
    result.update(inputs=inputs, algorithm_version="formation-envelope/2.0")
    if result["decision"] == "PROJECTED":
        source_thickness = (source.get("base_md_m") or 0)-(source.get("top_md_m") or 0)
        target_thickness = (target.get("base_md_m") or 0)-(target.get("top_md_m") or 0)
        if source_thickness <= 0:
            source_thickness = source.get("approx_thickness_m", 0)
        if target_thickness <= 0:
            target_thickness = target.get("approx_thickness_m", 0)
        scale = target_thickness/source_thickness if source_thickness and target_thickness else 1.
        datum_margin = source.get("datum_uncertainty_m", 0)+target.get("datum_uncertainty_m", 0)+event.get("datum_uncertainty_m", 0)
        if result["method"] == "tvd_fallback":
            center = sum(result["projected_md_interval_m"])/2
            inclination = inclination_at(target_path, center)
            datum_margin /= max(.1, abs(math.cos(math.radians(inclination or 0))))
        depth_margin = event.get("depth_uncertainty_m", 0)*scale
        margin = datum_margin+depth_margin
        result["projected_md_interval_m"] = [round(result["projected_md_interval_m"][0]-margin, 2),
                                                round(result["projected_md_interval_m"][1]+margin, 2)]
        result["uncertainty_components"] = {"datum_margin_m": datum_margin, "event_depth_margin_m": depth_margin,
            "formation_top_base_included": True,
            "datum_uncertainty_status": "CONFIGURED" if "datum_uncertainty_m" in source and "datum_uncertainty_m" in target else "UNSPECIFIED",
            "assumption": "conservative independent bounded datum/depth errors; unspecified datum bounds are reported, not inferred; no datum transformation"}
    return result


def _project_event(event, source, target, source_path=None, target_path=None):
    if target is None:
        return {"decision": "BLOCKED", "reason": "formation_absent", "projected_md_interval_m": None}
    if source.get("datum") != target.get("datum"):
        return {"decision": "BLOCKED", "reason": "datum_mismatch", "projected_md_interval_m": None}
    if source.get("datum") in (None, "UNKNOWN"):
        return {"decision": "BLOCKED", "reason": "datum_unknown", "projected_md_interval_m": None}
    if event.get("review_status") == "QUARANTINED":
        return {"decision": "BLOCKED", "reason": "event_quarantined", "projected_md_interval_m": None}
    depth = event["md_from_m"]
    s_top, t_top = source.get("top_md_m"), target.get("top_md_m")
    s_base, t_base = source.get("base_md_m"), target.get("base_md_m")
    s_unc, t_unc = source.get("uncertainty_m", 0), target.get("uncertainty_m", 0)
    if None not in (s_top, t_top, s_base, t_base):
        if s_base <= s_top or t_base <= t_top:
            raise ValueError("Non-positive formation thickness")
        fraction = (depth-s_top)/(s_base-s_top)
        if not 0 <= fraction <= 1:
            return {"decision": "BLOCKED", "reason": "event_outside_source_formation", "projected_md_interval_m": None}
        # Conservative corner envelope includes top/base uncertainty for both wells.
        candidates = []
        for st in (s_top-s_unc, s_top+s_unc):
            for sb in (s_base-s_unc, s_base+s_unc):
                if sb <= st:
                    continue
                f = max(0., min(1., (depth-st)/(sb-st)))
                for tt in (t_top-t_unc, t_top+t_unc):
                    for tb in (t_base-t_unc, t_base+t_unc):
                        candidates.append(tt+f*(tb-tt))
        interval = [round(min(candidates), 2), round(max(candidates), 2)]
        return {"decision": "PROJECTED", "method": "formation_fraction", "strat_fraction": round(fraction, 5),
                "projected_md_interval_m": interval, "alignment_confidence": "moderate",
                "algorithm_version": "formation-envelope/1.0", "inputs": {"source": source, "target": target, "event_depth_m": depth}}
    source_thickness = s_base-s_top if s_base is not None and s_top is not None else source.get("approx_thickness_m")
    target_thickness = t_base-t_top if t_base is not None and t_top is not None else target.get("approx_thickness_m")
    if s_top is not None and t_top is not None and source_thickness and target_thickness:
        if source_thickness <= 0 or target_thickness <= 0:
            raise ValueError("Non-positive estimated formation thickness")
        f = (depth-s_top)/source_thickness
        if not 0 <= f <= 1:
            return {"decision": "BLOCKED", "reason": "event_outside_estimated_formation", "projected_md_interval_m": None}
        center = t_top+f*target_thickness
        uncertainty = max(80., s_unc+t_unc, .25*target_thickness)
        method = "estimated_thickness"
    elif source_path and target_path:
        tvd = position(source_path, depth)["tvd_m"]
        near = min(target_path, key=lambda point: abs(point["tvd_m"]-tvd))
        center, uncertainty, method = near["md_m"], 150.+s_unc+t_unc, "tvd_fallback"
    else:
        center, uncertainty, method = depth, 200.+s_unc+t_unc, "raw_md_last_resort"
    return {"decision": "PROJECTED", "method": method, "projected_md_interval_m": [center-uncertainty, center+uncertainty],
            "alignment_confidence": "low", "reasons": ["missing top/base; approximate alignment"],
            "algorithm_version": "formation-envelope/1.0"}
