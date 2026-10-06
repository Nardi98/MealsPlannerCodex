FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Serve only. This image is what `docker-compose` builds; the Railway deployment
# uses the RAILPACK builder instead.
#
# Nothing here migrates: the schema is brought up to date by `alembic upgrade
# head`, set as the pre-deploy command in the Railway dashboard (see
# `docs/DEPLOYMENT.md`), so it runs once per deploy while the old container still
# serves. Does NOT run the seed script: that is destructive and compose-only.
#
# Honors the platform-injected $PORT (falls back to 8000 for local runs). Shell
# form so the variable is expanded at container start.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
