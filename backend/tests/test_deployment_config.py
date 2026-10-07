from app.config import Settings


def test_railway_database_url_uses_installed_psycopg_driver(monkeypatch):
    monkeypatch.delenv("NWIS_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db:5432/nwis")
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql+psycopg://user:pass@db:5432/nwis"


def test_explicit_database_url_takes_precedence(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db:5432/unused")
    monkeypatch.setenv("NWIS_DATABASE_URL", "sqlite+pysqlite:///./chosen.db")
    settings = Settings(_env_file=None)
    assert settings.database_url == "sqlite+pysqlite:///./chosen.db"


def test_sqlite_defaults_to_data_root(monkeypatch, tmp_path):
    monkeypatch.delenv("NWIS_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("NWIS_DATA_ROOT", str(tmp_path))
    settings = Settings(_env_file=None)
    assert settings.database_url == f"sqlite+pysqlite:///{(tmp_path / 'nwis.db').as_posix()}"


def test_empty_database_variables_fall_back_to_persistent_sqlite(monkeypatch, tmp_path):
    monkeypatch.setenv("NWIS_DATABASE_URL", "")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("NWIS_DATA_ROOT", str(tmp_path))
    settings = Settings(_env_file=None)
    assert settings.database_url == f"sqlite+pysqlite:///{(tmp_path / 'nwis.db').as_posix()}"
