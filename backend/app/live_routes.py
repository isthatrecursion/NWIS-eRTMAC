"""Single-worker prototype API for explicit simulation sessions and audited alerts."""
from datetime import datetime, timezone
import hashlib
from threading import RLock
from typing import Literal
from uuid import uuid4
import asyncio
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, field_validator
from .paths import DATA_ROOT
from .store import repository
from .live import CHANNELS, Sample, ReplayAdapter, ManualAdapter, parse_csv, stamp, utc_now, freshness_threshold
from .mud_loss import assess, sync_alert, transition_alert, audit_alert

router = APIRouter(prefix="/api")
LOCK = RLock()
PLAYBACK_TASKS = {}


def require(kind, key):
    result = repository().get(kind, key)
    if result is None: raise HTTPException(404, f"{kind} not found")
    return result


class SessionRequest(BaseModel):
    well_id: str = "SYN-ACTIVE-01"
    formation: str = "TIPAM"
    md_interval_m: tuple[float, float] = (2460, 2580)
    radius_km: float = Field(default=3, gt=0, le=100, allow_inf_nan=False)
    adapter: Literal["REPLAY", "MANUAL"] = "REPLAY"
    dataset_id: str | None = None

    @field_validator("md_interval_m")
    @classmethod
    def interval(cls, value):
        import math
        if not all(math.isfinite(v) for v in value) or not 0 <= value[0] < value[1] <= 15000:
            raise ValueError("Interval requires finite increasing MD bounds")
        return value


def context_for(session):
    well = require("well", session["well_id"])
    if session["adapter"] == "MANUAL":
        return ManualAdapter(well, session.get("samples", {}), session.get("history", [])).context_at()
    dataset = require("replay_dataset", session["dataset_id"])
    return ReplayAdapter(well, dataset["frames"], session).context_at()


def evaluate_session(session, history_cache=None):
    context = context_for(session)
    assessment = assess(repository(), require("well", session["well_id"]), session, context, history_cache)
    alert = sync_alert(repository(), session, assessment) if session.get("episode_active", True) else next((a for a in repository().all("alert") if a["well_id"] == session["well_id"] and a["formation"] == session["formation"] and a["md_interval_m"] == session["md_interval_m"]), None)
    return {"session": session, "context": context, "assessment": assessment, "alert": alert}


@router.get("/replay/config")
def replay_config():
    from .config import get_settings
    return {"channels": {name: {"unit": unit, "minimum": low, "maximum": high, "freshness_threshold_s": freshness_threshold(name)} for name, (unit, low, high) in CHANNELS.items()},
            "operation_freshness_threshold_s": freshness_threshold("operation_state"),
            "mud_loss_policy": get_settings().mud_loss_policy.model_dump(), "historical_policy": get_settings().historical_policy.model_dump()}


@router.post("/replay/datasets")
def upload_csv(file: UploadFile = File(...)):
    content = file.file.read(1024*1024+1)
    try: frames = parse_csv(content)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    key = "CSV-"+hashlib.sha256(content).hexdigest()[:20]
    dataset = {"id": key, "frames": frames, "frame_count": len(frames), "source": "UPLOADED_CSV", "simulation": True}
    with LOCK: repository().put("replay_dataset", dataset)
    return {k: v for k, v in dataset.items() if k != "frames"}


@router.post("/replay/sessions")
def create_session(request: SessionRequest):
    with LOCK:
        well = require("well", request.well_id)
        if well.get("status") != "ACTIVE": raise HTTPException(422, "Simulation requires an active well")
        interval = next((f for f in well["formations"] if f["formation_id"] == request.formation), None)
        if not interval or interval.get("base_md_m") is None or not interval["top_md_m"] <= request.md_interval_m[0] < request.md_interval_m[1] <= interval["base_md_m"]:
            raise HTTPException(422, "Monitoring interval must lie within a complete active formation")
        dataset = None
        if request.adapter == "REPLAY":
            if request.dataset_id: dataset = require("replay_dataset", request.dataset_id)
            else:
                try: content = (DATA_ROOT/"runtime"/"replay.csv").read_bytes(); frames = parse_csv(content)
                except (OSError, ValueError) as exc: raise HTTPException(422, "Replay fixture unavailable; run bootstrap or upload CSV") from exc
                key = "CSV-"+hashlib.sha256(content).hexdigest()[:20]
                dataset = {"id": key, "frames": frames, "frame_count": len(frames), "source": "GENERATED_LABEL_FREE_CSV", "simulation": True, "synthetic_flag": True}
                repository().put("replay_dataset", dataset)
        session = {"id": "RUN-"+uuid4().hex[:20], "well_id": well["id"], "adapter": request.adapter,
                   "dataset_id": dataset["id"] if dataset else None, "cursor": 0,
                   "frame_count": dataset["frame_count"] if dataset else 0, "failures": {}, "quality_events": [], "samples": {}, "history": [],
                   "formation": request.formation, "md_interval_m": list(request.md_interval_m), "radius_km": request.radius_km,
                   "epoch": utc_now().isoformat(), "simulation": True, "playing": False, "speed": 1., "generation": 0}
        repository().put("live_session", session)
        return evaluate_session(session)


