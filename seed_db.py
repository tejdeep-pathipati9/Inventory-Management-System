import sqlite3
from contextlib import closing

from database import connect, setup_database

SUPPLIERS = [
    (1, "Forge Tools"),
    (2, "Bolt and Nut Supply"),
    (3, "Clearflow Plumbing"),
    (4, "Everyday Hardware"),
]

# Quantities represent stock remaining after the historical sample sales.
PRODUCTS = [
    (1, "HAM-001", "Claw Hammer", "Tools", 1, 1599, 10, 3),
    (2, "SCR-001", "Screwdriver", "Tools", 1, 699, 2, 5),
    (3, "WRE-001", "Adjustable Wrench", "Tools", 1, 1299, 8, 3),
    (4, "PLI-001", "Combination Pliers", "Tools", 4, 1099, 6, 2),
    (5, "NAI-001", "Steel Nails", "Fasteners", 2, 499, 30, 10),
    (6, "SCW-001", "Wood Screws", "Fasteners", 2, 599, 20, 8),
    (7, "BLT-001", "Hex Bolts", "Fasteners", 2, 799, 5, 5),
    (8, "NUT-001", "Hex Nuts", "Fasteners", 4, 399, 15, 5),
    (9, "PVC-001", "PVC Elbow", "Plumbing", 3, 249, 12, 4),
    (10, "TAP-001", "PTFE Tape", "Plumbing", 3, 199, 3, 5),
    (11, "VAL-001", "Ball Valve", "Plumbing", 3, 1499, 7, 2),
    (12, "WAS-001", "Rubber Washers", "Plumbing", 4, 299, 20, 5),
]

SALES = [
    (1, "2026-10-01T10:00:00+00:00"),
    (2, "2026-10-03T11:00:00+00:00"),
    (3, "2026-10-05T12:00:00+00:00"),
    (4, "2026-10-07T13:00:00+00:00"),
    (5, "2026-10-09T14:00:00+00:00"),
]

SALE_ITEMS = [
    (1, 1, 1, 1599), (1, 2, 2, 699), (1, 5, 3, 499),
    (2, 3, 1, 1299), (2, 6, 2, 599),
    (3, 4, 1, 1099), (3, 7, 1, 799), (3, 8, 2, 399),
    (4, 9, 2, 249), (4, 10, 1, 199),
    (5, 1, 1, 1599), (5, 5, 2, 499),
]

def _row_counts(connection):
    """Return the actual number of rows in each table."""
    return {
        "suppliers": connection.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0],
        "products": connection.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "sales": connection.execute("SELECT COUNT(*) FROM sales").fetchone()[0],
        "sale_items": connection.execute("SELECT COUNT(*) FROM sale_items").fetchone()[0],
        "stock_movements": connection.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0],
    }


def seed_database(connection):
    """Load sample data into an empty database and return actual table counts."""
    if any(_row_counts(connection).values()):
        raise ValueError("Database already contains data; nothing was changed.")
    with connection:
        connection.executemany("INSERT INTO suppliers (id, name) VALUES (?, ?)", SUPPLIERS)
        connection.executemany(
            "INSERT INTO products "
            "(id, sku, name, category, supplier_id, price_cents, quantity, reorder_level) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", PRODUCTS,
        )
        connection.executemany("INSERT INTO sales (id, sale_date) VALUES (?, ?)", SALES)
        connection.executemany(
            "INSERT INTO sale_items (sale_id, product_id, quantity, unit_price_cents) "
            "VALUES (?, ?, ?, ?)", SALE_ITEMS,
        )
    return _row_counts(connection)


def main():
    with closing(connect()) as connection:
        setup_database(connection)
        try:
            counts = seed_database(connection)
        except (sqlite3.IntegrityError, ValueError) as error:
            print("Could not seed database:", error)
            return 1
        for table, count in counts.items():
            print(f"{table}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
