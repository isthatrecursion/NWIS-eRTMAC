"""Offline deterministic synthetic-field fixture generator. Never imported by runtime APIs."""
import argparse
import json
import math
from pathlib import Path
import random

from .store import Store
from .paths import DATA_ROOT
from .domain.units import enrich

VERSION = "synthetic-field/2.1"
EVENT_DETAILS = {
    "STUCK_PIPE": ("stuck pipe", "TRIPPING", "restricted pipe movement", "Worked pipe under approved procedure", "pipe freed"),
    "KICK": ("kick / influx", "DRILLING", "pit gain and excess returns", "Applied approved well-control procedure", "influx contained"),
    "TORQUE_DYSFUNCTION": ("torque dysfunction", "REAMING", "erratic torque", "Reviewed drilling programme", "torque stabilized"),
    "CEMENTING_ISSUE": ("cementing failure", "CEMENTING", "cement losses", "Reviewed cement placement", "remedial plan recorded"),
}

RUNTIME = DATA_ROOT / "runtime"
EVALUATION = DATA_ROOT / "evaluation"


def build_field(seed=121, count=24):
    if not 20 <= count <= 40:
        raise ValueError("Prototype field requires 20–40 wells")
    rng = random.Random(seed)
    event_rng = random.Random(seed+10000)
    wells, events, truth = [], [], []
    for i in range(count):
        active = i == 0
        x, y = (0., 0.) if active else (rng.uniform(-2400, 2400), rng.uniform(-2400, 2400))
        inc, azi = rng.uniform(12, 46), rng.uniform(0, 360)
        if i == 0: inc, azi = 30., 90.
        if i == 1: x, y, inc, azi = 100., 0., 30., 270.
        if i == 2: x, y, inc, azi = 1600., 0., 0., 90.
        top = 2200.+rng.uniform(-90, 90)
        thickness = rng.uniform(320, 430)
        if i < 3: top, thickness = 2200., 380.
        well_id = "SYN-ACTIVE-01" if active else f"SYN-NHK-{i:02d}"
        intervals = [
            {"formation_id": "NAMSANG", "name": "Namsang (synthetic)", "top_md_m": 1800., "base_md_m": top, "uncertainty_m": 8., "datum": "LOCAL_KB", "review_status": "VERIFIED"},
            {"formation_id": "TIPAM", "name": "Tipam analogue (synthetic)", "top_md_m": top, "base_md_m": top+thickness, "uncertainty_m": 12.+i%4*4, "datum": "LOCAL_KB", "review_status": "VERIFIED"},
            {"formation_id": "BARAIL", "name": "Barail analogue (synthetic)", "top_md_m": top+thickness, "base_md_m": 3200., "uncertainty_m": 24., "datum": "LOCAL_KB", "review_status": "VERIFIED"},
        ]
        if i == 20: intervals = [f for f in intervals if f["formation_id"] != "TIPAM"]
        if i == 21: intervals[1]["base_md_m"] = None; intervals[1]["approx_thickness_m"] = 380.
        survey = [{"md_m": float(md), "incl_deg": inc if md >= 800 else inc*md/800, "azi_deg": azi} for md in range(0, 3401, 100)]
        ecd = round(rng.uniform(1.08, 1.28), 3)
        weakness = rng.uniform(0, 1)
        region = ("WEST" if x < -500 else "EAST" if x > 900 else "CENTRAL")
        latent = weakness + max(0, ecd-1.15)*4 + (0.2 if region == "EAST" else 0)
        loss = rng.random() < min(.85, latent*.55)
        if i in (0, 2, 3): loss = True
        depth = round(top+thickness*rng.uniform(.82, .94), 1)
        if i == 2: depth = 2548.
        complete = i not in (5, 9, 14, 20)
        wells.append({"id": well_id, "name": well_id, "field": "Synthetic Upper Assam", "synthetic": True,
            "status": "ACTIVE" if active else "OFFSET", "x_m": round(x, 2), "y_m": round(y, 2),
            "latitude": 27.28+y/111320, "longitude": 95.33+x/(111320*math.cos(math.radians(27.28))),
            "surface_x_km": x/1000, "surface_y_km": y/1000, "crs": "LOCAL_ENU_METRES_DEMO",
            "datum": "LOCAL_KB", "structural_domain": region, "structural_quality": "SYNTHETIC_TRUSTED",
            "survey": survey, "formations": intervals, "mud_program": {"mud_system": "WBM", "ecd_sg": ecd, "hole_section_in": 8.5},
            "casing_program": [{"size_in": 13.375, "setting_md_m": 850.}, {"size_in": 9.625, "setting_md_m": 2100.}],
            "coverage_expected": complete, "held_out": active})
        item = {"id": f"EV-SYN-{i:02d}", "well_id": well_id, "event_type": "MUD_LOSS", "md_from_m": depth,
            "formation_id": "TIPAM", "symptom": "partial returns", "severity": "SEVERE" if weakness > .6 else "MODERATE",
            "operation_state": "DRILLING", "cause_kind": "unknown", "mitigation": "LCM pill pumped", "outcome": "returns improved", "synthetic": True}
        truth.append({**item, "event_present": loss, "latent_weakness": weakness})
        if loss and not active and complete: events.append(item)
        # Separate planted event families with deterministic, type-specific occurrence.
        # Every family is guaranteed in the report population; active-well truth stays held out.
        for j, (kind, details) in enumerate(EVENT_DETAILS.items()):
            phrase, operation, symptom, mitigation, outcome = details
            present = active or i == j+1 or event_rng.random() < (.22 + weakness*.15)
            extra = {**item, "id": f"EV-SYN-{i:02d}-{kind}", "event_type": kind,
                "md_from_m": round(top+thickness*(.3+j*.12), 1), "operation_state": operation,
                "symptom": symptom, "mitigation": mitigation, "outcome": outcome}
            truth.append({**extra, "event_present": present, "latent_weakness": weakness})
            if present and not active and complete:
                events.append(extra)
    return enrich({"seed": seed, "generator_version": VERSION, "synthetic_flag": True,
                   "wells": wells, "events": events}), enrich(truth, True)