@router.post("/replay/demo")
def demo():
    from .replay_demo import install_demo
    with LOCK:
        well, dataset = install_demo(repository())
        result = create_session(SessionRequest(well_id=well["id"], dataset_id=dataset["id"], md_interval_m=(2460, 2520)))
        session = result["session"]
        session["epoch"] = "2026-01-15T00:00:00+00:00"
        reset_session(session)
        return evaluate_session(session)


@router.get("/replay/sessions/{session_id}")
def get_session(session_id: str):
    session = require("live_session", session_id)
    return {"session": session, "context": context_for(session)}


class AdvanceRequest(BaseModel):
    frames: int = Field(default=1, ge=1, le=100)


@router.post("/replay/sessions/{session_id}/advance")
def advance(session_id: str, request: AdvanceRequest):
    with LOCK:
        session = require("live_session", session_id)
        if session["adapter"] != "REPLAY": raise HTTPException(422, "Manual sessions cannot advance replay")
        if session.get("playing"): raise HTTPException(409, "Pause backend playback before advancing frames manually")
        end = min(session["frame_count"]-1, session["cursor"]+request.frames)
        history_cache = {}
        result = None
        for cursor in range(session["cursor"]+1, end+1):
            session["cursor"] = cursor
            result = evaluate_session(session, history_cache)
        repository().put("live_session", session)
        return result or evaluate_session(session)


class FailureRequest(BaseModel):
    channel: str
    quality: Literal["FRESH", "STALE", "MISSING", "SUSPECT"]

    @field_validator("channel")
    @classmethod
    def known(cls, value):
        if value not in (*CHANNELS, "operation_state"): raise ValueError("Unknown telemetry channel")
        return value


@router.post("/replay/sessions/{session_id}/quality")
def quality(session_id: str, request: FailureRequest):
    with LOCK:
        session = require("live_session", session_id)
        if session["adapter"] != "REPLAY": raise HTTPException(422, "Quality injection is replay-only")
        if request.quality == "FRESH": session["failures"].pop(request.channel, None)
        else: session["failures"][request.channel] = request.quality
        events = [event for event in session.get("quality_events", []) if event["cursor"] != session["cursor"]]
        session["quality_events"] = events+[{"cursor": session["cursor"], "failures": dict(session["failures"])}]
        repository().put("live_session", session)
        repository().put("simulation_audit", {"id": "SIM-"+uuid4().hex[:20], "session_id": session_id,
                            "channel": request.channel, "quality": request.quality, "timestamp": utc_now().isoformat()})
        return evaluate_session(session)


@router.post("/replay/sessions/{session_id}/evaluate")
def reevaluate(session_id: str):
    with LOCK: return evaluate_session(require("live_session", session_id))


class ManualRequest(BaseModel):
    samples: dict[str, Sample]

    @field_validator("samples")
    @classmethod
    def known(cls, value):
        if not value or set(value)-set(CHANNELS)-{"operation_state"}: raise ValueError("Supply known telemetry channels only")
        return value


@router.post("/replay/sessions/{session_id}/manual")
def manual_update(session_id: str, request: ManualRequest):
    with LOCK:
        session = require("live_session", session_id)
        if session["adapter"] != "MANUAL": raise HTTPException(422, "Select a manual session before entering samples")
        old = context_for(session)
        history = session.get("history", [])
        if session.get("samples"):
            valid = all(old["channels"][k]["quality_status"] == "FRESH" for k in ("bit_md_m", "operation_state", "flow_in_l_min", "flow_out_l_min", "pit_volume_m3", "ecd_sg"))
            history.append({"timestamp": old["timestamp"], "values": {k: v["value"] for k, v in old["channels"].items()},
                            "channel_quality": {k: v["quality_status"] for k, v in old["channels"].items()},
                            "channel_timestamps": {k: v["timestamp"] for k, v in old["channels"].items()}, "quality_status": "VALID" if valid else "SUSPECT"})
        for key, sample in request.samples.items():
            previous = session["samples"].get(key)
            if previous and sample.timestamp < stamp(previous["timestamp"]): raise HTTPException(422, "Out-of-order channel timestamp")
            session["samples"][key] = sample.model_dump(mode="json")
        session["history"] = history[-120:]
        repository().put("live_session", session)
        return evaluate_session(session)


@router.get("/alerts")
def alerts(session_id: str):
    require("live_session", session_id)
    return [a for a in repository().all("alert") if session_id in a.get("session_ids", [a["session_id"]])]


