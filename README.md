# Inventory Management System

A Python and SQLite terminal app for managing a hardware store's products, prices, stock, and sales. It includes inventory reports, stock movement logs, and rollback for failed stock changes or sales. It also supports database backups and Docker volumes to keep data between containers.

## Run

Requires Python 3.12+ and SQLite 3.37+ for `STRICT` tables.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python seed_db.py
python main.py
```

Run the seed script once on an empty database to load sample data. Enter prices in dollars: `15.99` is stored as `1599` cents and displayed as `$15.99`.

The default database is `inventory.db` next to the code. To use another file, set `INVENTORY_DB` before seeding or starting the app:

```bash
mkdir -p data
export INVENTORY_DB="$PWD/data/inventory.db"
```

## Tests

```bash
python -m pytest -q
python -m ruff check .
```

## Expected sample reports

These results apply to freshly seeded data. Sales revenue uses the price recorded on each sale item.

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

In the sample data, product 1 has 10 units and product 2 has 2. The first sale line has enough stock, but the second asks for 999 units and causes the whole sale to roll back:

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

## Docker

Open Docker Desktop and run these commands from the project folder. Version 1.0.0 is built from Git tag `v1.0.0`, and 1.1.0 is built from the current files. The local images are named `inventory:1.0.0` and `inventory:1.1.0`.

```bash
git archive v1.0.0 | docker build --progress=plain -t inventory:1.0.0 -
docker build --progress=plain -t inventory:1.1.0 .
docker volume create inventory-data
docker run --rm -v inventory-data:/data inventory:1.0.0 python seed_db.py
docker run -it --rm \
  -e INVENTORY_DB=/data/inventory.db \
  -v inventory-data:/data \
  inventory:1.0.0
```

Both images use Python `3.12.16-slim-bookworm`. If the volume already contains inventory data, skip the seed command.

Build output from November 4, 2026, for version 1.1.0. Some dependency layers were cached, so step numbers and times may differ when you build it again.

```text
#9 [5/6] COPY . .
#9 DONE 0.0s

#10 [6/6] RUN mkdir -p /data
#10 DONE 0.1s

#11 exporting to image
#11 exporting layers 0.0s done
#11 exporting manifest sha256:d076e6d77d2c55bde0c92b8396da786bd2d6e42b8df43f532a64bf2afdb92f7a done
#11 exporting config sha256:4c3649cab611cb5f08bf55ada84379b1513d7b949b5e46af77097e65beba67b7 done
#11 exporting attestation manifest sha256:83aa6ce929527151f2a446e0149ae1e00941a3f1331b4d4063bed0c275c5d9df done
#11 exporting manifest list sha256:5d3066462eebf24b582f6c57b26303b356488f5e1256c1387a019ff02821fe29 done
#11 naming to docker.io/library/inventory:1.1.0 done
#11 unpacking to docker.io/library/inventory:1.1.0 0.0s done
#11 DONE 0.1s
```

Version 1.1.0 shows the low stock count at startup. Both versions use the same database schema.

### Persistence

Exit the 1.0.0 menu, then start 1.1.0 with the same volume:

```bash
docker run -it --rm \
  -e INVENTORY_DB=/data/inventory.db \
  -v inventory-data:/data \
  inventory:1.1.0
```

With fresh sample data, the banner shows **3** low stock products. Choose **6** to restock product **1** by **5**, then exit with **0**. Start a new container using the same command and choose **2** to look up product **1**.

The persistence check used a separate volume, `inventory-readme-check-20261104`. The output below shows the restock result and the stock and row counts read by a new container:

```text
Product ID: Amount to add: Stock is now 15.
Version 1.1.0: product 1 quantity: 15
Row counts: {'suppliers': 4, 'products': 12, 'sales': 5, 'sale_items': 12, 'stock_movements': 1}
```

The `--rm` option removes the container when it exits. The named volume keeps the database.

## Backup and restore

Choose **13** to create a backup. Enter `/data/backups` in Docker or `backups` locally. The file is named `inventory-YYYY-MM-DD.db`. A second backup in the same folder on the same day replaces the first, so keep an additional copy elsewhere.

Close the menu before restoring. Set `backup_path` below to the backup file you want to restore:

```bash
docker run --rm -i -v inventory-data:/data inventory:1.1.0 python - <<'PY'
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

For the restore check, product 1's stock was temporarily set to zero after the backup was made. Restoring the backup recovered its stock and the full database:

```text
Integrity: ok
Original counts: {'suppliers': 4, 'products': 12, 'sales': 5, 'sale_items': 12, 'stock_movements': 1}
Backup counts: {'suppliers': 4, 'products': 12, 'sales': 5, 'sale_items': 12, 'stock_movements': 1}
Before restore: 0
After restore: 15
Full database restored: True
```

For a local restore, run the Python code with `python` and set `backup_path` to your local backup file. Restoring replaces the database selected by `INVENTORY_DB`, or the default `inventory.db` if it is unset. Restart the menu after restoring.

## Rollback

Exit the 1.1.0 menu and start 1.0.0 with the same volume:

```bash
docker run -it --rm \
  -e INVENTORY_DB=/data/inventory.db \
  -v inventory-data:/data \
  inventory:1.0.0
```

After the persistence example, look up product **1** and check that its stock is still **15**. Version 1.0.0 starts without the banner. The rollback check produced:

```text
Version 1.0.0 rollback: product 1 quantity: 15
Row counts: {'suppliers': 4, 'products': 12, 'sales': 5, 'sale_items': 12, 'stock_movements': 1}
```

To return to 1.1.0, run that image with the same volume.

## Self-review

Keeping the database code separate from the menu worked well. It let me test the functions with an in-memory database without going through the menu each time. The failed-sale tests are especially useful because they check that the whole database stays unchanged after an error, including stock quantities, sale items, and movement logs.

If I built this again, I would spend more time on the menu flow. The prompts should make it clearer when a numeric product ID is needed, since entering a SKU is an easy mistake to make. I would also let users retry an invalid entry without returning to the main menu and starting the operation again.

I would improve backups too. Making two backups on the same day currently replaces the first one. Adding the time to the filename would keep both copies. A restore option in the menu would also make recovery easier.

One thing I would ask a reviewer to check is how the stock functions behave inside an existing transaction. The menu currently runs each operation separately, so I would want to understand what could happen if these functions were later used together in a larger operation.
