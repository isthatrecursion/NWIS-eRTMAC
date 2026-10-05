"""Transparent secondary indicators. Historical support is not a risk classifier."""
from copy import deepcopy
import math
from statistics import median
from .evidence import evaluate
from .live import stamp

VERSION = "secondary-support/1.0"
MATURITY = {"MUD_LOSS": "POLISHED_SIMULATION_SLICE", "STUCK_PIPE": "PARTIAL_DECISION_SUPPORT",
            "KICK": "CONSERVATIVE_INDICATORS", "TORQUE_DYSFUNCTION": "SUPPORTING_INDICATORS", "CEMENTING_ISSUE": "HISTORICAL_PLANNING_ONLY"}
POLICY = {"version": VERSION, "baseline_min_s": 30, "baseline_max_s": 120, "baseline_min_samples": 3,
          "gap_max_s": 30, "stationary_depth_tolerance_m": .5, "torque_change_fraction": .2,
          "hookload_deviation_fraction": .15, "spp_change_fraction": .15,
          "pit_gain_min_m3": .5, "flow_excess_min_l_min": 30, "flow_excess_fraction": .05,
          "gas_rise_min_pct": 1., "basis": "Uncalibrated, transparent synthetic supporting indicators"}


def fresh(context, key):
    channel = context["channels"].get(key, {})
    value = channel.get("value")
    return value if channel.get("quality_status") == "FRESH" and isinstance(value, (int, float)) and not isinstance(value, bool) else None


def history(context, keys, operation=None):
    """A contiguous, channel-specific, same-operation acquisition window."""
    now = stamp(context["timestamp"])
    tail, endpoint = [], now
    for row in sorted(context.get("history", []), key=lambda r: stamp(r["timestamp"]), reverse=True):
        at = stamp(row["timestamp"])
        if (now-at).total_seconds() > POLICY["baseline_max_s"]: break
        values, qualities = row["values"], row.get("channel_quality", {})
        if not 0 < (endpoint-at).total_seconds() <= POLICY["gap_max_s"]: break
        if qualities.get("operation_state", "VALID") not in ("VALID", "FRESH") or (not qualities and row.get("quality_status") != "VALID"): break
        if values.get("operation_state") != (operation or context["operation_state"]): break
        if any(qualities.get(k, "VALID") not in ("VALID", "FRESH") or not isinstance(values.get(k), (float, int)) for k in keys): break
        if any((row.get("channel_timestamps") or {}).get(k) and abs((at-stamp(row["channel_timestamps"][k])).total_seconds()) > context["channels"].get(k, {}).get("freshness_threshold_s", 30) for k in keys): break
        tail.insert(0, row); endpoint = at
    if len(tail) < POLICY["baseline_min_samples"] or not tail or (now-stamp(tail[0]["timestamp"])).total_seconds() < POLICY["baseline_min_s"]: return []
    for key in keys:
        times = [stamp(row.get("channel_timestamps", {}).get(key) or row["timestamp"]) for row in tail]
        if not all(a < b for a, b in zip(times, times[1:])): return []
    return tail


def trend(context, key, threshold=None, fraction=False, absolute=False):
    current = fresh(context, key)
    rows = history(context, [key]) if current is not None else []
    baseline = median(row["values"][key] for row in rows) if rows else None
    delta = current-baseline if baseline is not None else None
    change = delta/abs(baseline) if delta is not None and baseline else None
    test = change if fraction else delta
    return {"name": key, "value": current, "baseline": baseline, "change": delta, "fraction_change": change,
            "available": delta is not None, "triggered": (abs(test) if absolute else test) >= threshold if test is not None and threshold is not None else False,
            "threshold": threshold, "sample_count": len(rows), "baseline_method": "median of contiguous same-operation samples",
            "source_timestamps": [row["timestamp"] for row in rows], "provenance_type": "COMPUTED"}


