ARG PYTHON_IMAGE=python:3.12.11-slim@sha256:47ae396f09c1303b8653019811a8498470603d7ffefc29cb07c88f1f8cb3d19f
FROM ${PYTHON_IMAGE}

ENV PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 deployproof \
    && useradd --uid 10001 --gid 10001 --no-create-home \
        --home-dir /app --shell /usr/sbin/nologin deployproof

COPY deployproof_api ./deployproof_api

ARG SOURCE_REVISION=unknown
ENV SOURCE_REVISION=${SOURCE_REVISION}

USER 10001:10001
EXPOSE 8080

CMD ["uvicorn", "deployproof_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
