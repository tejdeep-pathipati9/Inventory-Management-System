# Inventory Management System

A small hardware-store app for products, stock, sales, and reports. It uses SQLite.
If a stock change or sale fails, none of its changes are saved.

## Run

Requires Python 3.12+ and SQLite 3.37+ for `STRICT` tables.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python seed_db.py
python main.py
```

Seed once to load sample data. Enter prices like `15.99`; they are stored as whole
cents and displayed with two decimals.

The default database is `inventory.db` next to the code. To use another file locally:

```bash
mkdir -p data
export INVENTORY_DB="$PWD/data/inventory.db"
```

## Tests

```bash
python -m pytest -q
python -m ruff check .
```

Test results inside the 1.1.0 Docker image:

```text
.........................................                                [100%]
41 passed in 0.05s
All checks passed!
```

## Expected sample reports

These are the results with fresh sample data. Revenue uses the price saved on each sale.

**Stock value by supplier**, highest first:

| Supplier | Value |
| --- | ---: |
| Bolt and Nut Supply | $309.45 |
| Forge Tools | $277.80 |
| Everyday Hardware | $185.59 |
| Clearflow Plumbing | $140.78 |

**Low stock**, including products exactly at their reorder level:

| SKU | Stock | Reorder level | Units short |
| --- | ---: | ---: | ---: |
| BLT-001 | 5 | 5 | 0 |
| TAP-001 | 3 | 5 | 2 |
| SCR-001 | 2 | 5 | 3 |

**Sales by product**, highest revenue first:

| SKU | Units sold | Revenue |
| --- | ---: | ---: |
| HAM-001 | 2 | $31.98 |
| NAI-001 | 5 | $24.95 |
| SCR-001 | 2 | $13.98 |
| WRE-001 | 1 | $12.99 |
| SCW-001 | 2 | $11.98 |
| PLI-001 | 1 | $10.99 |
| BLT-001 | 1 | $7.99 |
| NUT-001 | 2 | $7.98 |
| PVC-001 | 2 | $4.98 |
| TAP-001 | 1 | $1.99 |
| VAL-001 | 0 | $0.00 |
| WAS-001 | 0 | $0.00 |

**Never sold:** VAL-001 (Ball Valve) and WAS-001 (Rubber Washers).

## Failed sale example

Product 1 has 10 units; product 2 has 2. The first line succeeds, but the second
asks for more stock than is available:

```python
record_sale(connection, [(1, 1), (2, 999)], created_at="2026-11-03T12:00:00+00:00")
```

Recorded result:

```text
Before: stock=[(1, 10), (2, 2)]; sales=5, sale_items=12, stock_movements=0
IntegrityError: CHECK constraint failed: quantity >= 0
After: stock=[(1, 10), (2, 2)]; sales=5, sale_items=12, stock_movements=0
Entire database unchanged: True
```

The whole database was unchanged, including the sale, its lines, stock, and movements.

## Docker

The Git release tags are `v1.0.0` and `v1.1.0`. The Docker image tags below are
local images named `inventory-management:1.0.0` and `inventory-management:1.1.0`.

Open Docker Desktop. Run these from the project folder. Build each image from its
matching Git release tag:

```bash
git fetch origin --tags
git archive v1.0.0 | docker build -t inventory-management:1.0.0 -
git archive v1.1.0 | docker build -t inventory-management:1.1.0 -
docker volume create inventory-data
docker run --rm -v inventory-data:/data inventory-management:1.0.0 python seed_db.py
docker run -it --rm \
  -e INVENTORY_DB=/data/inventory.db \
  -v inventory-data:/data \
  inventory-management:1.0.0
