from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["phase"] == "10"


def test_seed_well_contract() -> None:
    response = client.get("/api/wells/SYN-ACTIVE-01")
    assert response.status_code == 200
    assert response.json()["synthetic"] is True
