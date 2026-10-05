"""Historical-evidence + fresh-channel mud-loss corroboration. No rig control path."""
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
from .evidence import evaluate
from .live import stamp, utc_now
from .config import get_settings

VERSION = "mud-loss-gates/2.0"
REQUIRED = ("bit_md_m", "operation_state", "flow_in_l_min", "flow_out_l_min", "pit_volume_m3", "ecd_sg")


def corroborate(context, evidence):
    POLICY = get_settings().mud_loss_policy.model_dump()
    channels = context["channels"]
    missing = [name for name in REQUIRED if channels[name]["quality_status"] != "FRESH"]
    now = stamp(context["timestamp"])
    usable = []
    for record in context["history"]:
        age = (now-stamp(record["timestamp"])).total_seconds()
        if 0 < age <= POLICY["trend_max_s"] and record.get("quality_status") == "VALID" and record["values"].get("operation_state") == "DRILLING":
            usable.append(record)
    usable.sort(key=lambda row: stamp(row["timestamp"]))
    current = {key: channels[key]["value"] for key in REQUIRED}
    def deficit(values):
        incoming, outgoing = values.get("flow_in_l_min"), values.get("flow_out_l_min")
        if not isinstance(incoming, (int, float)) or not isinstance(outgoing, (int, float)) or incoming <= 0: return False
        return incoming-outgoing >= max(POLICY["flow_deficit_min_l_min"], incoming*POLICY["flow_deficit_fraction"])
    flow_fresh = all(channels[key]["quality_status"] == "FRESH" for key in ("flow_in_l_min", "flow_out_l_min"))
    count = POLICY["flow_sustained_min_samples"]-1
    last = usable[-count:]
    duration = (now-stamp(last[0]["timestamp"])).total_seconds() if len(last) == count else 0
    # A gap larger than one freshness allowance cannot prove a sustained condition.
    sequence = [stamp(row["timestamp"]) for row in last]+[now]
    gap_ok = len(last) == count and all(0 < (b-a).total_seconds() <= POLICY["acquisition_gap_max_s"] for a, b in zip(sequence, sequence[1:]))
    observed_times = [stamp((row.get("channel_timestamps") or {}).get("flow_out_l_min") or row["timestamp"]) for row in last]
    if channels["flow_out_l_min"]["timestamp"]: observed_times.append(stamp(channels["flow_out_l_min"]["timestamp"]))
    distinct_measurements = len(observed_times) == count+1 and all(a < b for a, b in zip(observed_times, observed_times[1:])) and (observed_times[-1]-observed_times[0]).total_seconds() >= POLICY["flow_sustained_min_s"]
    sustained = flow_fresh and deficit(current) and len(last) == count and duration >= POLICY["flow_sustained_min_s"] and gap_ok and distinct_measurements and all(deficit(row["values"]) for row in last)
    pit_current = channels["pit_volume_m3"]
    pit_history = sorted([r for r in context["history"] if 0 < (now-stamp(r["timestamp"])).total_seconds() <= POLICY["trend_max_s"]], key=lambda r: stamp(r["timestamp"]))
    tail, endpoint = [], now
    for record in reversed(pit_history):
        at = stamp(record["timestamp"])
        if record.get("quality_status") != "VALID" or record["values"].get("operation_state") != "DRILLING" or not isinstance(record["values"].get("pit_volume_m3"), (int, float)) or not 0 < (endpoint-at).total_seconds() <= POLICY["acquisition_gap_max_s"]: break
        tail.insert(0, record); endpoint = at
    baseline = tail[0] if tail and (now-stamp(tail[0]["timestamp"])).total_seconds() >= POLICY["trend_min_s"] else None
    drop = baseline["values"]["pit_volume_m3"]-pit_current["value"] if baseline and pit_current["quality_status"] == "FRESH" else None
    # No long acquisition gaps, operation changes or quality gaps in the pit trend.
    trend = [r for r in context["history"] if baseline and stamp(r["timestamp"]) >= stamp(baseline["timestamp"])]
    times = [stamp(r["timestamp"]) for r in trend]+[now]
    continuity = bool(trend) and all(r.get("quality_status") == "VALID" and r["values"].get("operation_state") == "DRILLING" and r["values"].get("pit_volume_m3") is not None for r in trend) and all(0 < (b-a).total_seconds() <= POLICY["acquisition_gap_max_s"] for a, b in zip(times, times[1:]))
    falling = drop is not None and drop >= POLICY["pit_drop_min_m3"] and continuity
    depth = context["bit_md_m"]
    windows = [t["projection"]["projected_md_interval_m"] for r in evidence["rows"] if r["role"] == "SUPPORT" for t in r["transfers"] if t["event_id"] == r.get("selected_event_id")]
    approaching = depth is not None and any(start-POLICY["approach_distance_m"] <= depth <= end for start, end in windows)
    ahead = [(start-depth, end) for start, end in windows if depth is not None and depth <= end]
    distance = min((max(0, item[0]) for item in ahead), default=None)
    stage = "UNKNOWN" if depth is None else "PASSED" if windows and not ahead else "DISTANT" if distance is None or distance > POLICY["lesson_distance_m"] else "APPROACH" if approaching else "LOOKAHEAD"
    activated = evidence["state"] if approaching else "LESSON" if stage == "LOOKAHEAD" and evidence["state"] in ("LESSON", "ELEVATED") else "NO_EVIDENCE"
    gates = {"historical_elevated": evidence["state"] == "ELEVATED", "approaching_or_inside_event_window": approaching,
             "required_channels_fresh": not missing, "operation_drilling": context["operation_state"] == "DRILLING",
             "context_consistent": not context["context_conflict"], "flow_deficit_sustained": sustained, "pit_volume_falling": falling}
    allowed = all(gates.values())
    timestamps = [stamp(channels[key]["timestamp"]) for key in REQUIRED if channels[key]["quality_status"] == "FRESH"]
    gates["samples_time_coherent"] = len(timestamps) == len(REQUIRED) and (max(timestamps)-min(timestamps)).total_seconds() <= POLICY["sample_skew_max_s"]
    allowed = all(gates.values())
    flow_difference = channels["flow_in_l_min"]["value"]-channels["flow_out_l_min"]["value"] if flow_fresh else None
    ecd = channels["ecd_sg"]
    ecd_previous = baseline["values"].get("ecd_sg") if baseline else None
    mud = channels.get("mud_weight_sg", {})
    mud_value = mud.get("value") if mud.get("quality_status") == "FRESH" else None
    mud_previous = baseline["values"].get("mud_weight_sg") if baseline and continuity and all(row.get("channel_quality", {}).get("mud_weight_sg", "VALID") in ("VALID", "FRESH") for row in trend) else None
    return {"warning_allowed": allowed, "state": "WARNING" if allowed else activated, "gates": gates,
            "activation": {"stage": stage, "distance_to_event_m": distance, "historical_state": evidence["state"]},
            "mud_weight_sg": mud_value, "mud_weight_change_sg": mud_value-mud_previous if mud_value is not None and isinstance(mud_previous, (int, float)) else None,
            "missing_or_invalid_channels": missing, "flow_deficit_l_min": flow_difference, "pit_drop_m3": drop,
            "flow_duration_s": duration, "aligned_windows_m": windows, "ecd_sg": ecd["value"] if ecd["quality_status"] == "FRESH" else None,
            "ecd_change_sg": ecd["value"]-ecd_previous if ecd["quality_status"] == "FRESH" and isinstance(ecd_previous, (int, float)) else None,
            "policy": POLICY, "summary": "Fresh simulated signals corroborate historical concern" if allowed else "Warning gates not satisfied; inspect historical evidence and channel quality"}


