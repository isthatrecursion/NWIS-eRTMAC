"""Versioned prototype policies. No latent truth, live signals or calibrated probability."""
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from .geometry import project_event, separation, trajectory
from .transfer_context import compare_context
from .config import get_settings

VERSION = "analog-evidence/2.1"
RISKS = ("MUD_LOSS", "STUCK_PIPE", "KICK", "TORQUE_DYSFUNCTION", "CEMENTING_ISSUE")


def formation(well, name):
    return next((f for f in well.get("formations", []) if f["formation_id"] == name), None)


def path(well):
    return trajectory(well["survey"], well["x_m"], well["y_m"])


def snapshot(store, kind, result):
    # Hash the complete input-derived result; subsequent reviews create a new snapshot.
    key = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()[:20]
    result = {**result, "id": f"{kind.upper()}-{key}", "computed_at": datetime.now(timezone.utc).isoformat()}
    store.put(kind, result)
    return result


def candidate(active, offset, name, radius):
    supports, penalties, unknowns, blockers = [], [], [], []
    distance = math.hypot(offset["x_m"]-active["x_m"], offset["y_m"]-active["y_m"])/1000
    source, target = formation(offset, name), formation(active, name)
    geometry = None
    if distance > radius: blockers.append("outside_surface_radius")
    if not source or not target: blockers.append("formation_absent")
    else: supports.append("same formation")
    if offset.get("crs") != active.get("crs") or offset.get("datum") != active.get("datum"):
        blockers.append("coordinate_reference_mismatch")
    trusted = all(w.get("structural_quality") in ("TRUSTED", "SYNTHETIC_TRUSTED") and w.get("structural_domain") for w in (active, offset))
    structural = 1.
    if trusted:
        if active["structural_domain"] != offset["structural_domain"]: blockers.append("trusted_structural_domain_mismatch")
        else: supports.append("same trusted structural domain")
    else:
        unknowns.append("no reliable structural-domain comparison"); structural = .7
    if not blockers and source and target:
        if source.get("base_md_m") is not None and target.get("base_md_m") is not None:
            try:
                geometry = separation(path(active), path(offset), [target["top_md_m"], target["base_md_m"]], [source["top_md_m"], source["base_md_m"]],
                    active.get("datum_uncertainty_m", 0)+offset.get("datum_uncertainty_m", 0)+target.get("datum_uncertainty_m", 0)+source.get("datum_uncertainty_m", 0))
                supports.append(f"{geometry['target_distance_m']:.0f} m target-interval mean separation")
            except (ValueError, KeyError) as exc: blockers.append(f"invalid_geometry: {exc}")
        else: unknowns.append("incomplete formation interval; surface distance is a fallback")
    spatial = 1/(1+(geometry["target_distance_interval_m"][1]/1000 if geometry else distance))
    if geometry is None: spatial *= .5
    comparison = compare_context(active, offset, formation_id=name)
    for key, destination in (("support", supports), ("penalties", penalties), ("unknowns", unknowns), ("blockers", blockers)):
        destination.extend(comparison[key])
    weight = spatial*structural*comparison["factor"] if not blockers else 0.
    return {"well_id": offset["id"], "surface_distance_km": round(distance, 4), "geometry": geometry,
            "decision": "EXCLUDED" if blockers else "CANDIDATE", "relevance": round(weight, 6),
            "support": supports, "penalties": penalties, "unknowns": unknowns, "blockers": blockers,
            "cascade": ["surface_radius", "formation", "geometry", "trusted_structure", "context", "source_quality"],
            "context_comparisons": comparison}


