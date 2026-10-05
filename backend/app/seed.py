from datetime import datetime, timezone

from .domain.contracts import CurrentWellContext, WellSummary, ChannelValue
from .domain.enums import Freshness, OperationState

NOW = datetime.now(timezone.utc)

ACTIVE_WELL = WellSummary(
    id="SYN-ACTIVE-01",
    name="SYN–Naharkatia A1",
    field="Synthetic Upper Assam",
    latitude=27.288,
    longitude=95.336,
    surface_x_km=0,
    surface_y_km=0,
    status="ACTIVE",
)

WELLS = [
    ACTIVE_WELL,
    WellSummary(id="SYN-NHK-01", name="SYN–Naharkatia 01", field="Synthetic Upper Assam", latitude=27.296, longitude=95.341, surface_x_km=0.8, surface_y_km=0.5, status="OFFSET"),
    WellSummary(id="SYN-MOR-03", name="SYN–Moran 03", field="Synthetic Upper Assam", latitude=27.281, longitude=95.349, surface_x_km=1.2, surface_y_km=-0.7, status="OFFSET"),
]

CONTEXT = CurrentWellContext(
    well_id=ACTIVE_WELL.id,
    timestamp=NOW,
    bit_md_m=2435,
    hole_md_m=2440,
    tvd_m=2210,
    formation_id="TIPAM",
    next_formation_id="BARAIL",
    hole_section_in=8.5,
    inclination_deg=46.2,
    operation_state=OperationState.DRILLING,
    channels={
        "flow_out": ChannelValue(value=930, unit="L/min", timestamp=NOW, source="REPLAY", freshness=Freshness.FRESH),
        "pit_volume": ChannelValue(value=410, unit="m³", timestamp=NOW, source="REPLAY", freshness=Freshness.FRESH),
        "ecd": ChannelValue(value=1.19, unit="SG", timestamp=NOW, source="REPLAY", freshness=Freshness.FRESH),
    },
)

