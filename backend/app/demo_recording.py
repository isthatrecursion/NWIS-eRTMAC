"""Backup video of actual deterministic API traces, with an explicitly illustrative UI."""
import json
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
from fastapi.testclient import TestClient
from .main import app
from .store import Store
from . import store as store_module
from .generator import build_field


def main():
    output=Path(__file__).resolve().parents[2]/"docs/demo_media"
    output.mkdir(parents=True,exist_ok=True)
    previous=store_module._store
    temporary=tempfile.TemporaryDirectory(prefix="nwis-backup-")
    isolated=Store("sqlite+pysqlite:///"+str(Path(temporary.name)/"trace.db").replace("\\","/"))
    field,_=build_field()
    for well in field["wells"]:isolated.put("well",well)
    store_module._store=isolated
    try:
        client=TestClient(app)
        response=client.post("/api/replay/demo");response.raise_for_status()
        run=response.json()["session"]["id"]
        trace=[]
        for stage in ("RESET","ELEVATED","STALE_FLOW","RECOVER","PASSED"):
            response=client.post("/api/demo/scenario",json={"session_id":run,"scenario":stage});response.raise_for_status()
            trace.append({"stage":stage,"response":response.json()})
    finally:
        store_module._store=previous
        isolated.engine.dispose()
        temporary.cleanup()
    (output/"backup-trace.json").write_text(json.dumps(trace,indent=2),encoding="utf-8")
    path=output/"backup-demonstration.mp4"
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*"mp4v"),10,(1280,720))
    if not writer.isOpened():raise RuntimeError("Local MP4 encoder unavailable; trace JSON remains available")
    def font(size):return ImageFont.truetype("C:/Windows/Fonts/arial.ttf",size)
    for index,item in enumerate(trace):
        record=item["response"];assessment=record["assessment"];live=assessment["corroboration"];context=record["context"]
        image=Image.new("RGB",(1280,720),"#f6f5ef");draw=ImageDraw.Draw(image)
        draw.rectangle((0,0,1280,80),fill="#172c40")
        draw.text((40,20),"NWIS | Recorded deterministic simulation",fill="white",font=font(32))
        draw.text((40,100),"API-derived backup walkthrough; illustrative display, not a screen recording",fill="#555555",font=font(22))
        draw.text((40,155),item["stage"].replace("_"," "),fill="#172c40",font=font(40))
        facts=[f"FACT replay: {context['bit_md_m']} m MD | {context['formation_id']}",f"COMPUTED historical state: {assessment['historical']['state']}",f"COMPUTED current advisory: {live['state']}",f"FACT flow-out quality: {context['channels']['flow_out_l_min']['quality_status']}",f"Warning permitted by deterministic gates: {live['warning_allowed']}",f"Support / counter / unknown: {assessment['historical']['support_count']} / {assessment['historical']['counter_count']} / {assessment['historical']['unknown_count']}"]
        for row,text in enumerate(facts):draw.text((40,225+row*50),text,fill="#a3442a" if "STALE" in text else "#172c40",font=font(26))
        draw.text((40,560),"Stale flow blocks escalation; restored fresh samples permit corroboration.",fill="#172c40",font=font(25))
        draw.text((40,610),"Synthetic acceptance fixture. No rig write-back. No field accuracy claim.",fill="#555555",font=font(22))
        draw.rectangle((40,670,40+(index+1)/len(trace)*1200,680),fill="#758b73")
        frame=cv2.cvtColor(np.array(image),cv2.COLOR_RGB2BGR)
        for _ in range(80):writer.write(frame)
    writer.release()
    check=cv2.VideoCapture(str(path));count=int(check.get(cv2.CAP_PROP_FRAME_COUNT));check.release()
    if count!=400:raise RuntimeError("Backup video verification failed")
    print(json.dumps({"video":str(path),"frames":count,"seconds":40,"trace":str(output/"backup-trace.json")}))


if __name__ == "__main__":main()
