# Deploying to Railway

Two services and two managed resources:

| Component | What it is |
|---|---|
| **api** | `backend/`, Dockerfile build. FastAPI + the public share pages. |
| **web** | `frontend-v2/`, Dockerfile build. The Vite bundle, served by nginx. |
| **Postgres** | Railway plugin. Supplies `DATABASE_URL`. |
| **Bucket** | Railway object storage. Holds uploaded recipe images. |

The two services get separate domains, which is why several variables below
exist at all: the API has to be told the frontend's origin (CORS, email links),
the frontend has to be told the API's origin at *build* time, and the session
cookie has to be marked cross-site.

## Schema

`alembic upgrade head` runs as the api service's **pre-deploy command**
(`backend/railway.json`), so it runs once per deploy, while the previous
container is still serving, and a failed migration fails the deploy rather than
starting a service whose code expects columns the database does not have. The
app itself never creates tables.

Note that this lives in `railway.json`, not in the Dockerfile: running the image
outside Railway does **not** migrate. Do it yourself with
`alembic upgrade head` from `backend/`.

On a brand-new database the migrations build the schema and the app's startup
bootstrap seeds reserved usernames and system tags. Nothing else is needed —
`scripts/seed_testing_data.py` is **destructive**, is excluded from the
production image, and refuses to run without `ALLOW_DESTRUCTIVE_SEED=1`.

See `backend/migrations/README.md` for the schema-change workflow.

## Images

Uploads go to the bucket when `AWS_S3_BUCKET_NAME` is set, and to a local
`media/` directory otherwise (`backend/storage.py`). The platform filesystem is
**ephemeral**: without the bucket configured, every uploaded image is lost on the
next deploy. Configure the bucket before anyone uploads anything.

### Service settings live in the dashboard, not in a file

The api service deliberately has **no `railway.json`**. Railway treats a
committed config file as the source of truth and greys the corresponding
controls out in the dashboard, which made the region unchangeable there. These
settings are therefore configured on the service itself and are edited in the
dashboard:

| Setting | Value | Why it matters |
|---|---|---|
| Region | `europe-west4` (Amsterdam) | Co-located with Postgres; a split would put every query across the Atlantic. |
| Root directory | `/backend` | |
| Pre-deploy command | `alembic upgrade head` | **The only thing that migrates the database.** If this is ever cleared, deploys will start against a stale schema. |
| Healthcheck path | `/health` | |
| Replicas | `1` | Rate limiting is in-process; see below. |
| Restart policy | `ON_FAILURE`, max 3 | |

The trade-off is that these are no longer version-controlled, so they are
recorded here instead. Check them after any significant Railway change.

## Variables — api

| Var | Value | Why |
|---|---|---|
| `DATABASE_URL` | reference to the Postgres service | Required; the app refuses to start without it. |
| `JWT_SECRET` | a fresh random secret | Required. Never reuse the compose default — anyone holding it can forge sessions. |
| `PUBLIC_BASE_URL` | `https://<api-domain>` | The origin share links are built on. Left empty it falls back to the request `Host`, which is attacker-controlled. |
| `ALLOWED_HOSTS` | `<api-domain>,healthcheck.railway.app,${{RAILWAY_PRIVATE_DOMAIN}}` | `TrustedHostMiddleware`. Unset means `*`, and a forged `Host` yields a share link on someone else's origin that the sharer then forwards. **The two extra hosts are required** -- see below. |
| `ALLOWED_ORIGINS` | `https://<web-domain>` | CORS allowlist. |
| `FRONTEND_URL` | `https://<web-domain>` | Where verification and password-reset links point. |
| `COOKIE_SECURE` | `1` | The refresh cookie is HTTPS-only. |
| `COOKIE_SAMESITE` | `none` | Required while api and web are different registrable domains, or the refresh cookie is not sent and every session ends on page reload. Requires `COOKIE_SECURE=1`. |
| `MAIL_BACKEND` | `resend` | Default is `console`, which prints links to the log and sends nothing. **Not `smtp`** -- see below. |
| `RESEND_API_KEY` | Resend API key | |
| `MAIL_FROM` | a Resend-verified sender | |
| `AWS_*` | from the bucket | Image storage. |
| `GOOGLE_CLIENT_ID` | OAuth client id | Optional; omit to disable Google sign-in. |

**Must stay unset:** `AUTH_DEV_MODE` (makes the JWT secret a publicly-known
constant) and `ALLOW_DESTRUCTIVE_SEED` (unlocks a full database wipe).

### Railway blocks outbound SMTP

`MAIL_BACKEND=smtp` cannot work on Railway. Ports 25, 465 and 587 are blocked
outbound to prevent spam abuse, so the connection to the mail provider times out
after ~2 minutes and `POST /auth/register` returns a 500 with
`TimeoutError: [Errno 110] Connection timed out` in the log. From the browser
this looks like the signup button doing nothing at all.

Use `MAIL_BACKEND=resend`, which posts to Resend's REST API over ordinary HTTPS
on 443. The `smtp` backend is kept for environments that do permit outbound SMTP
(and for anyone self-hosting elsewhere).

### The healthcheck needs its own host

Railway's healthcheck does not probe the public domain -- it reaches the
container over the internal network with its own `Host` header. Setting
`ALLOWED_HOSTS` to just the public domain therefore makes `TrustedHostMiddleware`
answer the probe with `400 Invalid host header`, the healthcheck never passes,
and the deploy fails with *"1/1 replicas never became healthy"* even though the
app started correctly and the migration ran. The runtime log shows the tell:
`GET /health HTTP/1.1" 400 Bad Request`.

Including `healthcheck.railway.app` and `${{RAILWAY_PRIVATE_DOMAIN}}` fixes it
and costs nothing: the forged-Host attack this variable exists to stop is
already closed independently by `PUBLIC_BASE_URL`, which is what share links are
actually built from. `ALLOWED_HOSTS` is defence in depth, not the only defence.

Note also that Railway's edge rejects an unknown `Host` with a 404 before the
request reaches the app at all, so the allowlist is the second line, not the
first.

## Variables — web

These are **build** variables. Vite inlines them into the bundle at build time;
setting them at runtime does nothing.

| Var | Value |
|---|---|
| `VITE_API_BASE_URL` | `https://<api-domain>` |
| `VITE_GOOGLE_CLIENT_ID` | same client id as the api, if used |

Because each service needs the other's domain, the first deploy is a two-pass
operation: deploy to obtain the generated domains, fill in the cross-references,
redeploy.

## Backups

Enable Railway's Postgres backups and **restore one to a scratch database once**
before inviting testers. An untested backup is not a backup.

## Operational notes

- **Do not scale the api past one replica.** Rate limiting (`backend/ratelimit.py`)
  uses in-process counters; a second replica halves every limit and makes them
  unpredictable. `railway.json` pins `numReplicas: 1`.
- `/health` is the healthcheck. It is deliberately a pure liveness probe and does
  not touch the database, so a transient database blip cannot get a healthy
  container killed.
- Every request logs one JSON line (method, path, query *keys*, status,
  duration) to Railway's log view. Query values are never logged — they carry
  verification and reset tokens.
- `/docs` and `/redoc` are publicly reachable. They carry `X-Robots-Tag:
  noindex, nofollow` but are not access-controlled.
- The legacy `/plan` routes remain registered alongside `/meal-plans`; removal is
  scheduled no earlier than 2026-10-01.
- The `refresh_tokens` table has no expired-row cleanup yet. Harmless at alpha
  scale; it needs a sweep before any wider release.
