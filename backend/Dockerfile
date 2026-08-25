FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Serve only. The schema is brought up to date by `alembic upgrade head`, run
# as the platform's pre-deploy command (see railway.json) -- once per deploy,
# rather than on every container start, and while the old container is still
# serving. Does NOT run the seed script: that is destructive and compose-only.
#
# Honors the platform-injected $PORT (falls back to 8000 for local runs). Shell
# form so the variable is expanded at container start.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
