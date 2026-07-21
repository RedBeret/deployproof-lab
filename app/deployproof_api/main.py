from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse

APP_NAME = "deployproof-inventory"
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
SOURCE_REVISION = os.getenv("SOURCE_REVISION", "local")

app = FastAPI(title="DeployProof Inventory API", version=APP_VERSION)


def configuration() -> dict[str, str]:
    return {
        "customer_region": os.getenv("CUSTOMER_REGION", "lab-west"),
        "environment": os.getenv("APP_ENVIRONMENT", "certification"),
        "feature_mode": os.getenv("FEATURE_MODE", "standard"),
    }


def sha256_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def configuration_fingerprint() -> str:
    return sha256_json(configuration())


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=int(os.getenv("PGPORT", "5432")),
        user=os.getenv("PGUSER", "deployproof"),
        password=os.getenv("PGPASSWORD", ""),
        dbname=os.getenv("PGDATABASE", "deployproof"),
        connect_timeout=2,
    )


def database_facts() -> dict[str, Any]:
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
        migrations = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT sku, name, quantity, warehouse FROM inventory_items ORDER BY sku")
        rows = cursor.fetchall()

    items = [
        {"name": row[1], "quantity": row[2], "sku": row[0], "warehouse": row[3]} for row in rows
    ]
    return {
        "data_sha256": sha256_json(items),
        "migration_version": migrations[-1] if migrations else None,
        "row_counts": {"inventory_items": len(items)},
    }


def release_payload() -> dict[str, Any]:
    return {
        "application": APP_NAME,
        "application_version": APP_VERSION,
        "configuration": configuration(),
        "configuration_sha256": configuration_fingerprint(),
        "source_revision": SOURCE_REVISION,
        **database_facts(),
    }


@app.get("/")
def root() -> dict[str, str]:
    return {"application": APP_NAME, "project": "DeployProof Lab"}


@app.get("/live")
def live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health", response_model=None)
def health() -> dict[str, str] | JSONResponse:
    try:
        facts = database_facts()
        if not facts["migration_version"]:
            raise RuntimeError("database migration is missing")
    except Exception as error:  # noqa: BLE001 - health converts dependencies to status
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "reason": error.__class__.__name__},
        )
    return {"status": "healthy"}


@app.get("/release-info", response_model=None)
def release_info() -> dict[str, Any] | JSONResponse:
    try:
        return release_payload()
    except Exception as error:  # noqa: BLE001 - endpoint must return dependency state
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "reason": error.__class__.__name__},
        )
