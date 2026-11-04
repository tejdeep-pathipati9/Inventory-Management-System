# Inventory Management System

A terminal application for a small hardware store. It manages products and suppliers,
searches stock, runs reports, and records stock changes and sales in SQLite.
A failed sale rolls back completely, including stock updates and movement records.
Version 1.1.0 adds a low-stock count when the menu starts.

## Run locally

Use Python 3.12 or newer and SQLite 3.37 or newer. The schema uses `STRICT` tables.
The Docker image pins Python to `3.12.16-slim-bookworm`.

```bash
git clone https://github.com/tejdeep-pathipati9/Inventory-Management-System.git
cd Inventory-Management-System
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python seed_db.py
python main.py
```

Seed only a new database. Running `seed_db.py` again refuses to overwrite existing data.
The menu creates missing tables but does not seed them automatically.
The sample suppliers have IDs 1–4; product lookup and sale input use product IDs.

The seed script prints:

```text
suppliers: 4
products: 12
sales: 5
sale_items: 12
stock_movements: 0
```

### Configuration and files

`INVENTORY_DB` selects the database file. If unset or empty, the program uses
`inventory.db` next to the Python code. Create any parent directory first.
Docker sets it to `/data/inventory.db`.

```bash
mkdir -p data
INVENTORY_DB="$PWD/data/inventory.db" python seed_db.py
INVENTORY_DB="$PWD/data/inventory.db" python main.py
```

| File | Purpose |
| --- | --- |
| `schema.sql` | Five related tables, constraints, and join indexes |
| `inventory_db.py` | Shared connection, product functions, reports, transactions, and backup |
| `seed_db.py` | Sample suppliers, products, sales, and row counts |
| `main.py` | Menu, input validation, and money display |
| `tests/` | Database, product, report, stock, seed, and menu tests |
| `Dockerfile` / `.dockerignore` | Container build and excluded local files |

Version 1.0.0 calls the database module `database.py`; 1.1.0 renames it to
`inventory_db.py`. Both versions use the same database schema.

### Menu and database rules

Options 1–8 search, look up, add, change price, delete, restock, adjust, and record a sale.
Options 9–12 show the four reports; 13 backs up the database and 0 exits.
Search matches product name, SKU, or supplier name, ignoring case, and supports
combined category, maximum-price, in-stock, and low-stock filters. Results sort by name.

Prices are stored as integer cents and displayed with two decimals. Enter dollar
amounts such as `15.99`; negative prices and more than two decimal places are refused.
Text entered for an integer produces a friendly error and returns to the menu.

The database enforces unique SKUs, required fields, foreign keys, nonnegative stock
and prices, positive sale quantities, and valid movement reasons. Sold products cannot
be deleted. An unsold product's movement history survives deletion through its saved
SKU and a nullable product reference. Every connection enables foreign keys.
SQL values use placeholders; connections close with `contextlib.closing`.

Restocking requires a positive amount. Adjustments accept a nonzero signed amount,
but cannot make stock negative. Each operation and each whole sale uses one
`with connection:` block. Sale lines save the current product price, so later price
changes do not change historical revenue. Duplicate products, unknown products,
and insufficient stock undo the entire sale. Stock functions accept `created_at`;
when omitted, they use the current UTC time.

## Tests and CI

```bash
python -m pytest -q
python -m ruff check .
```

The tests use fresh in-memory databases; backup tests use a temporary directory.
Both CI jobs run on pull requests and pushes to `main`. The `docker-build` job builds
the image and runs pytest and Ruff inside it.

Actual checks inside `inventory-management:1.1.0`:

```bash
docker run --rm inventory-management:1.1.0 python -m pytest -q
docker run --rm inventory-management:1.1.0 python -m ruff check .
```

```text
.........................................                                [100%]
41 passed in 0.05s
All checks passed!
```

The 1.0.0 image passed 40 tests and Ruff; 1.1.0 adds the banner test.

## Expected sample reports

