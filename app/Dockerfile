ARG PYTHON_IMAGE=python:3.12.11-slim
FROM ${PYTHON_IMAGE}

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --system deployproof \
    && useradd --system --gid deployproof --home-dir /app deployproof

COPY deployproof_api ./deployproof_api

USER deployproof
EXPOSE 8080

CMD ["uvicorn", "deployproof_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
