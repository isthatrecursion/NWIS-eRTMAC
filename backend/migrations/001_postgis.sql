CREATE EXTENSION IF NOT EXISTS postgis;
CREATE TABLE IF NOT EXISTS nwis_trajectories (
    well_id text PRIMARY KEY,
    crs text NOT NULL,
    datum text NOT NULL,
    algorithm_version text NOT NULL,
    geom geometry(LineStringZ, 0) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_nwis_trajectories_geom ON nwis_trajectories USING gist (geom);
