import pytest
from app import store as store_module
from app.generator import build_field


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path, monkeypatch):
    from app import ingestion
    monkeypatch.setattr(ingestion, "DATA_ROOT", tmp_path)
    repository = store_module.Store(f"sqlite:///{tmp_path/'test.db'}")
    monkeypatch.setattr(store_module, "_store", repository)
    field, _ = build_field()
    for well in field["wells"]: repository.put("well", well)
    return repository
