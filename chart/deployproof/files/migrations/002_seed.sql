BEGIN;

DELETE FROM inventory_items;

INSERT INTO inventory_items (sku, name, quantity, warehouse) VALUES
    ('DP-1001', 'Field router', 12, 'west'),
    ('DP-1002', 'Rugged switch', 8, 'west'),
    ('DP-1003', 'Console cable', 40, 'central'),
    ('DP-1004', 'SFP module', 24, 'central'),
    ('DP-1005', 'Edge appliance', 6, 'east'),
    ('DP-1006', 'Recovery drive', 10, 'east');

INSERT INTO schema_migrations (version)
VALUES ('002')
ON CONFLICT (version) DO NOTHING;

COMMIT;