def assess(store, well, session, context, history_cache=None):
    active = deepcopy(well)
    # Do not reinterpret missing telemetry as an observed programme match.
    active["mud_program"]["ecd_sg"] = context["channels"]["ecd_sg"]["value"] if context["channels"]["ecd_sg"]["quality_status"] == "FRESH" else None
    active["mud_program"]["hole_section_in"] = context["hole_section_in"]
    mud = context["channels"].get("mud_weight_sg", {})
    active["mud_program"]["mud_weight_sg"] = mud.get("value") if mud.get("quality_status") == "FRESH" else None
    active["pressure_context"]["mud_weight_sg"] = active["mud_program"]["mud_weight_sg"]
    active["operating_context"]["mud_weight_sg"] = active["mud_program"]["mud_weight_sg"]
    cache_key = (active["mud_program"]["ecd_sg"], active["mud_program"]["mud_weight_sg"], active["mud_program"]["hole_section_in"], context["operation_state"])
    history = history_cache.get(cache_key) if history_cache is not None else None
    if history is None:
        history = evaluate(store, active, session["formation"], "MUD_LOSS", session["md_interval_m"], session["radius_km"],
                           context["operation_state"], context_source=f"Canonical {context['source']} context under {context['clock']} clock; simulation only")
        if history_cache is not None: history_cache[cache_key] = history
    live = corroborate(context, history)
    lessons = []
    for row in history["rows"]:
        if row["role"] != "SUPPORT": continue
        selected = next(t for t in row["transfers"] if t["event_id"] == row["selected_event_id"])
        event = selected["inputs"]["event"]
        lessons.append({"well_id": row["well_id"], "event_id": event["id"], "mitigation": event.get("mitigation"),
                        "outcome": event.get("outcome"), "source": selected["source"], "document_id": event["document_id"],
                        "severity": event.get("severity", "UNKNOWN"), "event_md_interval_m": event.get("event_md_interval_m"), "mud_context": event.get("context_values", {}),
                        "language": "Historical response only. Review the source and approved programme; do not copy operating parameters."})
    return {"historical": history, "corroboration": live, "context": context, "lessons": lessons,
            "recommendation": "Verify returns and instrument quality. Review comparable historical responses and the approved pressure window with the drilling team. Prepare only approved contingencies.",
            "policy_version": VERSION, "simulation": True}


