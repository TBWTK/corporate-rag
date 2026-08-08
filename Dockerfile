FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        fonts-dejavu-core \
        fonts-liberation \
        libreoffice-writer \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system rag && adduser --system --ingroup rag --home /app rag \
    && mkdir -p /data/uploads && chown -R rag:rag /app /data

COPY --chown=rag:rag pyproject.toml requirements.lock README.md ./
COPY --chown=rag:rag src ./src
COPY --chown=rag:rag tests ./tests
COPY --chown=rag:rag examples ./examples
COPY --chown=rag:rag certs ./certs

RUN pip install --upgrade pip \
    && pip install --requirement requirements.lock \
    && pip install --no-deps .

USER rag

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=4s --start-period=15s --retries=5 \
  CMD python -c "import json,urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)); raise SystemExit(0 if data['status']=='ok' else 1)"

CMD ["uvicorn", "rag_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
