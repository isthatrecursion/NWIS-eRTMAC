"""Local document ingestion with explicit source spans and review gates."""
import hashlib
import re
from pathlib import Path
from statistics import mean
from pydantic import BaseModel, Field
from .paths import DATA_ROOT
from .domain.enums import CauseType, EventType, ExtractionConfidence
from .domain.units import normalize
from .gazetteer import match_formation
from .document_intelligence import detect_layout, metadata, extract_quantities, narrative_chain, ABBREVIATIONS, expand_abbreviations, parse_date, DATE

VERSION = "grounded-parser/2.1"
_ocr = None


class ExtractedEvent(BaseModel):
    event_type: EventType
    md_from_m: float | None = Field(default=None, ge=0)
    formation_id: str | None = None
    symptom: str | None = None
    cause_text: str | None = None
    cause_kind: CauseType = CauseType.UNKNOWN
    mitigation: str | None = None
    outcome: str | None = None
    operation_state: str = "UNKNOWN"
    review_status: str = "NEEDS_REVIEW"


def read_pages(content, suffix):
    if suffix in (".txt", ".md"):
        text = content.decode("utf-8-sig")
        return [{"page": 1, "text": text, "is_scan": False, "confidence": 1.,
                 "lines": [{"text": line, "bbox": None} for line in text.splitlines()]}]
    if suffix != ".pdf":
        raise ValueError("Supported files: PDF, UTF-8 TXT, Markdown")
    import fitz
    import numpy as np
    global _ocr
    pages = []
    with fitz.open(stream=content, filetype="pdf") as pdf:
        if pdf.is_encrypted:
            raise ValueError("Encrypted PDFs require an unlocked copy")
        if len(pdf) > 100:
            raise ValueError("Prototype limit: 100 pages per upload")
        for index, page in enumerate(pdf):
            text = page.get_text()
            if len(text.strip()) >= 30:
                lines = []
                for block in page.get_text("dict")["blocks"]:
                    for line in block.get("lines", []):
                        lines.append({"text": "".join(span["text"] for span in line["spans"]), "bbox": list(line["bbox"])})
                pages.append({"page": index+1, "text": text, "lines": lines, "is_scan": False, "confidence": 1.})
            else:
                if _ocr is None:
                    from rapidocr_onnxruntime import RapidOCR
                    _ocr = RapidOCR()
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
                result, _ = _ocr(array)
                lines = [{"text": item[1], "bbox": [min(p[0] for p in item[0])/2, min(p[1] for p in item[0])/2,
                                                       max(p[0] for p in item[0])/2, max(p[1] for p in item[0])/2]} for item in (result or [])]
                pages.append({"page": index+1, "text": "\n".join(line["text"] for line in lines), "lines": lines,
                              "is_scan": True, "confidence": mean(item[2] for item in result) if result else 0.})
    return pages


def labeled(text, label):
    found = re.search(rf"{label}\s*:\s*([^\n]+)", text, re.I)
    return found.group(1).strip() if found else None


