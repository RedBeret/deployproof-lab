BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS inventory_items (
    sku text PRIMARY KEY,
    name text NOT NULL,
    quantity integer NOT NULL CHECK (quantity >= 0),
    warehouse text NOT NULL
);

INSERT INTO schema_migrations (version)
VALUES ('001')
ON CONFLICT (version) DO NOTHING;

COMMIT;
