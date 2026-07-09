FROM python:3.11-slim

WORKDIR /app

COPY apps/api/pyproject.toml .
COPY PRD_SCHEMA.json .
RUN pip install --no-cache-dir -e ".[dev]"

COPY apps/api/app/ ./app/
COPY apps/api/tests/ ./tests/

ENV PYTHONPATH=/app
ENV PORT=8000

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
