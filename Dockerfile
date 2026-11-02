# The ML image: pipeline steps (called by Airflow) and the matching service.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY config ./config
COPY dbt ./dbt
COPY migrations ./migrations
# editable, so config/, dbt/ and migrations/ are found next to the source
RUN pip install --no-cache-dir -e ".[dev]"
ENV MLFLOW_DISABLE_AGENT_HINT=1 PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "mma.serve.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