def generate_reports(field, root):
    import fitz
    from PIL import Image, ImageDraw, ImageFont
    root.mkdir(parents=True, exist_ok=True)
    manifest = []
    for i, well in enumerate(field["wells"][1:13], start=1):
        well_events = [e for e in field["events"] if e["well_id"] == well["id"]]
        event = next((e for e in well_events if e["event_type"] == "MUD_LOSS"), None)
        top = well["formations"][1]["top_md_m"]
        lines = ["SYNTHETIC DEMONSTRATION DATA - NOT OIL FIELD DATA", "Daily Drilling Report", f"Well: {well['id']}",
                 "Date: 2026-01-15", "Date coverage: 2026-01-01 to 2026-01-15",
                 "Formation: Tipam", "Operation: DRILLING", f"Coverage: {top:.1f} m to {top+380:.1f} m MD", "Datum: LOCAL_KB"]
        if event:
            lines += [f"At {event['md_from_m']:.1f} m MD, partial mud loss observed.", "Symptom: partial returns.", "Mitigation: LCM pill pumped.", "Outcome: returns improved."]
        else: lines += ["No mud loss observed during the covered drilling interval."]
        for extra in well_events:
            if extra["event_type"] == "MUD_LOSS":
                continue
            phrase = EVENT_DETAILS[extra["event_type"]][0]
            lines += [f"At {extra['md_from_m']:.1f} m MD, {phrase} observed.",
                      f"Operation: {extra['operation_state']}",
                      f"Symptom: {extra['symptom']}.", f"Mitigation: {extra['mitigation']}.",
                      f"Outcome: {extra['outcome']}."]
        doc_type = "WCR" if i % 2 == 0 else "DDR"
        lines[1] = "Well Completion Report" if doc_type == "WCR" else "Daily Drilling Report"
        # Structured operational table, varied units, headers and controlled OCR noise.
        lines += ["OPERATIONS TABLE | MD (m) | ECD (sg) | SPP (psi)",
                  f"Drilling | {top:.1f} | {well['mud_program']['ecd_sg']:.3f} | 1800",
                  f"ECD: {well['mud_program']['ecd_sg']/.119826427316:.5f} ppg" if i % 4 == 0 else f"ECD: {well['mud_program']['ecd_sg']:.3f} sg",
                  "Standpipe pressure: 1800 psi",
                  "End of interval summary | synthetic_flag: true"]
        if i % 4 == 0:
            for planted in well_events:
                lines = [line.replace(f"{planted['md_from_m']:.1f} m MD", f"{planted['md_from_m']/.3048:.3f} ft MD")
                         if line.startswith("At ") else line for line in lines]
        if not well["coverage_expected"]: lines = [line for line in lines if not line.startswith("Coverage:")]+["Interval coverage is incomplete."]
        scanned = i in (3, 7)
        path = root / f"{well['id']}-{doc_type}.pdf"
        pdf = fitz.open()
        page = pdf.new_page(width=595, height=842)
        if scanned:
            image = Image.new("RGB", (1400, 1800), "white")
            draw = ImageDraw.Draw(image)
            try: font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 28)
            except OSError: font = ImageFont.load_default(size=28)
            for j, line in enumerate(lines): draw.text((60, 70+j*42), line, fill=(25, 25, 25), font=font)
            if i == 7:
                for n in range(120):
                    draw.point((37*n % 1400, 61*n % 1800), fill=(180, 180, 180))
            import io
            stream = io.BytesIO(); image.save(stream, format="PNG")
            page.insert_image(page.rect, stream=stream.getvalue())
        else:
            page.insert_text((32, 48), "\n".join(lines), fontsize=10)
        if doc_type == "WCR":
            summary = pdf.new_page(width=595, height=842)
            summary.insert_text((32, 40), "SYNTHETIC DEMONSTRATION - WELL COMPLETION SUMMARY", fontsize=11)
            summary.insert_text((32, 65), f"Well: {well['id']}\nDatum: LOCAL_KB\nFormation and casing programme", fontsize=10)
            rows = [["Formation", "Top MD (m)", "Base MD (m)"]]
            rows += [[item["formation_id"], f"{item['top_md_m']:.1f}", str(item.get("base_md_m") or "Not confirmed")]
                     for item in well["formations"]]
            for row_index, row in enumerate(rows):
                for col_index, value in enumerate(row):
                    rect = fitz.Rect(32+col_index*170, 120+row_index*30, 202+col_index*170, 150+row_index*30)
                    summary.draw_rect(rect, color=(.25, .25, .25), fill=(.92, .94, .96) if row_index == 0 else None)
                    summary.insert_text((rect.x0+6, rect.y0+19), value, fontsize=10)
            summary.insert_text((32, 300), "Programme summary (synthetic):\n"+"\n".join(
                f"Casing {item['size_in']} in; setting depth {item['setting_md_m']} m MD" for item in well["casing_program"]), fontsize=10)
        pdf.save(path, no_new_id=True); pdf.close()
        manifest.append({"path": str(path), "well_id": well["id"], "synthetic": True,
            "synthetic_flag": True, "is_scan": scanned, "doc_type": doc_type,
            "format_variant": "scan-noise" if scanned else "native-table", "generator_version": VERSION})
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def write_evaluation(field, truth, root):
    root.mkdir(parents=True, exist_ok=True)
    held_out = {well["id"] for well in field["wells"] if well["held_out"]}
    manifests = {
        "truth.json": truth,
        "held_out_events.json": [item for item in truth if item["well_id"] in held_out and item["event_present"]],
        "expected_intervals.json": [{"event_id": item["id"], "well_id": item["well_id"],
            "event_type": item["event_type"], "formation_id": item["formation_id"],
            "md_interval_m": [item["md_from_m"]-10, item["md_from_m"]+10],
            "datum": "LOCAL_KB", "synthetic_flag": True} for item in truth if item["event_present"]],
        "generator_metadata.json": {"seed": field["seed"], "version": VERSION,
            "well_count": len(field["wells"]), "event_types": ["MUD_LOSS", *EVENT_DETAILS],
            "held_out_well_ids": sorted(held_out), "synthetic_flag": True,
            "interval_tolerance_m": 10, "purpose": "offline evaluation only"},
    }
    for name, data in manifests.items():
        (root/name).write_text(json.dumps(data, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--seed", type=int, default=121); parser.add_argument("--count", type=int, default=24)
    args = parser.parse_args()
    field, truth = build_field(args.seed, args.count)
    store = Store()
    for well in field["wells"]: store.put("well", well)
    RUNTIME.mkdir(parents=True, exist_ok=True); EVALUATION.mkdir(parents=True, exist_ok=True)
    write_evaluation(field, truth, EVALUATION)
    # Input fixture for the later replay adapter; no event labels appear in this CSV.
    import csv
    with (RUNTIME / "replay.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["elapsed_s", "bit_md_m", "hole_md_m", "operation_state", "flow_in_l_min", "flow_out_l_min", "pit_volume_m3", "ecd_sg", "mud_weight_sg", "wob_kn", "rpm", "rop_m_h", "torque_kn_m", "hookload_kn", "standpipe_pressure_kpa", "gas_pct"])
        writer.writeheader()
        for step in range(181):
            depth = 2400.+step
            loss_signal = max(0., min(1., (depth-truth[0]["md_from_m"]+10)/20))
            writer.writerow({"elapsed_s": step*10, "bit_md_m": depth, "operation_state": "DRILLING", "flow_in_l_min": 950.,
                "flow_out_l_min": round(945.-loss_signal*60., 2), "pit_volume_m3": round(410.-loss_signal*3., 2), "ecd_sg": 1.19,
                "hole_md_m": 2600, "mud_weight_sg": 1.16, "wob_kn": 90, "rpm": 120, "rop_m_h": 20, "torque_kn_m": 12, "hookload_kn": 1200, "standpipe_pressure_kpa": 18000, "gas_pct": .5})
    manifest = generate_reports(field, RUNTIME / "reports")
    print(json.dumps({"wells": len(field["wells"]), "reports": len(manifest), "scans": sum(d["is_scan"] for d in manifest), "truth": "offline evaluation directory"}))


if __name__ == "__main__": main()