def context_policy(active, offset, risk, operation, source_operation, event=None, projection=None, formation_id=None):
    loss_policy = get_settings().mud_loss_policy
    support, penalties, unknowns, blockers = [], [], [], []
    weight = 1.
    a, b = active.get("mud_program", {}), {**offset.get("mud_program", {}), **((event or {}).get("context_values", {}))}
    for key in ("hole_section_in", "mud_system", "ecd_sg"):
        av, bv = a.get(key), b.get(key)
        if av is None or bv is None:
            unknowns.append(f"missing {key}"); weight *= .3 if key == "ecd_sg" else .4 if key == "mud_system" else .6
        elif key == "hole_section_in":
            if abs(av-bv) > loss_policy.hole_section_tolerance_in: blockers.append("incompatible_hole_section")
            else: support.append("similar hole section")
        elif key == "mud_system":
            if av != bv: penalties.append("mud system differs"); weight *= .5
            else: support.append("same mud system")
        elif risk == "MUD_LOSS":
            delta = abs(av-bv)
            if delta > loss_policy.ecd_max_difference_sg: blockers.append("strongly_different_ecd")
            else:
                weight *= max(loss_policy.ecd_weight_floor, 1-delta/loss_policy.ecd_weight_scale_sg)
                (support if delta <= loss_policy.ecd_similar_difference_sg else penalties).append(f"ECD difference {delta:.3f} sg")
        else:
            # Do not reuse loss ECD direction for kick or stuck-pipe mechanisms.
            unknowns.append("ECD direction not modeled for this risk"); weight *= .7
    if source_operation in (None, "UNKNOWN") or operation == "UNKNOWN":
        unknowns.append("operation state unknown"); weight *= .6
    elif source_operation != operation:
        blockers.append("incompatible_operation_state")
    else: support.append(f"same operation: {operation}")
    comparison = compare_context(active, offset, risk, event, projection, formation_id, include_common=False)
    # Candidate comparisons cover well-level pressure/era; event context compares
    # those observations at the event depth as well as risk-specific exposure.
    weight *= comparison["factor"]
    for key, destination in (("support", support), ("penalties", penalties), ("unknowns", unknowns), ("blockers", blockers)):
        destination.extend(comparison[key])
    if risk == "CEMENTING_ISSUE":
        unknowns.append("cement programme and placement conditions not modeled"); weight *= .4
    return {"factor": weight, "support": support, "penalties": penalties, "unknowns": unknowns, "blockers": blockers,
            "comparisons": comparison}


def transfer(active, offset, event, radius=3., operation="DRILLING"):
    POLICY = get_settings().historical_policy.model_dump()
    row = candidate(active, offset, event.get("formation_id"), radius)
    row = {**row, "event_id": event["id"], "source_span_id": event.get("source_span_id"),
           "document_id": event.get("document_id"), "event_type": event["event_type"], "policy_version": VERSION}
    projection = None
    if event["event_type"] not in RISKS: row["blockers"].append("risk_policy_not_implemented")
    source, target = formation(offset, event.get("formation_id")), formation(active, event.get("formation_id"))
    if event.get("review_status") in ("QUARANTINED", "NEEDS_REVIEW"):
        row["blockers"].append("event_requires_review_or_quarantined")
    if event.get("md_from_m") is None: row["blockers"].append("event_depth_unknown")
    if not source or event.get("datum") != source.get("datum") or event.get("datum") == "UNKNOWN":
        row["blockers"].append("event_datum_unknown_or_mismatched")
    if not row["blockers"]:
        try: projection = project_event(event, source, target, path(offset), path(active))
        except (ValueError, KeyError) as exc: row["blockers"].append(f"alignment_invalid: {exc}")
        if projection and projection["decision"] == "BLOCKED": row["blockers"].append(projection["reason"])
    context = context_policy(active, offset, event["event_type"], operation, event.get("operation_state"), event, projection, event.get("formation_id"))
    for key in ("support", "penalties", "unknowns", "blockers"): row[key].extend(context[key])
    alignment = .8 if projection and projection.get("alignment_confidence") == "moderate" else .35
    if projection and alignment == .35: row["penalties"].append("low-confidence alignment fallback")
    quality = max(0., min(1., event.get("confidence", 0.)))
    if quality < .85: row["penalties"].append("poor extraction confidence")
    if event.get("review_status") != "VERIFIED": quality *= .8; row["penalties"].append("source event not human verified")
    if not event.get("source_span_id"): row["blockers"].append("source_provenance_missing")
    weight = row["relevance"]*alignment*context["factor"]*quality if not row["blockers"] else 0.
    row.update({"weight": round(weight, 6), "decision": "INCLUDED" if weight >= POLICY["minimum_weight"] else "EXCLUDED",
                "projection": projection, "factors": {"well_relevance": row["relevance"], "alignment": alignment,
                "preconditions": context["factor"], "source_quality": quality}, "provenance_type": "INFERRED",
                "inputs": {"event": event, "active_programme": active.get("mud_program"), "offset_programme": offset.get("mud_program"),
                           "operation_state": operation, "source_formation": source, "target_formation": target},
                "context_comparisons": context["comparisons"]})
    row["mud_context_provenance"] = {key: "FACT_EXTRACTED_EVENT" if key in event.get("context_values", {}) else "STORED_PROGRAMME_FALLBACK" if offset.get("mud_program", {}).get(key) is not None else "UNKNOWN" for key in ("mud_weight_sg", "ecd_sg", "mud_system", "hole_section_in")}
    if not row["blockers"] and row["decision"] == "EXCLUDED": row["penalties"].append("below minimum transferability weight")
    return row


