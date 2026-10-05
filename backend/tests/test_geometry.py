import math
import pytest
from app.geometry import position, project_event, separation, trajectory
from app.generator import build_field


def test_vertical_and_constant_inclination():
    vertical = trajectory([{"md_m": 0, "incl_deg": 0, "azi_deg": 0}, {"md_m": 1000, "incl_deg": 0, "azi_deg": 0}])
    assert vertical[-1]["tvd_m"] == 1000
    assert vertical[-1]["x_m"] == vertical[-1]["y_m"] == 0
    inclined = trajectory([{"md_m": 0, "incl_deg": 30, "azi_deg": 90}, {"md_m": 1000, "incl_deg": 30, "azi_deg": 90}])
    assert inclined[-1]["x_m"] == pytest.approx(500)
    assert inclined[-1]["tvd_m"] == pytest.approx(1000*math.cos(math.pi/6))


def test_curved_north_build():
    path = trajectory([{"md_m": 0, "incl_deg": 0, "azi_deg": 0}, {"md_m": 100, "incl_deg": 90, "azi_deg": 0}])
    assert path[-1]["tvd_m"] == pytest.approx(200/math.pi)
    assert path[-1]["y_m"] == pytest.approx(200/math.pi)
    assert position(path, 50)["tvd_m"] == pytest.approx(100/math.pi)


@pytest.mark.parametrize("stations", [
    [{"md_m": 5, "incl_deg": 0, "azi_deg": 0}],
    [{"md_m": 0, "incl_deg": 0, "azi_deg": 0}, {"md_m": 0, "incl_deg": 0, "azi_deg": 0}],
    [{"md_m": 0, "incl_deg": -3, "azi_deg": 0}],
])
def test_invalid_surveys(stations):
    with pytest.raises(ValueError): trajectory(stations)


def test_outside_survey_is_rejected():
    with pytest.raises(ValueError): position(trajectory([{"md_m": 0, "incl_deg": 0, "azi_deg": 0}]), 100)


def test_downhole_ranking_swap():
    field, _ = build_field()
    active, nearest, farther = field["wells"][:3]
    paths = [trajectory(w["survey"], w["x_m"], w["y_m"]) for w in (active, nearest, farther)]
    interval = [2200, 2580]
    near_distance = separation(paths[0], paths[1], interval, interval)["target_distance_m"]
    far_distance = separation(paths[0], paths[2], interval, interval)["target_distance_m"]
    assert nearest["x_m"] < farther["x_m"]
    assert far_distance < near_distance


def formation(top=1000, base=1200, uncertainty=10):
    return {"top_md_m": top, "base_md_m": base, "uncertainty_m": uncertainty, "datum": "LOCAL_KB"}


def test_fraction_projection_and_uncertainty():
    event = {"md_from_m": 1100}
    result = project_event(event, formation(), formation(2000, 2400))
    low, high = result["projected_md_interval_m"]
    assert result["strat_fraction"] == .5
    assert low < 2200 < high
    wide = project_event(event, formation(uncertainty=30), formation(2000, 2400, uncertainty=40))
    assert wide["projected_md_interval_m"][1]-wide["projected_md_interval_m"][0] > high-low


def test_pinchoff_datum_and_quarantine():
    event = {"md_from_m": 1100}
    assert project_event(event, formation(), None)["reason"] == "formation_absent"
    assert project_event(event, formation(), {**formation(), "datum": "MSL"})["reason"] == "datum_mismatch"
    assert project_event({**event, "review_status": "QUARANTINED"}, formation(), formation())["reason"] == "event_quarantined"


def test_fallback_is_wider_and_flagged():
    result = project_event({"md_from_m": 1100}, {**formation(), "base_md_m": None, "approx_thickness_m": 200}, {**formation(2000, 2400), "approx_thickness_m": 400})
    assert result["method"] == "estimated_thickness"
    assert result["alignment_confidence"] == "low"
    assert result["projected_md_interval_m"][1]-result["projected_md_interval_m"][0] >= 200


def test_only_target_base_missing_uses_source_verified_thickness():
    result = project_event({"md_from_m": 1100}, formation(), {**formation(2000, 2400), "base_md_m": None, "approx_thickness_m": 400})
    assert result["method"] == "estimated_thickness"
    assert result["projected_md_interval_m"] == [2100, 2300]