def extract(page):
    text = page["text"]
    raw_formation = labeled(text, "Formation")
    formation_match = match_formation(raw_formation)
    formation = formation_match["formation_id"]
    candidates = []
    event_patterns = {"MUD_LOSS": r"(?:mud\s*loss|lost\s*circulation|partial\s*returns|severe\s*losses)",
                      "STUCK_PIPE": r"stuck\s*pipe", "KICK": r"\b(?:kick|influx)\b",
                      "TORQUE_DYSFUNCTION": r"(?:torque\s*dysfunction|stick\s*slip)",
                      "CEMENTING_ISSUE": r"(?:cementing\s*failure|cement\s*loss)"}
    lines = [dict(line) for line in page["lines"]]
    for table in page.get("layout", {}).get("tables", []):
        for row in table["rows"]:
            text_row = " | ".join(row["cells"])
            if not any(re.search(pattern, text_row, re.I) for pattern in event_patterns.values()):
                continue
            depth_columns = [column for column in table["depth_columns"] if column["index"] < len(row["cells"])]
            if len(depth_columns) != 1:
                continue
            column = depth_columns[0]
            raw_depth = row["cells"][column["index"]]
            if not re.fullmatch(r"[\d,]+(?:\.\d+)?", raw_depth):
                continue
            raw_source = row["source"]["text"] if not row.get("cell_sources") else "\n".join(row["cells"])
            depth_source = dict(row["cell_sources"][column["index"]] if row.get("cell_sources") else row["source"])
            depth_source.update(table_header=column["header"], cell_text=raw_depth)
            record = {"text": text_row, "source_text": raw_source, "bbox": row["source"].get("bbox"),
                      "table_depth": (raw_depth, column["unit"], column["reference"]), "depth_source": depth_source}
            existing_line = next((item for item in lines if item["text"] == raw_source), None)
            if existing_line:
                existing_line.update(record)
            else:
                lines.append(record)
    first_event = next((index for index, line in enumerate(lines) if any(re.search(pattern, expand_abbreviations(line["text"]), re.I) for pattern in event_patterns.values())), len(lines))
    header_quantities = extract_quantities(page, lines[:first_event])
    for line_index, line in enumerate(lines):
        sentence = line["text"]
        expanded = expand_abbreviations(sentence)
        for event_type, pattern in event_patterns.items():
            if not re.search(pattern, expanded, re.I) or re.search(r"\b(?:no\s*(?:mud|partial|severe|loss|lost|kick|influx|stuck|cement|torque)|without|not\s*observed|denied)", expanded, re.I):
                continue
            # Require a depth in the event sentence; never borrow an unrelated coverage number.
            match = re.search(r"\b(?:At|Depth\s*:?|@)\s*([\d,]+(?:\.\d+)?)\s*(m|metres?|meters?|ft|feet)\s*(MD|TVD)?", sentence, re.I)
            if not match and line.get("table_depth"):
                match = re.match(r"([\d,]+(?:\.\d+)?)\s*(m|ft)\s*(MD|TVD)", " ".join(line["table_depth"]), re.I)
            depth, original, unit = None, None, None
            measurement = None
            interval_match = re.search(r"(?:At|Event interval\s*:)\s*([\d,.]+)\s*(m|ft)?\s*(?:to|–|-)\s*([\d,.]+)\s*(m|ft)\s*MD", sentence, re.I)
            if interval_match:
                match = re.match(r"([\d,.]+)\s*(m|ft)\s*(MD)", f"{interval_match.group(1)} {interval_match.group(2) or interval_match.group(4)} MD", re.I)
            if match:
                original = float(match.group(1).replace(",", "")); unit = match.group(2).lower()
                reference = (match.group(3) or "MD").upper()
                measurement = normalize(original, "ft" if unit in ("ft", "feet") else "m", "depth",
                    labeled(text, "Datum") or "UNKNOWN", reference, sentence).model_dump()
                if reference == "MD": depth = measurement["value"]
            end = len(lines)
            for next_index in range(line_index+1, len(lines)):
                next_text = lines[next_index]["text"]
                if (lines[next_index].get("table_depth") or re.search(r"\b(?:At|Depth\s*:?)\s*\d", next_text, re.I)) and any(re.search(p, expand_abbreviations(next_text), re.I) for p in event_patterns.values()):
                    end = next_index; break
            chain_lines = lines[line_index:end]
            chain_text = "\n".join(row["text"] for row in chain_lines)
            narrative = narrative_chain(chain_lines)
            def chain_value(field, label):
                return labeled(chain_text, label) or narrative.get(field, {}).get("text")
            operation = (labeled(chain_text, "Operation") or labeled(text, "Operation") or "UNKNOWN").upper()
            if operation == "UNKNOWN":
                operation = next((state for abbreviation, state in ABBREVIATIONS.items() if re.search(rf"\b{abbreviation}\b", chain_text, re.I)), operation)
            operation = ABBREVIATIONS.get(operation, operation)
            if operation not in {"DRILLING", "TRIPPING", "TRIPPING_IN", "TRIPPING_OUT", "REAMING", "CIRCULATING", "CONNECTION", "CEMENTING", "LOGGING", "STATIC", "UNKNOWN"}:
                operation = "UNKNOWN"
            event = ExtractedEvent(event_type=event_type, md_from_m=depth, formation_id=formation,
                symptom=chain_value("symptom", "Symptom"), cause_text=chain_value("cause_text", "Cause"),
                cause_kind="stated" if chain_value("cause_text", "Cause") else "unknown", mitigation=chain_value("mitigation", "Mitigation"),
                outcome=chain_value("outcome", "Outcome"), operation_state=operation)
            reasons = []
            if re.search(r"\b(?:potential|possible|contingency|training|planning|has not started|none occurred)\b", sentence, re.I):
                reasons.append("Prospective or negated narrative context requires review before treating this as an observed event")
            if depth is None: reasons.append("Missing or non-MD event depth")
            if formation is None: reasons.append("Unverified formation alias")
            if re.search(r"\bSP\b", sentence): reasons.append("Ambiguous SP drilling abbreviation requires confirmation")
            numerical_fields = {**header_quantities, **extract_quantities(page, chain_lines)}
            if any(item.get("requires_review") for item in numerical_fields.values()):
                reasons.append("Conflicting event numerical fields")
            if page["is_scan"]: reasons.append("OCR-derived event requires review")
            if page["confidence"] < .85: reasons.append("Low OCR confidence")
            event.review_status = "NEEDS_REVIEW" if reasons else "AUTO_ACCEPTED"
            if depth is not None and depth > 15000:
                event.review_status = "QUARANTINED"; reasons.append("Depth outside prototype physical range")
            candidates.append({**event.model_dump(), "source_text": line.get("source_text", sentence), "bbox": line["bbox"],
                "field_evidence": {name: {"page": page["page"], "text": labeled(text if name == "formation_id" else chain_text, label)}
                    for name, label in [("symptom", "Symptom"), ("cause_text", "Cause"), ("mitigation", "Mitigation"), ("outcome", "Outcome"), ("formation_id", "Formation")]
                    if labeled(text if name == "formation_id" else chain_text, label) is not None},
                "original_value": original, "original_unit": unit, "depth_reference": "MD" if depth is not None else "UNKNOWN",
                "normalization": "feet × 0.3048" if unit in ("ft", "feet") else "metres unchanged", "review_reasons": reasons})
            candidates[-1]["extraction_confidence"] = (ExtractionConfidence.HIGH if not reasons else
                ExtractionConfidence.MEDIUM if page["confidence"] >= .85 else ExtractionConfidence.LOW)
            if measurement:
                candidates[-1]["measurements"] = {"md_from_m" if depth is not None else "tvd_m": measurement}
            candidate = candidates[-1]
            candidate["severity"] = "UNKNOWN"
            severity = re.search(r"\b(partial|minor|moderate|severe|total|complete)\s+(?:mud\s+)?(?:loss|losses|lost returns)", chain_text, re.I) if event_type == "MUD_LOSS" else None
            if severity:
                candidate["severity"] = {"minor": "MINOR", "partial": "PARTIAL", "moderate": "MODERATE", "severe": "SEVERE", "total": "TOTAL", "complete": "TOTAL"}[severity.group(1).lower()]
                candidate["field_evidence"]["severity"] = {"page": page["page"], "text": severity.group(0)}
            if interval_match:
                upper = float(interval_match.group(3).replace(",", ""))*(.3048 if interval_match.group(4).lower() == "ft" else 1)
                if depth is not None and depth <= upper <= 15000:
                    candidate["event_md_interval_m"] = [depth, upper]
                    candidate["md_to_m"] = upper
                    from .document_intelligence import source as interval_source
                    candidate["field_evidence"]["event_md_interval_m"] = interval_source(page, line, interval_match)
                    candidate.setdefault("measurements", {})["md_to_m"] = normalize(float(interval_match.group(3).replace(",", "")), interval_match.group(4).lower(), "depth", labeled(text, "Datum") or "UNKNOWN", "MD", interval_match.group(0)).model_dump()
                else:
                    candidate["review_status"] = "NEEDS_REVIEW"
                    candidate["review_reasons"].append("Invalid event depth interval")
            candidate["formation_match"] = formation_match
            candidate["numerical_fields"] = numerical_fields
            candidate.setdefault("measurements", {}).update({name: item["measurement"] for name, item in numerical_fields.items()})
            candidate["context_values"] = {name: item["value"] for name, item in numerical_fields.items() if not item.get("requires_review")}
            mud_system = re.search(r"Mud\s*(?:system|type)\s*:\s*(WBM|OBM|SBM|water[- ]based|oil[- ]based|synthetic[- ]based)\b", chain_text, re.I) or re.search(r"Mud\s*(?:system|type)\s*:\s*(WBM|OBM|SBM|water[- ]based|oil[- ]based|synthetic[- ]based)\b", text, re.I)
            if mud_system:
                raw_system = mud_system.group(1).upper()
                candidate["context_values"]["mud_system"] = raw_system if raw_system in ("WBM", "OBM", "SBM") else "WBM" if raw_system.startswith("WATER") else "OBM" if raw_system.startswith("OIL") else "SBM"
                candidate["field_evidence"]["mud_system"] = {"page": page["page"], "text": mud_system.group(0)}
            from .document_intelligence import source as field_source
            for field, source_line in narrative.items():
                if field not in candidate["field_evidence"]:
                    candidate["field_evidence"][field] = field_source(page, source_line)
            if measurement:
                candidate["field_evidence"]["md_from_m" if depth is not None else "tvd_m"] = line.get("depth_source") or field_source(page, line, match)
            candidate["field_evidence"].update({name: item["source"] for name, item in numerical_fields.items()})
            date_match = re.search(rf"(?:Event\s*date|Date)\s*:\s*({DATE})", chain_text, re.I)
            candidate["event_date"] = parse_date(date_match.group(1)) if date_match else None
    # Avoid duplicate symptom-only events when a depth-grounded event already covers this type.
    return [candidate for candidate in candidates if candidate["md_from_m"] is not None or
            not any(other["event_type"] == candidate["event_type"] and other["md_from_m"] is not None for other in candidates)]


