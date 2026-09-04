# Dockerfile — multi-stage: python deps + xray binary + slim runtime.
# Author: OpenCode

# ---- stage 1: python deps ----
FROM python:3.11-slim AS pydeps
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/pkg -r requirements.txt

# ---- stage 2: xray binary ----
ARG XRAY_VERSION=26.3.27
FROM alpine:3.20 AS xraydl
ARG XRAY_VERSION
RUN apk add --no-cache unzip curl && \
    curl -fsSL --retry 5 --retry-delay 2 --retry-all-errors \
      -o /tmp/x.zip "https://github.com/XTLS/Xray-core/releases/download/v${XRAY_VERSION}/Xray-linux-64.zip" && \
    unzip -o /tmp/x.zip -d /xray xray && chmod +x /xray/xray

# ---- stage 3: final ----
FROM python:3.11-slim
ARG XRAY_VERSION
ENV PYTHONUNBUFFERED=1 DATA_DIR=/data PORT=8080 XRAY_VERSION=${XRAY_VERSION}
RUN useradd -u 1000 -m appuser
WORKDIR /app
COPY --from=pydeps /pkg /usr/local
COPY --from=xraydl /xray/xray /usr/local/bin/xray
COPY app/ ./app/
COPY static/ ./static/
COPY alembic/ ./alembic/
RUN mkdir -p /data && chown -R appuser:appuser /data /app
USER appuser
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\",\"8080\")}/api/health')"
ENTRYPOINT ["python", "-m", "app.main"]