```

Seed only once. If your folder already contains the pre-banner code, you can use
`docker build -t inventory-management:1.0.0 .` instead of the archive command.
Both images use Python `3.12.16-slim-bookworm`.

Build output excerpt:

```text
#9 [5/6] COPY . .
#9 DONE 0.0s
#10 [6/6] RUN mkdir -p /data
#10 DONE 0.1s
#11 DONE 0.1s
```

The **1.0.0 image** has no startup banner. The **1.1.0 image** adds the count and
renames `database.py` to `inventory_db.py`. Both use the same database schema.

### Persistence

Exit 1.0.0, then start 1.1.0 with the same volume. Don't seed again.

```bash
docker run -it --rm \
  -e INVENTORY_DB=/data/inventory.db \
  -v inventory-data:/data \
  inventory-management:1.1.0
```

The banner should show **3** low-stock products. Restock (**6**) product **1** by **5**,
then exit (**0**). Run the menu command again and look up (**2**) product **1**.
Recorded result from the isolated verification volume:

```text
Product ID: Amount to add: Stock is now 15.
Version 1.1.0: product 1 quantity: 15
Row counts: {'suppliers': 4, 'products': 12, 'sales': 5, 'sale_items': 12, 'stock_movements': 1}
```

The container is removed on exit; the volume keeps the data.

## Backup and restore

Choose **13**, then enter `/data/backups` in Docker or `backups` locally.
The backup is named `inventory-YYYY-MM-DD.db`. Backing up twice on the same day
replaces that day's file, so keep a copy elsewhere too.

Exit the menu before restoring. Replace the example filename below with yours:

```bash
docker run --rm -i -v inventory-data:/data inventory-management:1.1.0 python - <<'PY'
from contextlib import closing
from pathlib import Path
from inventory_db import connect
from seed_db import _row_counts

backup_path = Path("/data/backups/inventory-2026-11-04.db")
if not backup_path.is_file():
    raise SystemExit("Backup file not found; check the filename before restoring.")
with closing(connect()) as original, closing(connect(backup_path)) as backup:
    integrity = backup.execute("PRAGMA integrity_check").fetchone()[0]
    print("Integrity:", integrity)
    print("Original counts:", _row_counts(original))
    print("Backup counts:", _row_counts(backup))
    assert integrity == "ok"
    backup.backup(original)
PY
```

Recorded backup check and restore test, after temporarily setting product 1's stock to zero:

```text
Integrity: ok
Original counts: {'suppliers': 4, 'products': 12, 'sales': 5, 'sale_items': 12, 'stock_movements': 1}
Backup counts: {'suppliers': 4, 'products': 12, 'sales': 5, 'sale_items': 12, 'stock_movements': 1}
Before restore: 0
After restore: 15
Full database restored: True
```

For a local restore, run the Python code with `python` and your local backup path.
It replaces the database selected by `INVENTORY_DB` (or the default). Restart the menu afterward.

## Rollback

Stop 1.1.0 and start 1.0.0 with the same volume:

```bash
docker run -it --rm \
  -e INVENTORY_DB=/data/inventory.db \
  -v inventory-data:/data \
  inventory-management:1.0.0
```

Look up product 1. The banner should be gone, but its stock should still be **15**.
Recorded result:

```text
Version 1.0.0 rollback: product 1 quantity: 15
Row counts: {'suppliers': 4, 'products': 12, 'sales': 5, 'sale_items': 12, 'stock_movements': 1}
```

The full database fingerprint also matched. To return to 1.1.0, run that image with the same volume.

## Self-review

Keeping the database code separate from the menu made testing easier. The failed-sale
test checks the whole database, so it catches leftover sale lines or movements as
well as incorrect stock. Saving the price on each sale item also keeps old sales
correct when a product's price changes.

If I started again, I would decide on module and function names earlier. Renaming
the database module late meant changing imports across several files. I would also
give each report its own display function instead of tying its formatting to a menu number.

I would ask a reviewer to check what happens when a stock function runs during an
existing transaction. That is the part I would want checked most carefully. Backups
could also be improved: two made on the same day currently replace each other.
Keeping multiple copies and adding a restore option would be useful next steps.