def ingest(store, content, filename, well_id, synthetic=False, storage_dir=None, classification=None, doc_type=None):
    if not store.get("well", well_id):
        raise ValueError("Unknown well")
    if len(content) > 20*1024*1024: raise ValueError("Prototype upload limit is 20 MB")
    suffix = Path(filename).suffix.lower()
    key = hashlib.sha256(content+well_id.encode()).hexdigest()[:20]
    document_id = "DOC-"+key
    existing = store.get("document", document_id)
    if classification is None:
        classification = existing.get("classification", "PRIVATE") if existing else "PRIVATE"
    if classification not in ("PRIVATE", "PUBLIC"):
        raise ValueError("Classification must be PRIVATE or PUBLIC")
    if existing and (existing.get("extractor_version") == VERSION or
            any(store.get("event", key).get("reviewer") for key in existing["event_ids"]) or
            any(store.get("coverage", key).get("reviewer") for key in existing["coverage_ids"])):
        if existing.get("classification", "PRIVATE") != classification or (doc_type and existing.get("doc_type") != doc_type):
            checked = metadata(existing["page_data"], store.get("well", well_id), doc_type, classification)
            existing["classification"] = checked["classification"]
            if doc_type:
                existing["doc_type"] = doc_type
                existing["doc_type_source"] = "DECLARED"
            store.put("document", existing)
        return existing
    pages = read_pages(content, suffix)
    for page in pages:
        page["layout"] = detect_layout(page)
    intelligence = metadata(pages, store.get("well", well_id), doc_type, classification)
    root = Path(storage_dir or DATA_ROOT/"runtime"/"uploads")
    root.mkdir(parents=True, exist_ok=True)
    path = root/(document_id+suffix); path.write_bytes(content)
    event_ids, review_ids, coverage_ids = [], [], []
    measurements = {}
    for page in pages:
        page_dates = [interval for interval in intelligence["date_coverages"] if interval["source"]["page"] == page["page"]]
        date_coverage = page_dates[0] if len(page_dates) == 1 else None
        for label, field, quantity in [("ECD", "ecd_sg", "density"), ("Mud density", "mud_density_sg", "density"),
                                       ("Standpipe pressure", "standpipe_pressure_kpa", "pressure")]:
            found = re.search(rf"{label}\s*:\s*([\d.]+)\s*(kg/m3|g/cm3|ppg|sg|kPa|MPa|Pa|psi|bar)\b", page["text"], re.I)
            if found:
                raw_unit = found.group(2)
                unit = {"kpa": "kPa", "mpa": "MPa", "pa": "Pa"}.get(raw_unit.lower(), raw_unit.lower())
                measurements[f"page_{page['page']}_{field}"] = normalize(float(found.group(1)), unit, quantity,
                    labeled(page["text"], "Datum") or "UNKNOWN", "UNKNOWN", f"page {page['page']}: {found.group(0)}").model_dump()
        for index, parsed in enumerate(extract(page)):
            if "Reported well name does not match associated well" in intelligence["review_reasons"]:
                parsed["review_reasons"].append("Reported well name does not match associated well")
                parsed["review_status"] = "NEEDS_REVIEW"
            event_id = f"EV-{key}-{page['page']}-{index}"
            span_id = f"SPAN-{key}-{page['page']}-{index}"
            store.put("source_span", {"id": span_id, "document_id": document_id, "page": page["page"],
                "char_start": page["text"].find(parsed["source_text"]),
                "char_end": page["text"].find(parsed["source_text"])+len(parsed["source_text"]),
                "text": parsed.pop("source_text"), "bbox": parsed.pop("bbox"), "synthetic_flag": synthetic})
            item = {**parsed, "id": event_id, "well_id": well_id, "document_id": document_id,
                "source_span_id": span_id, "synthetic": synthetic, "extractor_version": VERSION, "confidence": page["confidence"],
                "datum": labeled(page["text"], "Datum") or "UNKNOWN"}
            store.put("event", item); event_ids.append(event_id)
            if item["review_status"] in ("NEEDS_REVIEW", "QUARANTINED"):
                review_id = "REV-"+event_id
                store.put("review", {"id": review_id, "kind": "event", "entity_id": event_id, "document_id": document_id,
                    "status": "PENDING", "reason": "; ".join(item["review_reasons"]), "priority": "HIGH"})
                review_ids.append(review_id)
        coverage = re.search(r"Coverage\s*:\s*([\d,.]+)\s*(m|ft)\s*to\s*([\d,.]+)\s*(m|ft)\s*MD", page["text"], re.I)
        cov_id = f"COV-{key}-{page['page']}"
        interval = None
        if coverage:
            interval = [float(coverage.group(1).replace(",", ""))*(.3048 if coverage.group(2).lower() == "ft" else 1),
                        float(coverage.group(3).replace(",", ""))*(.3048 if coverage.group(4).lower() == "ft" else 1)]
            if interval[0] < 0 or interval[1] <= interval[0]: interval = None
        store.put("coverage", {"id": cov_id, "well_id": well_id, "document_id": document_id, "page": page["page"],
            "md_interval": interval, "coverage_status": "PROBABLE" if interval else "UNKNOWN", "reviewer": None,
            "date_from": date_coverage["date_from"] if date_coverage else None,
            "date_to": date_coverage["date_to"] if date_coverage else None,
            "date_source": date_coverage["source"] if date_coverage else None,
            "date_coverage_status": "PROBABLE" if date_coverage else "UNKNOWN",
            "synthetic_flag": synthetic,
            "measurements": {name: normalize(float(coverage.group(value).replace(",", "")), coverage.group(unit).lower(),
                "depth", labeled(page["text"], "Datum") or "UNKNOWN", "MD", coverage.group(0)).model_dump()
                for name, value, unit in [("md_from_m", 1, 2), ("md_to_m", 3, 4)]} if coverage else {},
            "source_text": coverage.group(0) if coverage else "No valid explicit interval", "datum": labeled(page["text"], "Datum") or "UNKNOWN"})
        coverage_ids.append(cov_id)
        if interval or date_coverage:
            review_id = "REV-"+cov_id
            store.put("review", {"id": review_id, "kind": "coverage", "entity_id": cov_id, "document_id": document_id,
                "status": "PENDING", "reason": "Confirm explicit interval and date coverage before counting clean crossings", "priority": "MEDIUM"})
            review_ids.append(review_id)
    if intelligence["review_reasons"]:
        review_id = "REV-"+document_id
        store.put("review", {"id": review_id, "kind": "document", "entity_id": document_id, "document_id": document_id,
            "status": "PENDING", "reason": "; ".join(intelligence["review_reasons"]), "priority": "HIGH", "synthetic_flag": synthetic})
        review_ids.append(review_id)
    doc = {**intelligence, "id": document_id, "well_id": well_id, "title": Path(filename).name,
        "pages": len(pages), "is_scan": any(p["is_scan"] for p in pages), "ocr_confidence": mean(p["confidence"] for p in pages) if pages else 0,
        "review_status": "NEEDS_REVIEW" if review_ids else "AUTO_ACCEPTED", "synthetic": synthetic,
        "event_ids": event_ids, "coverage_ids": coverage_ids, "path": str(path), "page_data": pages, "extractor_version": VERSION}
    doc["measurements"] = measurements
    doc["measurements"].update({name: item["measurement"] for name, item in intelligence["numerical_fields"].items()})
    store.put("document", doc)
    return doc