def fingerprint(evidence):
    items = []
    for row in evidence["rows"]:
        selected = next((t for t in row["transfers"] if t["event_id"] == row.get("selected_event_id")), None)
        event = selected["inputs"]["event"] if selected else {}
        items.append((row["well_id"], row["role"], row.get("selected_event_id"),
                      (row.get("clean_source") or {}).get("coverage_id"), event.get("md_from_m"),
                      event.get("review_status"), event.get("mitigation"), event.get("outcome"), event.get("severity"), event.get("event_md_interval_m"), event.get("context_values"),
                      selected["projection"]["projected_md_interval_m"] if selected else None))
    return hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()[:16]


def audit_alert(store, alert, event, actor="ENGINE", notify=False):
    index = len(alert["history"])+1
    entry = {"id": f"{alert['id']}-{index}", "event": event, "actor": actor, "timestamp": utc_now().isoformat(),
             "simulation_timestamp": alert.get("context_timestamp"), "notified": notify}
    alert["history"].append(entry)
    if notify: alert["notification_count"] += 1
    store.put("alert_audit", {**entry, "alert_id": alert["id"]})


def sync_alert(store, session, assessment):
    key = f"{session['well_id']}|MUD_LOSS|{session['formation']}|{[float(v) for v in session['md_interval_m']]}"
    alert_id = "ALERT-"+hashlib.sha256(key.encode()).hexdigest()[:20]
    # Retire persisted legacy run-scoped alerts before creating the well-scoped record.
    for legacy in store.all("alert"):
        if legacy["id"] != alert_id and legacy["well_id"] == session["well_id"] and legacy["formation"] == session["formation"] and legacy["md_interval_m"] == session["md_interval_m"] and legacy["lifecycle"] != "RESOLVED":
            legacy.update(lifecycle="RESOLVED", resolved_at=utc_now().isoformat(), superseded_by=alert_id)
            audit_alert(store, legacy, "well_interval_dedup_migration")
            store.put("alert", legacy)
    alert = store.get("alert", alert_id)
    historical = assessment["historical"]; state = assessment["corroboration"]["state"]
    now = stamp(assessment["context"]["timestamp"])
    depth = assessment["context"]["bit_md_m"]
    passed = depth is not None and depth > session["md_interval_m"][1]
    eligible = state in ("LESSON", "ELEVATED", "WARNING") and not passed
    if alert and alert.get("restart_pending") and eligible:
        alert.update(restart_pending=False, lifecycle="CREATED", evidence_state=state, peak_state=state,
                     resolved_at=None, snoozed_until=None, session_id=session["id"], context_timestamp=now.isoformat())
        audit_alert(store, alert, "episode_restarted", notify=True)
    if alert:
        alert["session_ids"] = sorted(set(alert.get("session_ids", [alert["session_id"]])) | {session["id"]})
        if not alert.get("restart_pending") and now < stamp(alert.get("context_timestamp", now.isoformat())):
            store.put("alert", alert)
            return alert
    if not alert and not eligible: return None
    if not alert:
        alert = {"id": alert_id, "session_id": session["id"], "well_id": session["well_id"], "risk_type": "MUD_LOSS",
                 "formation": session["formation"], "md_interval_m": session["md_interval_m"], "simulation": True,
                 "lifecycle": "CREATED", "evidence_state": state, "peak_state": state, "history": [], "notification_count": 0,
                 "created_at": utc_now().isoformat(), "snoozed_until": None, "resolved_at": None,
                 "evidence_fingerprint": fingerprint(historical)}
        alert["session_ids"] = [session["id"]]
        alert["context_timestamp"] = now.isoformat()
        audit_alert(store, alert, "created", notify=True)
    elif alert["lifecycle"] == "RESOLVED":
        # Manual/automatic resolution is latched for this fixed session interval.
        store.put("alert", alert)
        return alert
    else:
        alert["session_ids"] = sorted(set(alert.get("session_ids", [alert["session_id"]])) | {session["id"]})
        alert["session_id"] = session["id"]
        alert["context_timestamp"] = now.isoformat()
        old_state = alert["evidence_state"]
        alert["evidence_state"] = state
        ranks = {"NO_EVIDENCE": 0, "INSUFFICIENT_EVIDENCE": 0, "LESSON": 1, "ELEVATED": 2, "WARNING": 3}
        escalation = ranks[state] > ranks[alert["peak_state"]]
        expired = alert["lifecycle"] == "SNOOZED" and now >= stamp(alert["snoozed_until"])
        changed = fingerprint(historical) != alert["evidence_fingerprint"]
        if passed:
            alert["lifecycle"] = "RESOLVED"; alert["resolved_at"] = utc_now().isoformat(); alert["snoozed_until"] = None
            audit_alert(store, alert, "interval_passed")
        elif escalation:
            alert["peak_state"] = state; alert["lifecycle"] = "ESCALATED"; alert["snoozed_until"] = None
            audit_alert(store, alert, "escalated", notify=True)
        elif expired:
            alert["lifecycle"] = "CREATED"; alert["snoozed_until"] = None
            audit_alert(store, alert, "snooze_expired", notify=eligible)
        elif changed:
            audit_alert(store, alert, "evidence_changed", notify=eligible and alert["lifecycle"] != "SNOOZED")
        elif old_state != state:
            audit_alert(store, alert, "corroboration_changed")
        alert["evidence_fingerprint"] = fingerprint(historical)
    alert.update({"evidence_snapshot_id": historical["id"], "evidence_sentence": historical["sentence"],
                  "corroboration": assessment["corroboration"], "lessons": assessment["lessons"],
                  "recommendation": assessment["recommendation"], "updated_at": utc_now().isoformat()})
    store.put("alert", alert)
    return alert


def transition_alert(store, alert, action, actor, now, snooze_seconds=60):
    if alert["lifecycle"] == "RESOLVED": raise ValueError("Resolved alert cannot be changed; explicitly reset the simulation episode")
    if action == "acknowledge":
        if alert["lifecycle"] == "ACKNOWLEDGED": return alert
        alert["lifecycle"] = "ACKNOWLEDGED"; alert["snoozed_until"] = None
    elif action == "snooze":
        alert["lifecycle"] = "SNOOZED"; alert["snoozed_until"] = (now+timedelta(seconds=snooze_seconds)).isoformat()
    elif action == "resolve":
        alert["lifecycle"] = "RESOLVED"; alert["resolved_at"] = utc_now().isoformat(); alert["snoozed_until"] = None
    else: raise ValueError("Unsupported alert transition")
    alert["context_timestamp"] = now.isoformat()
    audit_alert(store, alert, action, actor=actor)
    store.put("alert", alert)
    return alert