def reset_session(session):
    """An explicit restart resets the shared monitoring episode, preserving its audit."""
    for alert in repository().all("alert"):
        if alert["well_id"] == session["well_id"] and alert["formation"] == session["formation"] and alert["md_interval_m"] == session["md_interval_m"]:
            alert.update(lifecycle="RESOLVED", resolved_at=utc_now().isoformat(), snoozed_until=None)
            audit_alert(repository(), alert, "replay_episode_reset", actor="SIMULATION_CONTROL")
            alert["restart_pending"] = True
            repository().put("alert", alert)
    # Pause other observers of this same interval so an older clock cannot alter the restarted episode.
    for other in repository().all("live_session"):
        if other["well_id"] == session["well_id"] and other["formation"] == session["formation"] and other["md_interval_m"] == session["md_interval_m"]:
            other["playing"] = False
            other["episode_active"] = False
            repository().put("live_session", other)
    session.update(cursor=0, failures={}, quality_events=[], samples={}, history=[], playing=False, episode_active=True, playback_elapsed_s=None,
                   generation=session.get("generation", 0)+1, wall_anchor=None, elapsed_anchor=None)
    repository().put("live_session", session)


class ReplayControl(BaseModel):
    action: Literal["play", "pause", "speed", "reset", "seek"]
    speed: float = Field(default=1, gt=0, le=100, allow_inf_nan=False)
    cursor: int = Field(default=0, ge=0)


def tick(session):
    if not session.get("playing"): return
    frames = require("replay_dataset", session["dataset_id"])["frames"]
    elapsed = session["elapsed_anchor"]+(utc_now()-stamp(session["wall_anchor"])).total_seconds()*session["speed"]
    session["playback_elapsed_s"] = elapsed
    cache = {}
    while session["cursor"]+1 < len(frames) and frames[session["cursor"]+1]["elapsed_s"] <= elapsed:
        session["cursor"] += 1
        evaluate_session(session, cache)
    if session["cursor"] == len(frames)-1: session["playing"] = False
    repository().put("live_session", session)


async def playback_worker(session_id):
    try:
        while True:
            await asyncio.sleep(.25)
            with LOCK:
                session = require("live_session", session_id)
                if not session.get("playing"): break
                tick(session)
    finally:
        PLAYBACK_TASKS.pop(session_id, None)


@router.post("/replay/sessions/{session_id}/control")
async def control(session_id: str, request: ReplayControl):
    with LOCK:
        session = require("live_session", session_id)
        if session["adapter"] != "REPLAY": raise HTTPException(422, "Playback controls require replay")
        if request.action == "seek" and request.cursor >= session["frame_count"]: raise HTTPException(422, "Seek cursor exceeds dataset")
        tick(session)
        if request.action in ("reset", "seek"):
            reset_session(session)
            # Reevaluate each frame to reproduce escalation and interval-passed transitions.
            cache = {}
            for cursor in range((request.cursor if request.action == "seek" else 0)+1):
                session["cursor"] = cursor
                evaluate_session(session, cache)
        else:
            session["playing"] = request.action == "play" or (request.action == "speed" and session.get("playing", False))
            if request.action in ("play", "speed"): session["speed"] = request.speed
        frame = require("replay_dataset", session["dataset_id"])["frames"][session["cursor"]]
        session.update(wall_anchor=utc_now().isoformat(), elapsed_anchor=frame["elapsed_s"] if request.action in ("reset", "seek") else session.get("playback_elapsed_s") or frame["elapsed_s"])
        repository().put("live_session", session)
        result = evaluate_session(session)
        if session["playing"] and session_id not in PLAYBACK_TASKS:
            PLAYBACK_TASKS[session_id] = asyncio.create_task(playback_worker(session_id))
        return result


@router.websocket("/replay/sessions/{session_id}/stream")
async def stream(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        previous = None
        while True:
            with LOCK:
                session = require("live_session", session_id)
                signature = (session["cursor"], session.get("playing"), session.get("speed"), session.get("generation"), repr(session["failures"]))
                result = evaluate_session(session) if signature != previous else None
            if result is not None:
                await websocket.send_json(result)
                previous = signature
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=.25)
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        pass
    except HTTPException:
        await websocket.close(code=1008, reason="Session unavailable")


class AlertAction(BaseModel):
    action: Literal["acknowledge", "snooze", "resolve"]
    actor: str = Field(min_length=1, max_length=120)
    snooze_seconds: int = Field(default=60, ge=10, le=3600)

    @field_validator("actor")
    @classmethod
    def literal_actor(cls, value):
        if not value.strip(): raise ValueError("Actor name is required")
        return value.strip()


@router.post("/alerts/{alert_id}/transition")
def alert_action(alert_id: str, request: AlertAction):
    with LOCK:
        alert = require("alert", alert_id)
        context = context_for(require("live_session", alert["session_id"]))
        try: return transition_alert(repository(), alert, request.action, request.actor, stamp(context["timestamp"]), request.snooze_seconds)
        except ValueError as exc: raise HTTPException(409, str(exc)) from exc
