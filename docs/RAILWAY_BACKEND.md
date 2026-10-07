# Railway backend deployment

This repository contains two Dockerfiles. Railway can build from either the repository root (`Dockerfile`) or the `backend/` root (`backend/Dockerfile`). Both now listen on Railway's `PORT`; their non-Railway defaults are 7860 and 8000 respectively. Leave the Railway Start Command empty so the Dockerfile command runs.

## Railway service

1. Connect the repository to a Railway service. Set its Root Directory to `/backend` for the smaller build context, or leave it at `/` to use the root Dockerfile. Do not use `/frontend` for the API service.
2. Set the healthcheck path to `/health` and generate a public domain for the API.
3. Set `NWIS_CORS_ORIGINS` to the exact Vercel origin, for example `https://your-project.vercel.app` (no path or trailing slash). Add other origins as comma-separated values only if needed.
4. Set `NWIS_ENVIRONMENT=demo` and `NWIS_DEMO_MODE=true`. The application generates synthetic demonstration records during startup; it is not an authenticated production service. Do not upload private field reports to a public deployment.
5. Choose storage below. The app writes generated reports, review data and other files under `/app/storage`; this directory needs a Railway volume if those files must survive redeploys.

### Simplest persistent demonstration: SQLite

Attach a Railway volume to the API service with mount path `/app/storage`. Set `NWIS_DATA_ROOT=/app/storage`. Leave both `NWIS_DATABASE_URL` and `DATABASE_URL` unset. The application will then use `/app/storage/nwis.db`. Use one service replica; this mode is for the synthetic evaluator demo.

### PostgreSQL/PostGIS

Use a PostgreSQL service with the PostGIS extension installed. Railway's standard PostgreSQL image does not include PostGIS; use its PostGIS template or another PostGIS-capable database. Set the API service's `NWIS_DATABASE_URL` to a Railway reference to that database's `DATABASE_URL` (or set `DATABASE_URL` on the API service). `postgres://` and `postgresql://` URLs are converted to the installed `psycopg` driver. The first startup runs Alembic and `CREATE EXTENSION IF NOT EXISTS postgis`; a database without PostGIS will fail at this step. Attach a separate Railway volume to the API service at `/app/storage` for report files. Set `NWIS_DATA_ROOT=/app/storage`.

Do not configure both SQLite and PostgreSQL connection variables unless `NWIS_DATABASE_URL` is intentionally overriding `DATABASE_URL`.

## Vercel frontend

Set `VITE_API_BASE_URL` in Vercel to the Railway API origin, for example `https://your-api.up.railway.app`, then rebuild/redeploy the frontend. Vite reads this variable at build time. Without it, a production frontend sends API requests to its own Vercel origin. Check `https://your-api.up.railway.app/health` and then `https://your-api.up.railway.app/api/v1/meta` before testing the frontend.

## Reading a failed deploy

- `Application failed to respond` or failed healthcheck: confirm Railway did not override the Dockerfile Start Command, and that the process binds `0.0.0.0:$PORT`. The healthcheck is `/health`.
- `No module named psycopg2`: the database URL was not converted to `postgresql+psycopg`; deploy this version and check `NWIS_DATABASE_URL`/`DATABASE_URL`.
- `Could not parse SQLAlchemy URL from string ''`: a database variable is set to an empty value. This version treats empty values as unset and uses the volume-backed SQLite fallback when neither URL is configured.
- `extension "postgis" is not available`: the attached database is standard PostgreSQL rather than PostGIS-capable.
- `permission denied` or `unable to open database file`: check the `/app/storage` volume mount and `NWIS_DATA_ROOT`.
- Build upload is very large: ensure the `.dockerignore` belonging to the chosen build root is present; it excludes local virtual environments and generated data.

The API has write endpoints for document upload, review and replay. Its current authentication and concurrency controls have not been assessed for public field use.
