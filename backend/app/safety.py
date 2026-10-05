"""Local prototype safeguards, not production authentication or certification."""
from pathlib import Path
from fastapi import HTTPException


def source_path(doc):
    from .ingestion import DATA_ROOT
    path = Path(doc["path"]).resolve()
    if not path.is_relative_to(DATA_ROOT.resolve()): raise HTTPException(403, "Source is outside configured storage")
    return path