def active_records(store, kind):
    documents = {d["id"] for d in store.all("document") if not d.get("superseded_by") and d.get("review_status") != "QUARANTINED"
                 and (d.get("well_identity_confirmed") or not any(not row["matches_associated_well"] for row in d.get("well_identity", [])))}
    return [r for r in store.all(kind) if r["document_id"] in documents]


def clean_evidence(store, active, offset, name, risk, interval, radius, operation):
    POLICY = get_settings().historical_policy.model_dump()
    """Require verified coverage of the reverse-projected *uncertainty envelope* and explicit risk negation."""
    source, target = formation(offset, name), formation(active, name)
    if not source or not target: return None
    bounds = []
    for depth in interval:
        try:
            result = project_event({"md_from_m": depth}, target, source, path(active), path(offset))
        except (ValueError, KeyError): return None
        if result["decision"] != "PROJECTED" or result.get("method") != "formation_fraction": return None
        bounds.extend(result["projected_md_interval_m"])
    required = [min(bounds), max(bounds)]
    phrases = {"MUD_LOSS": r"No\s*mud\s*loss\s*observed\s*during\s*the\s*covered\s*drilling\s*interval",
               "STUCK_PIPE": r"No\s*stuck\s*pipe\s*observed\s*during\s*the\s*covered\s*drilling\s*interval",
               "KICK": r"No\s*kick\s*observed\s*during\s*the\s*covered\s*drilling\s*interval",
               "TORQUE_DYSFUNCTION": r"No\s*torque\s*dysfunction\s*observed\s*during\s*the\s*covered\s*drilling\s*interval",
               "CEMENTING_ISSUE": r"No\s*cementing\s*failure\s*observed\s*during\s*the\s*covered\s*cementing\s*interval"}
    for coverage in active_records(store, "coverage"):
        span = coverage.get("md_interval")
        if coverage["well_id"] != offset["id"] or coverage["coverage_status"] != "VERIFIED" or not span: continue
        if coverage.get("datum") != source.get("datum") or not span[0] <= required[0] <= required[1] <= span[1]: continue
        doc = store.get("document", coverage["document_id"])
        page = doc["page_data"][coverage["page"]-1]
        match = re.search(phrases[risk], page["text"], re.I)
        op = re.search(r"Operation\s*:\s*(\w+)", page["text"], re.I)
        context = context_policy(active, offset, risk, operation, op.group(1).upper() if op else "UNKNOWN", formation_id=name)
        analog = candidate(active, offset, name, radius)
        if not match or context["blockers"] or analog["blockers"]: continue
        weight = analog["relevance"]*.8*context["factor"]*page.get("confidence", 0.)
        if weight < POLICY["minimum_weight"]: continue
        return {"coverage_id": coverage["id"], "document_id": doc["id"], "page": coverage["page"],
                "source_text": match.group(0), "source_char_interval": [match.start(), match.end()],
                "required_source_interval_m": required, "weight": round(weight, 6), "context": context}
    return None


