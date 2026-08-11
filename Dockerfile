FROM python:3.12-slim

WORKDIR /app

# System deps kept minimal — the RLM 'local' REPL runs in-process; if you
# switch RLM_ENVIRONMENT_KIND to 'docker' in production for true multi-tenant
# isolation, this image also needs the Docker CLI + socket mount (see README
# security note) or you run the REPL sandboxing on a separate node pool.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
