FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install \
      "fastapi>=0.110" \
      "uvicorn[standard]>=0.27" \
      "websockets>=12.0" \
      "httpx>=0.27" \
      "aiosqlite>=0.19" \
      "pydantic>=2.6" \
      "numpy>=1.26"

COPY app ./app
COPY static ./static

ENV SCALPER_DATA_DIR=/data \
    PORT=8080
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