These results apply immediately after seeding, before changing stock or recording
more sales. Stock quantities already reflect the historical sample sales.

### Stock value by supplier

| Supplier | Stock value |
| --- | ---: |
| Bolt and Nut Supply | $309.45 |
| Forge Tools | $277.80 |
| Everyday Hardware | $185.59 |
| Clearflow Plumbing | $140.78 |

### Low stock

Products exactly at their reorder level are included, with zero units short.

| SKU | Product | Stock | Reorder level | Units short |
| --- | --- | ---: | ---: | ---: |
| BLT-001 | Hex Bolts | 5 | 5 | 0 |
| TAP-001 | PTFE Tape | 3 | 5 | 2 |
| SCR-001 | Screwdriver | 2 | 5 | 3 |

The 1.1.0 startup banner therefore reports **3 products**.

### Sales by product

Revenue uses the prices recorded on sale items, highest revenue first.
Products with no sales appear with zero units and revenue.

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

### Never sold

| SKU | Product |
| --- | --- |
| VAL-001 | Ball Valve |
| WAS-001 | Rubber Washers |

## A sale that fails halfway

Run this from the project directory. It uses an in-memory database and changes no
saved inventory. The first line can succeed, but the second asks for 999 screwdrivers
when only 2 are available.

```bash
python - <<'PYTHON'
import sqlite3
from contextlib import closing
from inventory_db import connect, record_sale, setup_database
from seed_db import seed_database

with closing(connect(':memory:')) as connection:
    setup_database(connection)
    seed_database(connection)

    def show_state(label):
        stock = [tuple(row) for row in connection.execute(
            'SELECT id, quantity FROM products WHERE id IN (?, ?) ORDER BY id', (1, 2)
        )]
        counts = connection.execute(
            'SELECT (SELECT COUNT(*) FROM sales), '
            '(SELECT COUNT(*) FROM sale_items), (SELECT COUNT(*) FROM stock_movements)'
        ).fetchone()
        print(f'{label}: stock={stock}; sales={counts[0]}, sale_items={counts[1]}, stock_movements={counts[2]}')

    before = '\n'.join(connection.iterdump())
    show_state('Before')
    print('Call: record_sale(connection, [(1, 1), (2, 999)], created_at="2026-11-03T12:00:00+00:00")')
    try:
        record_sale(connection, [(1, 1), (2, 999)], created_at='2026-11-03T12:00:00+00:00')
    except sqlite3.IntegrityError as error:
        print(f'{type(error).__name__}: {error}')
    show_state('After')
    print('Entire database unchanged:', before == '\n'.join(connection.iterdump()))
PYTHON
```

Actual output:

```text
Before: stock=[(1, 10), (2, 2)]; sales=5, sale_items=12, stock_movements=0
Call: record_sale(connection, [(1, 1), (2, 999)], created_at="2026-11-03T12:00:00+00:00")
IntegrityError: CHECK constraint failed: quantity >= 0
After: stock=[(1, 10), (2, 2)]; sales=5, sale_items=12, stock_movements=0
Entire database unchanged: True
```

The comparison checks the entire database dump, including rows beyond those printed.
The stock helper does not commit; its caller owns the transaction and rolls everything
back when the stock constraint raises `sqlite3.IntegrityError`.

## Docker deployment and releases

Docker Desktop or another running Docker Engine is required. Dependencies are copied
and installed before the application code, allowing the dependency layer to be reused.
Local databases, virtual environments, Git metadata, and environment files are excluded.

Build each image from its matching Git tag:

```bash
git fetch origin --tags
git switch --detach v1.0.0
docker build --progress=plain -t inventory-management:1.0.0 .
git switch --detach v1.1.0
docker build --progress=plain -t inventory-management:1.1.0 .
git switch main
```

These are local Docker image tags. No image registry is required for these commands;
on a new machine, clone the repository and build the images first.

Actual output excerpt from the 1.1.0 verification build (completed dependency layers
were cached):