def module(store, well, session, context, risk):
    active = deepcopy(well)
    for key in ("mud_weight_sg", "ecd_sg"):
        value = fresh(context, key)
        active["mud_program"][key] = value
        for name in ("pressure_context", "operating_context"): active.setdefault(name, {})[key] = value
    operation = "CEMENTING" if risk == "CEMENTING_ISSUE" else context["operation_state"]
    evidence = evaluate(store, active, session["formation"], risk, session["md_interval_m"], session["radius_km"], operation,
                        context_source="Historical planning context" if risk == "CEMENTING_ISSUE" else "Observed operation and fresh simulated mud context")
    indicators, limitations = [], []
    allowed = {"STUCK_PIPE": {"DRILLING", "REAMING", "TRIPPING", "TRIPPING_IN", "TRIPPING_OUT", "STATIC", "CONNECTION"},
               "KICK": {"DRILLING", "CIRCULATING"}, "TORQUE_DYSFUNCTION": {"DRILLING", "REAMING"}, "CEMENTING_ISSUE": {"CEMENTING"}}
    bound = operation in allowed[risk] and (risk == "CEMENTING_ISSUE" or context["channels"]["operation_state"]["quality_status"] == "FRESH")
    if risk == "STUCK_PIPE":
        indicators = [trend(context, "torque_kn_m", POLICY["torque_change_fraction"], True),
                      trend(context, "hookload_kn", POLICY["hookload_deviation_fraction"], True, True),
                      trend(context, "standpipe_pressure_kpa", POLICY["spp_change_fraction"], True)]
        rows = history(context, ["bit_md_m"])
        duration = 0.
        depth = fresh(context, "bit_md_m")
        if depth is not None:
            for row in reversed(rows):
                if abs(row["values"]["bit_md_m"]-depth) > POLICY["stationary_depth_tolerance_m"]: break
                duration = (stamp(context["timestamp"])-stamp(row["timestamp"])).total_seconds()
        indicators.append({"name": "stationary_duration_s", "value": duration if rows else None, "available": bool(rows), "triggered": duration >= POLICY["baseline_min_s"], "provenance_type": "COMPUTED", "interpretation": "Depth stationary within tolerance; pipe motion and downhole exposure are not measured"})
        limitations = ["Partial decision support; no stuck-pipe prediction accuracy claim", "Torque/hookload/SPP baselines are local observed references, not mechanical models", "Depth stationarity does not prove stationary pipe exposure"]
        limitations.append(f"Stationary duration is observed within the last {POLICY['baseline_max_s']} seconds; longer exposure is not measured")
    elif risk == "KICK":
        pit, gas = trend(context, "pit_volume_m3", POLICY["pit_gain_min_m3"]), trend(context, "gas_pct", POLICY["gas_rise_min_pct"])
        # Net volume uses the oldest valid observation, not the median.
        rows = history(context, ["pit_volume_m3"])
        if rows and fresh(context, "pit_volume_m3") is not None:
            pit.update(baseline=rows[0]["values"]["pit_volume_m3"], change=fresh(context, "pit_volume_m3")-rows[0]["values"]["pit_volume_m3"])
            pit["triggered"] = pit["change"] >= POLICY["pit_gain_min_m3"]
        incoming, outgoing = fresh(context, "flow_in_l_min"), fresh(context, "flow_out_l_min")
        coherent = all(context["channels"].get(k, {}).get("quality_status") == "FRESH" for k in ("flow_in_l_min", "flow_out_l_min", "pit_volume_m3", "gas_pct", "mud_weight_sg"))
        times = [stamp(context["channels"][k]["timestamp"]) for k in ("flow_in_l_min", "flow_out_l_min", "pit_volume_m3", "gas_pct", "mud_weight_sg") if context["channels"].get(k, {}).get("timestamp")]
        coherent = coherent and len(times) == 5 and (max(times)-min(times)).total_seconds() <= 10
        excess = outgoing-incoming if incoming is not None and outgoing is not None else None
        flow_rows = history(context, ["flow_in_l_min", "flow_out_l_min"])
        sustained = bool(flow_rows) and all(row["values"]["flow_out_l_min"]-row["values"]["flow_in_l_min"] >= max(POLICY["flow_excess_min_l_min"], row["values"]["flow_in_l_min"]*POLICY["flow_excess_fraction"]) for row in flow_rows[-2:])
        indicators = [pit, {"name": "flow_out_excess_l_min", "value": excess, "available": excess is not None,
            "triggered": excess is not None and incoming > 0 and excess >= max(POLICY["flow_excess_min_l_min"], incoming*POLICY["flow_excess_fraction"]) and sustained, "provenance_type": "COMPUTED"}, gas]
        bound = bound and coherent
        limitations = ["Conservative kick/influx indicators, not a black-box classifier or calibrated overpressure prediction", "Transfers and sensor transients can produce pit gain/excess returns/gas rise", "Pressure context is historical/programme context unless measured; approved well-control procedures remain authoritative"]
    elif risk == "TORQUE_DYSFUNCTION":
        torque = trend(context, "torque_kn_m", POLICY["torque_change_fraction"], True, True)
        torque["name"] = "torque_residual_kn_m"
        torque["value"] = torque["change"]
        indicators = [torque, trend(context, "wob_kn"), trend(context, "rpm"), trend(context, "rop_m_h")]
        wob, rpm, torque_value, rop = (fresh(context, k) for k in ("wob_kn", "rpm", "torque_kn_m", "rop_m_h"))
        hole = fresh(context, "hole_section_in")
        mse = None
        if all(v is not None for v in (wob, rpm, torque_value, rop, hole)) and rop > 0 and hole > 0:
            area = math.pi*(hole*.0254)**2/4
            mse = (wob*1000/area+120*math.pi*torque_value*1000*rpm/(area*rop))/1e6
        indicators.append({"name": "mse_mpa", "value": mse, "available": mse is not None, "triggered": False, "provenance_type": "COMPUTED", "inputs": {"wob_kn": wob, "rpm": rpm, "torque_kn_m": torque_value, "rop_m_h": rop, "hole_section_in": hole}, "formula": "WOB/area + 120*pi*torque*RPM/(area*ROP); SI inputs, ROP m/h", "interpretation": "Optional mechanical specific energy; never a standalone stuck-pipe predictor"})
        limitations = ["Torque residual is deviation from an observed baseline, not a fitted torque model", "ROP/WOB/RPM changes provide context; MSE is not a standalone stuck-pipe predictor"]
    else:
        limitations = ["Historical planning intelligence only; no real-time cementing model"]
    lessons = []
    for row in evidence["rows"]:
        if row["role"] != "SUPPORT": continue
        selected = next(t for t in row["transfers"] if t["event_id"] == row["selected_event_id"])
        event = selected["inputs"]["event"]
        offset = store.get("well", row["well_id"])
        doc = store.get("document", event["document_id"])
        shoes = sorted(offset.get("casing_program", []), key=lambda casing: casing["setting_md_m"])
        prior = 0
        casing_interval = None
        for shoe in shoes:
            if event.get("md_from_m") is not None and prior <= event["md_from_m"] <= shoe["setting_md_m"]:
                casing_interval = {"md_interval_m": [prior, shoe["setting_md_m"]], "size_in": shoe["size_in"], "provenance_type": "INFERRED", "basis": "Stored casing programme; not an extracted cement-job interval"}
                break
            prior = shoe["setting_md_m"]
        lessons.append({"event_id": event["id"], "well_id": offset["id"], "document_id": event["document_id"],
            "source_span_id": event["source_span_id"], "source": selected["source"], "mitigation": event.get("mitigation"), "outcome": event.get("outcome"),
            "casing_program": offset.get("casing_program", []), "casing_interval": casing_interval,
            "job_record": {"report_type": doc["doc_type"], "event_date": event.get("event_date"), "formation_id": event["formation_id"], "event_md_interval_m": event.get("event_md_interval_m"), "job_md_interval_m": None, "problem": event.get("symptom") or selected["source"]["text"], "remedial_action": event.get("mitigation"), "outcome": event.get("outcome"), "source_span_id": event["source_span_id"]} if risk == "CEMENTING_ISSUE" else None, "mud_context": event.get("context_values", {}), "provenance_type": "FACT"})
    signal = bound and not context.get("context_conflict") and any(i.get("triggered") for i in indicators)
    if risk == "KICK": signal = bound and not context.get("context_conflict") and all(i.get("triggered") for i in indicators)
    status = "HISTORICAL_PLANNING" if risk == "CEMENTING_ISSUE" else "CORROBORATING_INDICATORS" if signal and evidence["support_count"] else "SIGNALS_FOR_REVIEW" if signal else "CONTEXT_ONLY"
    return {"risk_type": risk, "maturity": MATURITY[risk], "status": status, "warning_allowed": False,
            "historical": evidence, "operation_state": operation, "operation_bound": bound, "indicators": indicators,
            "lessons": lessons, "formation_context": {"current": context["formation_id"], "target": session["formation"], "inclination_deg": context["inclination_deg"]},
            "pressure_context": well.get("pressure_context", {}), "mud_weight_sg": fresh(context, "mud_weight_sg"),
            "limitations": limitations, "policy": POLICY, "simulation": True, "algorithm_version": VERSION}
