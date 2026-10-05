import os
from pathlib import Path

DATA_ROOT = Path(os.environ.get("NWIS_DATA_ROOT", str(Path(__file__).resolve().parents[2]/"storage")))
