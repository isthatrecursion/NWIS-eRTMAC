"""Fresh-stack smoke: schema version, seed, API and persisted spatial geometry."""
from sqlalchemy import text
from fastapi.testclient import TestClient
from .main import app
from .store import repository


def main():
    store = repository()
    assert store.engine.dialect.name == "postgresql", "PostgreSQL required for this smoke check"
    with store.engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0001_foundation"
        assert connection.execute(text("SELECT PostGIS_Version()")).scalar()
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        wells = client.get("/api/v1/wells").json()
        assert 20 <= len(wells) <= 40
        assert client.get("/api/v1/documents").json()
        assert client.get("/api/v1/wells/SYN-ACTIVE-01/survey").status_code == 200
    with store.engine.connect() as connection:
        assert connection.execute(text("SELECT ST_NPoints(geom) FROM nwis_trajectories WHERE well_id='SYN-ACTIVE-01'")).scalar() > 1
    print("Clean PostgreSQL/PostGIS smoke passed")


if __name__ == "__main__":
    main()