```text
#6 [2/6] WORKDIR /app
#6 CACHED

#7 [3/6] COPY requirements.txt .
#7 CACHED

#8 [4/6] RUN python -m pip install --no-cache-dir -r requirements.txt
#8 CACHED

#9 [5/6] COPY . .
#9 DONE 0.0s

#10 [6/6] RUN mkdir -p /data
#10 DONE 0.1s

#11 exporting to image
#11 exporting layers 0.0s done
#11 exporting manifest sha256:2f3aa80f0efde3d75b71582c78ac6623f42593f13ed9e6b51fcafabf7eb037a9 done
#11 exporting config sha256:e8d4455e5990d8e0b3ddd3d885374c6f8052d57f821b1a576adc8d820f8d33b8 done
#11 exporting attestation manifest sha256:6b29a194e8b10fff4465a128028d87f8caa07f41022d3e0941ce4ff71b0b30bc done
#11 exporting manifest list sha256:8e9a4a4e5c4f96734a52108c9117625d70eb8a83335672967204a6f50a590df8 done
#11 naming to docker.io/library/inventory-management:1.1.0 done
#11 unpacking to docker.io/library/inventory-management:1.1.0 done
#11 DONE 0.1s

```

### Interactive run and persistence

Use a new volume for this sample. Reuse its exact name in every command below.
The verification volume was `inventory-release-check-c823280`.

```bash
docker run --rm -v inventory-release-check-c823280:/data inventory-management:1.0.0 python seed_db.py
docker run --rm -it -v inventory-release-check-c823280:/data inventory-management:1.1.0
```

At startup, the actual output included:

```text
Low stock alert: 3 products are at or below their reorder level.
```

Choose **6**, product **1**, amount **5**; then choose **13**, folder **/data/backups**;
then **0**. Actual output excerpts:

```text
Product ID: Amount to add: Stock is now 15.
Choose an option: Backup folder: Backup saved to /data/backups/inventory-2026-11-04.db.
Choose an option: Goodbye.
```

The dated backup name uses the container's calendar date, which may differ from the
local date. The verification commands below discover that generated file.
The stopped container is removed by `--rm`; the named volume retains the database.
Start a new container and read both the quantity and the entire database fingerprint:

```bash
docker run --rm -v inventory-release-check-c823280:/data inventory-management:1.1.0 python -c 'from contextlib import closing; from inventory_db import connect, get_product; from seed_db import _row_counts; from hashlib import sha256
with closing(connect()) as connection:
 print("Version 1.1.0: product 1 quantity:", get_product(connection, 1)["quantity"])
 print("Row counts:", _row_counts(connection))
 print("Database SHA256:", sha256("\n".join(connection.iterdump()).encode()).hexdigest())'
```

Actual output:

```text
Version 1.1.0: product 1 quantity: 15
Row counts: {'suppliers': 4, 'products': 12, 'sales': 5, 'sale_items': 12, 'stock_movements': 1}
Database SHA256: f09ef5d33ae657edfa261d797a7e3742acad0c40ed66358870e03cf5de86cd3d
```

For normal use, choose your own persistent volume name and seed it only once.
Backups inside the same volume support this exercise; keep an additional copy outside
that volume to protect against losing the volume itself.

## Backup, check, and restore

Menu option **13** accepts a folder. It uses SQLite's backup API and creates
`inventory-YYYY-MM-DD.db`. Repeating a backup in the same folder on the same day
replaces that day's backup. The connection must have no pending writes; menu actions
finish their transactions before backup.

Stop the menu before restoring. The following is the **sample verification exercise**:
it checks the saved backup, temporarily changes product 1 to zero, and restores it.
It uses only the isolated sample volume above. Its row counts and full database dump
are compared, as well as `PRAGMA integrity_check`.

