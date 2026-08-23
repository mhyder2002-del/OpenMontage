FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PUBLIC_DOMAIN=hermestudios.com \
    LM_STUDIO_BASE_URL=http://127.0.0.1:1234/v1 \
    HERMES_MAX_INFLIGHT=32 \
    HERMES_REQUIRE_AUTH=true

WORKDIR /app
COPY requirements.txt .
COPY requirements.billing.txt .
RUN pip install --no-cache-dir -r requirements.txt -r requirements.billing.txt \
    && useradd --uid 10001 --system --home-dir /app --shell /usr/sbin/nologin hermes

COPY app.py billing.py campaigns.py flywheel.py ./
COPY agents ./agents
COPY static ./static
RUN chown -R hermes:hermes /app

USER hermes
EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8080/livez', timeout=2)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
