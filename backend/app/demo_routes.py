"""Isolated acceptance demonstrations; never alters another well's replay."""
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .live_routes import LOCK, require, reset_session, advance, quality, reevaluate, AdvanceRequest, FailureRequest

router = APIRouter(prefix="/api")


@router.get("/demo/session")
def default_session():
    from .config import get_settings
    from .store import repository
    config = repository().get("demo_config", "DEMO-CONFIG")
    return {"enabled": get_settings().demo_mode, "session_id": config["session_id"] if config and get_settings().demo_mode else None}


class DemoScenario(BaseModel):
    session_id: str
    scenario: Literal["RESET", "ELEVATED", "STALE_FLOW", "RECOVER", "PASSED"]


@router.post("/demo/scenario")
def scenario(request: DemoScenario):
    with LOCK:
        session = require("live_session", request.session_id)
        if session["well_id"] != "SYN-DEMO-ACTIVE": raise HTTPException(422, "Scenario controls require the isolated synthetic demo")
        reset_session(session)
        if request.scenario == "RESET": return reevaluate(session["id"])
        advance(session["id"], AdvanceRequest(frames=7))
        if request.scenario == "ELEVATED": return reevaluate(session["id"])
        quality(session["id"], FailureRequest(channel="flow_out_l_min", quality="STALE"))
        blocked = advance(session["id"], AdvanceRequest(frames=3))
        if request.scenario == "STALE_FLOW": return blocked
        if request.scenario == "RECOVER":
            quality(session["id"], FailureRequest(channel="flow_out_l_min", quality="FRESH"))
            return advance(session["id"], AdvanceRequest(frames=3))
        return advance(session["id"], AdvanceRequest(frames=6))