```bash
docker run --rm -i -v inventory-release-check-c823280:/data inventory-management:1.1.0 python - <<'PYTHON'
from contextlib import closing
from pathlib import Path
from inventory_db import connect
from seed_db import _row_counts

backup_path = next(Path('/data/backups').glob('inventory-*.db'))
with closing(connect()) as source, closing(connect(backup_path)) as backup:
    print('Backup:', backup_path)
    print('Integrity:', backup.execute('PRAGMA integrity_check').fetchone()[0])
    print('Original counts:', _row_counts(source))
    print('Backup counts:', _row_counts(backup))
    assert _row_counts(source) == _row_counts(backup)
    original = '\n'.join(source.iterdump())
    assert original == '\n'.join(backup.iterdump())
    with source:
        source.execute('UPDATE products SET quantity = ? WHERE id = ?', (0, 1))
    print('Before restore:', source.execute('SELECT quantity FROM products WHERE id = ?', (1,)).fetchone()[0])
    backup.backup(source)
    print('After restore:', source.execute('SELECT quantity FROM products WHERE id = ?', (1,)).fetchone()[0])
    print('Full database restored:', original == '\n'.join(source.iterdump()))
PYTHON
```

Actual output:

```text
Backup: /data/backups/inventory-2026-11-04.db
Integrity: ok
Original counts: {'suppliers': 4, 'products': 12, 'sales': 5, 'sale_items': 12, 'stock_movements': 1}
Backup counts: {'suppliers': 4, 'products': 12, 'sales': 5, 'sale_items': 12, 'stock_movements': 1}
Before restore: 0
After restore: 15
Full database restored: True
```

For an ordinary restore, with the application stopped, use the exact backup you want.
Run this from the project directory, replacing the two paths:

```bash
python - <<'PYTHON'
from contextlib import closing
from inventory_db import connect

with closing(connect("backups/inventory-YYYY-MM-DD.db")) as backup:
    assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    with closing(connect("inventory.db")) as destination:
        backup.backup(destination)
PYTHON
```

Restart `python main.py` afterward. If `INVENTORY_DB` selects a different file, use that
file as the destination instead. Restore replaces the destination's current contents.

## Roll back from 1.1.0 to 1.0.0

Stop the 1.1.0 menu and run 1.0.0 against the **same volume**. Neither version changes
the schema, so no data migration is needed. Keep the volume when changing images.

```bash
docker run --rm -it -v inventory-release-check-c823280:/data inventory-management:1.0.0
```

The old menu starts without the low-stock banner. To reproduce the recorded data check:

```bash
docker run --rm -v inventory-release-check-c823280:/data inventory-management:1.0.0 python -c 'from contextlib import closing; from database import connect, get_product; from seed_db import _row_counts; from hashlib import sha256
with closing(connect()) as connection:
 print("Version 1.0.0 rollback: product 1 quantity:", get_product(connection, 1)["quantity"])
 print("Row counts:", _row_counts(connection))
 print("Database SHA256:", sha256("\n".join(connection.iterdump()).encode()).hexdigest())'
```

Actual output:

```text
Version 1.0.0 rollback: product 1 quantity: 15
Row counts: {'suppliers': 4, 'products': 12, 'sales': 5, 'sale_items': 12, 'stock_movements': 1}
Database SHA256: f09ef5d33ae657edfa261d797a7e3742acad0c40ed66358870e03cf5de86cd3d
```

Quantity, all five table counts, and the complete database fingerprint match 1.1.0.
Use the 1.1.0 image with the same volume to move forward again.

## Self-review

Keeping database operations separate from the menu makes the code easier to follow
and test. The failed-sale test checks the entire database, showing that stock, sale
items, and movement records all roll back together.

If I rebuilt the project, I would settle the module and function names earlier to
avoid updating imports late in development. I would also give each report its own
display function so formatting does not depend on menu numbers.

I would want a reviewer to check transaction ownership, especially what happens if
a stock function is called during an existing transaction. Backup retention could
also improve: making two backups in the same folder on the same day replaces the
earlier copy.
