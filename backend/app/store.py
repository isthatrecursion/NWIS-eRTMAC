"""Persistent prototype repository; works with SQLite or PostgreSQL."""
from sqlalchemy import Column, MetaData, String, Table, Text, create_engine, delete, select, text
import json
from .config import get_settings

metadata = MetaData()
records = Table("nwis_records", metadata,
    Column("kind", String(40), primary_key=True),
    Column("id", String(80), primary_key=True),
    Column("payload", Text, nullable=False))


class Store:
    def __init__(self, url=None):
        self.engine = create_engine(url or get_settings().database_url,
            connect_args={"check_same_thread": False} if (url or get_settings().database_url).startswith("sqlite") else {})
        from .migrate import upgrade
        upgrade(self.engine)

    def put(self, kind, record):
        from .domain.units import enrich
        from .domain.runtime import validate_record
        parent = self.get("document", record["document_id"]) if record.get("document_id") else None
        parent_well_id = record.get("well_id", record.get("active_well_id"))
        if parent is None and parent_well_id:
            parent = self.get("well", parent_well_id)
        record = validate_record(kind, enrich(record,
            parent.get("synthetic_flag", parent.get("synthetic")) if parent else None,
            parent.get("datum", "UNKNOWN") if parent else "UNKNOWN"))
        with self.engine.begin() as connection:
            connection.execute(delete(records).where(records.c.kind == kind, records.c.id == record["id"]))
            connection.execute(records.insert().values(kind=kind, id=record["id"], payload=json.dumps(record)))
        return record

    def get(self, kind, key):
        with self.engine.connect() as connection:
            value = connection.execute(select(records.c.payload).where(records.c.kind == kind, records.c.id == key)).scalar()
        if not value:
            return None
        from .domain.units import enrich
        return enrich(json.loads(value))

    def all(self, kind):
        with self.engine.connect() as connection:
            values = connection.execute(select(records.c.payload).where(records.c.kind == kind).order_by(records.c.id)).scalars().all()
        from .domain.units import enrich
        return [enrich(json.loads(value)) for value in values]

    def save_spatial_path(self, well, path):
        if self.engine.dialect.name != "postgresql": return
        wkt = "LINESTRING Z ("+", ".join(f"{p['x_m']} {p['y_m']} {p['tvd_m']}" for p in path)+")"
        with self.engine.begin() as connection:
            connection.execute(text("""INSERT INTO nwis_trajectories(well_id,crs,datum,algorithm_version,geom)
                VALUES (:id,:crs,:datum,:version,ST_GeomFromText(:wkt,0))
                ON CONFLICT(well_id) DO UPDATE SET geom=excluded.geom, algorithm_version=excluded.algorithm_version,
                crs=excluded.crs, datum=excluded.datum"""),
                {"id": well["id"], "crs": well["crs"], "datum": well["datum"], "version": path[0]["algorithm_version"], "wkt": wkt})


_store = None


def repository():
    global _store
    if _store is None:
        _store = Store()
    return _store
