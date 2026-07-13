FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Honor Railway's injected $PORT (falls back to 8000 for local runs). Uses the
# shell form so the variable is expanded at container start. Does NOT run the
# destructive seed script — that is dev/compose-only.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]

