"""Versioned, basin-scoped formation registry; fuzzy candidates require review."""
from difflib import SequenceMatcher
import re

VERSION = "assam-arakan-gazetteer/1.1"
SOURCE = "https://www.ndrdgh.gov.in/NDR/?page_id=617"
NAMES = ["Tipam Sandstone", "Barail", "Girujan Clay", "Kopili", "Langpar", "Lakadong", "Therria",
         "Tura Sandstone", "Sylhet Limestone", "Bokabil", "Bhuban", "Disang", "Surma", "Khasi",
         "Dergaon", "Dupitila", "Dihing", "Dhekiajuli"]


def clean(value):
    value = re.sub(r"\b(?:formation|group|fm)\b\.?", "", value.lower())
    return re.sub(r"[^a-z0-9]", "", value)


ENTRIES = [{"id": name.split()[0].upper(), "name": name, "basin": "ASSAM_ARAKAN",
            "aliases": [name, name.split()[0]], "sources": [{"url": SOURCE, "authority": "DGH / National Data Repository"}],
            "synthetic_flag": False} for name in NAMES]
ENTRIES.append({"id": "NAMSANG", "name": "Namsang", "basin": "ASSAM_ARAKAN",
    "aliases": ["Namsang"], "sources": [{"url": "https://www.oil-india.com/files/oldtender/global/NIT_CDG4898P21.pdf",
        "authority": "Oil India", "section": "4.3 Expected Formation Tops, Table 4"}], "synthetic_flag": False})
next(entry for entry in ENTRIES if entry["id"] == "LAKADONG")["aliases"].append("Lakadang")


def match_formation(raw, basin="ASSAM_ARAKAN"):
    query = clean(raw or "")
    eligible = [entry for entry in ENTRIES if entry["basin"] == basin]
    ranked = sorted([(max(SequenceMatcher(None, query, clean(alias)).ratio() for alias in entry["aliases"]), entry)
                     for entry in eligible], key=lambda item: -item[0]) if query else []
    exact = [entry for entry in eligible if query and query in {clean(alias) for alias in entry["aliases"]}]
    result = {"raw": raw, "basin": basin, "gazetteer_version": VERSION, "formation_id": None,
              "confidence": 0., "method": "UNKNOWN", "requires_review": True, "candidates": []}
    if len(exact) == 1:
        result.update(formation_id=exact[0]["id"], confidence=1., method="EXACT_ALIAS", requires_review=False,
                      sources=exact[0]["sources"])
    else:
        result.update(method="FUZZY_CANDIDATE" if ranked and ranked[0][0] >= .65 else "UNKNOWN",
            confidence=round(ranked[0][0], 4) if ranked else 0.,
            candidates=[{"formation_id": entry["id"], "confidence": round(score, 4), "sources": entry["sources"]}
                        for score, entry in ranked[:3] if score >= .65])
    return result
