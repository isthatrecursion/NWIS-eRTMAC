"""Deterministic source-grounded layout, metadata, abbreviations and quantity parsing."""
from datetime import datetime
import re
from .domain.units import normalize

VERSION = "document-intelligence/1.1"
ABBREVIATIONS = {"POOH": "TRIPPING_OUT", "RIH": "TRIPPING_IN", "WOC": "STATIC",
    "DRLG": "DRILLING", "CIRC": "CIRCULATING", "RMG": "REAMING", "CMTG": "CEMENTING"}
EVENT_ABBREVIATIONS = {"LC": "lost circulation", "SP": "stuck pipe", "S&S": "stick slip"}
NUMBER = r"[+-]?\d+(?:,\d{3})*(?:\.\d+)?"
DATE = r"(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})"


def expand_abbreviations(text):
    for abbreviation, phrase in EVENT_ABBREVIATIONS.items():
        text = re.sub(rf"(?<!\w){re.escape(abbreviation)}(?!\w)", phrase, text)
    return text


def source(page, line, match=None):
    text = line["text"]
    start = page["text"].find(text)
    return {"page": page["page"], "text": match.group(0) if match else text, "bbox": line.get("bbox"),
            "char_start": start+match.start() if match and start >= 0 else start,
            "char_end": start+match.end() if match and start >= 0 else start+len(text) if start >= 0 else -1}


def detect_layout(page):
    regions, tables, sections = [], [], []
    rows = []
    for index, line in enumerate(page["lines"]):
        text = line["text"].strip()
        kind = "BODY"
        header = False
        if index < 5 and (re.search(r"report|well\s*:|date\s*:|SYNTHETIC", text, re.I)):
            kind = "HEADER"
            header = True
        if text and (text.isupper() or re.match(r"(?:\d+\.?\s+)?(?:operations|summary|geology|formation and|cementing|conclusions)\b", text, re.I)):
            kind = "SECTION"
            sections.append({"title": text, "line_index": index, "source": source(page, line)})
        regions.append({"kind": kind, "is_header": header, "line_index": index, "source": source(page, line)})
        if "|" in text or "\t" in text:
            rows.append({"cells": [cell.strip() for cell in re.split(r"\||\t", text)], "source": source(page, line)})
    # Native PDF columns appear as separate lines with matching vertical coordinates.
    groups = []
    for line in page["lines"]:
        if not line.get("bbox"):
            continue
        group = next((group for group in groups if abs(group[0]["bbox"][1]-line["bbox"][1]) < 3), None)
        if group is None:
            groups.append([line])
        else:
            group.append(line)
    for group in groups:
        if len(group) >= 2:
            group.sort(key=lambda line: line["bbox"][0])
            rows.append({"cells": [line["text"] for line in group], "cell_sources": [source(page, line) for line in group],
                         "source": source(page, group[0])})
    current = None
    for row in rows:
        depth_columns = [{"index": index, "header": cell, "reference": "TVD" if "TVD" in cell.upper() else "MD",
                          "unit": "ft" if "ft" in cell.lower() else "m"}
                         for index, cell in enumerate(row["cells"]) if re.search(r"\b(?:MD|TVD|depth)\b", cell, re.I)]
        if depth_columns:
            current = {"headers": row["cells"], "depth_columns": depth_columns, "rows": [], "source": row["source"]}
            tables.append(current)
        elif current:
            current["rows"].append(row)
    return {"version": VERSION, "regions": regions, "headers": [item for item in regions if item["is_header"]], "sections": sections, "tables": tables,
            "method": "line-text-and-bbox-heuristics"}


def parse_date(raw):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None


