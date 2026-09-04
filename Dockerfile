# Dockerfile — v3: pure-python VLESS relay (no xray binary needed).
# Author: OpenCode
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 DATA_DIR=/data PORT=8080
RUN useradd -u 1000 -m appuser
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY static/ ./static/
RUN mkdir -p /data && chown -R appuser:appuser /data /app
USER appuser
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\",\"8080\")}/api/health')"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--ws", "websockets-sansio"]
