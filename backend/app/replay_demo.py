"""Deterministic, isolated synthetic acceptance fixture. Never verifies user documents."""
from copy import deepcopy
from .ingestion import ingest


def install_demo(store):
    well = deepcopy(store.get("well", "SYN-ACTIVE-01"))
    well.update(id="SYN-DEMO-ACTIVE", name="Synthetic mud-loss demonstration", x_m=well["x_m"]+100000,
                synthetic_flag=True, drilled_year=2026, drilling_technology="SYNTHETIC_ROTARY",
                pressure_context={"pore_pressure_kpa": 25000}, operating_context={})
    well["mud_program"].update(ecd_sg=1.19, mud_weight_sg=1.16)
    for formation in well["formations"]: formation["uncertainty_m"] = 5
    store.put("well", well)
    for index in range(4):
        offset = deepcopy(well)
        offset.update(id=f"SYN-DEMO-OFFSET-{index+1}", name=f"Synthetic demo offset {index+1}", status="OFFSET", held_out=False)
        store.put("well", offset)
        text = "SYNTHETIC DAILY DRILLING REPORT\nFormation: Tipam\nOperation: DRILLING\nDatum: LOCAL_KB\nCoverage: 2200 m to 2580 m MD\nMud weight: 1.16 sg\nECD: 1.19 sg\nHole size: 8.5 in\n"
        text += "At 2490 m to 2500 m MD, severe mud loss observed.\nMitigation: LCM pill pumped.\nOutcome: returns improved.\n" if index < 2 else "No mud loss observed during the covered drilling interval.\n"
        doc = ingest(store, text.encode(), f"synthetic-demo-{index+1}.txt", offset["id"], True, doc_type="DDR")
        # These literal fixture documents have independently asserted known coverage; this is not a user review bypass.
        for kind, keys in (("coverage", doc["coverage_ids"]), ("event", doc["event_ids"])):
            for key in keys:
                item = store.get(kind, key)
                before = deepcopy(item)
                item["coverage_status" if kind == "coverage" else "review_status"] = "VERIFIED"
                item["reviewer"] = "SYNTHETIC_DEMO_FIXTURE_VERIFIER"
                store.put(kind, item)
                store.put("audit", {"id": "DEMO-AUDIT-"+key, "timestamp": "2026-01-15T00:00:00+00:00", "reviewer": item["reviewer"], "action": "synthetic_fixture_acceptance", "entity_id": key, "before": before, "after": item})
        for task in store.all("review"):
            if task["document_id"] == doc["id"]:
                task["status"] = "RESOLVED"; store.put("review", task)
        doc["review_status"] = "VERIFIED"; store.put("document", doc)
    depths = [2050, 2200, 2250, 2300, 2350, 2400, 2430, 2450, 2460, 2470, 2480, 2490, 2500, 2510, 2530, 2580, 2600]
    frames = []
    for index, depth in enumerate(depths):
        loss = max(0, index-7)
        values = {"bit_md_m": depth, "hole_md_m": 2700, "operation_state": "DRILLING", "flow_in_l_min": 950,
                  "flow_out_l_min": 870 if index >= 7 else 945, "pit_volume_m3": 410-loss*.2,
                  "ecd_sg": 1.19, "mud_weight_sg": 1.16+min(loss, 3)*.001, "wob_kn": 90, "rpm": 120,
                  "rop_m_h": 20, "hole_section_in": 8.5, "torque_kn_m": 12, "hookload_kn": 1200, "standpipe_pressure_kpa": 18000, "gas_pct": .5}
        frames.append({"elapsed_s": index*10, "values": values})
    dataset = {"id": "CSV-SYNTHETIC-MUD-LOSS-DEMO-V2", "frames": frames, "frame_count": len(frames),
               "source": "SYNTHETIC_LABEL_FREE_ACCEPTANCE_DEMO", "simulation": True, "synthetic_flag": True}
    store.put("replay_dataset", dataset)
    return well, dataset