QUANTITIES = [
    ("mud_weight_sg", r"(?:Mud\s*(?:weight|density)|MW)", "density", r"kg/m3|g/cm3|ppg|sg"),
    ("ecd_sg", "ECD", "density", r"kg/m3|g/cm3|ppg|sg"),
    ("standpipe_pressure_kpa", r"(?:Standpipe\s*pressure|SPP)", "pressure", r"kPa|MPa|Pa|psi|bar"),
    ("pore_pressure_kpa", r"(?:Pore\s*pressure|PP)", "pressure", r"kPa|MPa|Pa|psi|bar"),
    ("overbalance_kpa", "Overbalance", "pressure", r"kPa|MPa|Pa|psi|bar"),
    ("hole_section_in", r"(?:Hole\s*(?:size|section)|Bit\s*size)", "diameter", r"inches|inch|in|mm"),
    ("stationary_exposure_h", r"(?:Stationary\s*(?:exposure|time)|Static\s*time)", "duration", r"hours?|hrs?|h|minutes?|mins?"),
    ("gas_pct", r"(?:Gas|Total\s*gas)", "percent", r"%"),
    ("influx_volume_m3", r"(?:Influx(?:\s*volume)?|Pit\s*gain)", "volume", r"m3|bbl"),
    ("permeability_md", "Permeability", "permeability", r"mD|D"),
    ("loss_rate_l_min", r"(?:Loss\s*rate|Losses)", "flow", r"L/min|lpm|bbl/hr"),
    ("torque_kn_m", "Torque", "torque", r"kN\.m|kNm|ft-lbf"),
    ("lcm_volume_m3", r"(?:LCM\s*(?:pill|volume))", "volume", r"m3|bbl"),
]
EXTRA_FACTORS = {"diameter": ("in", {"in": 1, "inch": 1, "inches": 1, "mm": 1/25.4}),
    "duration": ("h", {"h": 1, "hr": 1, "hrs": 1, "hour": 1, "hours": 1, "min": 1/60, "mins": 1/60, "minute": 1/60, "minutes": 1/60}),
    "percent": ("%", {"%": 1}), "volume": ("m3", {"m3": 1, "bbl": .158987294928}),
    "permeability": ("mD", {"mD": 1, "D": 1000}), "flow": ("L/min", {"L/min": 1, "lpm": 1, "bbl/hr": 158.987294928/60}),
    "torque": ("kN.m", {"kN.m": 1, "kNm": 1, "ft-lbf": .001355817948})}


def extract_quantities(page, lines=None, include_tables=True):
    fields = {}
    for line in lines if lines is not None else page["lines"]:
        for field, label, quantity, units in QUANTITIES:
            pattern = rf"\b{label}\s*[:=]?\s*(\d+\s+\d+/\d+|{NUMBER})\s*({units})(?!\w)"
            match = re.search(pattern, line["text"], re.I)
            if not match:
                continue
            raw_value, raw_unit = match.group(1), match.group(2)
            if "/" in raw_value:
                whole, fraction = raw_value.split()
                numerator, denominator = fraction.split("/")
                if float(denominator) == 0:
                    continue
                value = float(whole)+float(numerator)/float(denominator)
            else:
                value = float(raw_value.replace(",", ""))
            src = source(page, line, match)
            if quantity in EXTRA_FACTORS:
                canonical, factors = EXTRA_FACTORS[quantity]
                unit = next(unit for unit in factors if unit.lower() == raw_unit.lower())
                measurement = {"value": value*factors[unit], "unit": canonical, "original_value": value,
                    "original_unit": raw_unit, "datum": "UNKNOWN", "reference": "UNKNOWN", "source": src["text"], "algorithm_version": VERSION}
            else:
                unit = {"kpa": "kPa", "mpa": "MPa", "pa": "Pa"}.get(raw_unit.lower(), raw_unit.lower())
                measurement = normalize(value, unit, quantity, source=src["text"]).model_dump()
                measurement["original_unit"] = raw_unit
            # Conflicting repeated values are retained instead of choosing an arbitrary one.
            entry = {"value": measurement["value"], "measurement": measurement, "source": src}
            bounds = {"mud_weight_sg": (.5, 3), "ecd_sg": (.5, 3), "hole_section_in": (1, 50),
                "gas_pct": (0, 100), "stationary_exposure_h": (0, 10000), "permeability_md": (.000001, 1000000),
                "influx_volume_m3": (0, 10000), "pore_pressure_kpa": (0, 200000), "standpipe_pressure_kpa": (0, 200000)}
            if field in bounds and not bounds[field][0] <= entry["value"] <= bounds[field][1]:
                entry["requires_review"] = True
                entry["review_reason"] = "Quantity outside prototype physical range"
            if field in fields and fields[field]["value"] != entry["value"]:
                fields[field].setdefault("alternatives", []).append(entry)
                fields[field]["requires_review"] = True
            else:
                fields[field] = entry
    if include_tables and lines is None:
        for table in page.get("layout", {}).get("tables", []):
            for row in table["rows"]:
                for index, cell in enumerate(row["cells"]):
                    if index >= len(table["headers"]):
                        continue
                    header = table["headers"][index]
                    unit_match = re.search(r"\(([^)]+)\)", header)
                    if unit_match is None or not re.fullmatch(NUMBER, cell):
                        continue
                    label = header[:unit_match.start()].strip()
                    text = f"{label}: {cell} {unit_match.group(1)}"
                    parsed = extract_quantities({**page, "lines": [{"text": text, "bbox": row["source"].get("bbox")}]}, include_tables=False)
                    for field, item in parsed.items():
                        item["source"] = {**(row.get("cell_sources", [])[index] if row.get("cell_sources") else row["source"]),
                                          "table_header": header, "cell_text": cell, "column_index": index}
                        item["measurement"]["source"] = f"table column {header}; cell {cell}"
                        if field in fields and abs(fields[field]["value"]-item["value"]) > .0001:
                            fields[field].setdefault("alternatives", []).append(item)
                            fields[field]["requires_review"] = True
                        elif field not in fields:
                            fields[field] = item
    return fields