def aggregate(rows):
    POLICY = get_settings().historical_policy.model_dump()
    usable = [r for r in rows if r["role"] in ("SUPPORT", "COUNTER")]
    support = sum(r["role"] == "SUPPORT" for r in rows)
    counter = sum(r["role"] == "COUNTER" for r in rows)
    total = sum(r["weight"] for r in usable)
    squares = sum(r["weight"]**2 for r in usable)
    n_eff = total**2/squares if squares else 0.
    positive = sum(r["weight"] for r in usable if r["role"] == "SUPPORT")
    p_hat = (positive+POLICY["alpha"])/(total+POLICY["alpha"]+POLICY["beta"]) if usable else None
    state = "NO_EVIDENCE" if not usable else "INSUFFICIENT_EVIDENCE" if not support else "LESSON"
    if support >= POLICY["elevated_min_support"] and n_eff >= POLICY["elevated_min_n_eff"] and p_hat >= POLICY["elevated_min_p_hat"]:
        state = "ELEVATED"
    return {"state": state, "support_count": support, "counter_count": counter,
            "unknown_count": sum(r["role"] == "UNKNOWN" for r in rows), "excluded_count": sum(r["role"] == "EXCLUDED" for r in rows),
            "usable_wells": len(usable), "internal_statistics": {"p_hat": p_hat, "n_eff": n_eff, "sum_weights": total},
            "sentence": f"{support} supporting wells, {counter} verified clean crossings, and {sum(r['role']=='UNKNOWN' for r in rows)} wells with unknown interval evidence.",
            "warning_allowed": False, "policy": POLICY}


def evaluate(store, active, name, risk, interval, radius=3., operation="DRILLING", context_source="Explicit planning request and stored well programmes; not live telemetry"):
    rows = []
    events = active_records(store, "event")
    for offset in store.all("well"):
        if offset["id"] == active["id"] or offset.get("held_out"): continue
        analog = candidate(active, offset, name, radius)
        if analog["surface_distance_km"] > radius: continue
        historical = [e for e in events if e["well_id"] == offset["id"] and e["event_type"] == risk and e.get("formation_id") in (name, None)]
        transfers = [{**transfer(active, offset, e, radius, operation), "source": store.get("source_span", e.get("source_span_id", ""))} for e in historical]
        relevant = [t for t in transfers if t["decision"] == "INCLUDED" and t["projection"]["projected_md_interval_m"][0] <= interval[1] and t["projection"]["projected_md_interval_m"][1] >= interval[0]]
        row = {"well_id": offset["id"], "analog": analog, "transfers": transfers, "weight": 0., "role": "UNKNOWN", "reason": "coverage_unverified_incomplete_or_no_explicit_clean_statement"}
        if analog["blockers"]: row.update(role="EXCLUDED", reason="; ".join(analog["blockers"]))
        elif relevant:
            best = max(relevant, key=lambda t: t["weight"])
            row.update(role="SUPPORT", weight=best["weight"], reason="transferable_documented_event_overlaps_interval", selected_event_id=best["event_id"])
        else:
            # Any uncertain same-risk record prevents asserting a clean crossing.
            uncertain = bool(historical)  # Conflicting event and whole-interval negation require review.
            clean = None if uncertain else clean_evidence(store, active, offset, name, risk, interval, radius, operation)
            if clean: row.update(role="COUNTER", weight=clean["weight"], reason="verified_interval_and_explicit_no_event_statement", clean_source=clean)
        rows.append(row)
    summary = aggregate(rows)
    return snapshot(store, "evidence_snapshot", {"active_well_id": active["id"], "formation": name,
        "risk": risk, "md_interval_m": interval, "radius_km": radius, "operation_state": operation,
        "context_source": context_source,
        "provenance_type": "INFERRED", "policy_version": VERSION, "rows": rows, **summary})