def metadata(pages, well, declared_type=None, classification="PRIVATE"):
    full_text = "\n".join(page["text"] for page in pages)
    types = {"DDR": r"Daily\s+Drilling\s+Report|\bDDR\b", "WCR": r"Well\s+Completion\s+Report|\bWCR\b",
             "MUD_LOG": r"Mud\s+Log", "CEMENT_REPORT": r"Cement(?:ing)?\s+Report"}
    observed = [kind for kind, pattern in types.items() if re.search(pattern, full_text, re.I)]
    doc_type = declared_type or (observed[0] if len(observed) == 1 else "UNKNOWN")
    reasons = []
    if doc_type == "UNKNOWN":
        reasons.append("Report type not identified in document content")
    if declared_type and observed and declared_type not in observed:
        reasons.append("Declared report type conflicts with document content")
    if len(observed) > 1 and not declared_type:
        reasons.append("Ambiguous report type")
    if classification == "PUBLIC" and re.search(r"\b(?:PRIVATE|CONFIDENTIAL|RESTRICTED)\b", full_text, re.I):
        raise ValueError("Public classification conflicts with private/confidential source markings")
    fields, dates, names = {}, [], []
    date_coverages = []
    date_interval = None
    for page in pages:
        for name, item in extract_quantities(page).items():
            fields[f"page_{page['page']}_{name}"] = item
        for line in page["lines"]:
            match = re.search(r"\bWell(?:\s*(?:name|ID))?\s*:\s*([^|;\n]+)", line["text"], re.I)
            if match:
                raw = match.group(1).strip()
                normalized = re.sub(r"[^a-z0-9]", "", raw.lower())
                aliases = [well["id"], well["name"], *well.get("aliases", [])]
                valid = normalized in {re.sub(r"[^a-z0-9]", "", value.lower()) for value in aliases}
                names.append({"raw": raw, "matches_associated_well": valid, "source": source(page, line, match)})
            interval = re.search(rf"Date\s*coverage\s*:\s*({DATE})\s*(?:to|through)\s*({DATE})", line["text"], re.I)
            if interval:
                start, end = parse_date(interval.group(1)), parse_date(interval.group(2))
                if start and end and start <= end:
                    date_interval = {"date_from": start, "date_to": end, "status": "PROBABLE", "source": source(page, line, interval)}
                    date_coverages.append(date_interval)
                    if "/" in interval.group(1) or "/" in interval.group(2):
                        reasons.append("Locale-ambiguous date coverage; verify day-first interpretation")
                else:
                    reasons.append("Invalid date coverage interval")
            elif re.search(r"\b(?:Date|Report\s*date|Event\s*date)\s*:", line["text"], re.I):
                for match in re.finditer(DATE, line["text"]):
                    parsed = parse_date(match.group(0))
                    dates.append({"value": parsed, "raw": match.group(0), "source": source(page, line, match),
                                  "requires_review": parsed is None or "/" in match.group(0)})
    if any(not item["matches_associated_well"] for item in names):
        reasons.append("Reported well name does not match associated well")
    if any(item.get("requires_review") for item in fields.values()):
        reasons.append("Conflicting numerical fields")
    if any(item["requires_review"] for item in dates):
        reasons.append("Invalid or locale-ambiguous report date")
    return {"doc_type": doc_type, "doc_type_source": "DECLARED" if declared_type else "CONTENT" if observed else "UNKNOWN",
            "classification": classification, "well_identity": names, "dates": dates,
            "well_identity_status": "MATCHED" if names and all(item["matches_associated_well"] for item in names) else "MISMATCHED" if names else "UNKNOWN",
            "date_coverage": date_interval, "numerical_fields": fields, "review_reasons": reasons,
            "date_coverages": date_coverages,
            "intelligence_version": VERSION}


def narrative_chain(lines):
    result = {}
    patterns = {"symptom": r"(?:observed|experienced|noted|showed|encountered|returns|pit\s*gain|overpull)",
                "cause_text": r"(?:due\s+to|because\s+of|caused\s+by|attributed\s+to)",
                "mitigation": r"(?:pumped|spotted|worked\s+(?:the\s+)?pipe|shut\s*in|circulated|reduced|reamed|fished)",
                "outcome": r"(?:improved|restored|stabilized|freed|recovered|contained|resumed)"}
    for field, pattern in patterns.items():
        matches = [line for line in lines if re.search(pattern, line["text"], re.I)]
        if matches:
            result[field] = matches[0]
    return result
