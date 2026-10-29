import sqlite3
from contextlib import closing

import pytest

from database import connect, setup_database


def test_connection_enables_foreign_keys_and_named_rows(connection):
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert connection.execute("SELECT ? AS name", ("Hammer",)).fetchone()["name"] == "Hammer"


def test_connect_uses_inventory_db(monkeypatch, tmp_path):
    path = tmp_path / "inventory.db"
    monkeypatch.setenv("INVENTORY_DB", str(path))
    with closing(connect()) as connection:
        setup_database(connection)
    assert path.exists()


def test_schema_creates_five_strict_tables(connection):
    tables = {
        row["name"]: row["strict"]
        for row in connection.execute("PRAGMA table_list")
        if not row["name"].startswith("sqlite_")
    }
    assert tables == dict.fromkeys(
        ("suppliers", "products", "sales", "sale_items", "stock_movements"), 1
    )
    columns = {row["name"]: row for row in connection.execute("PRAGMA table_info(products)")}
    assert columns["id"]["pk"] == 1
    assert columns["sku"]["pk"] == 0


def test_rerunning_schema_preserves_data(connection, product_id):
    setup_database(connection)
    assert connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 1
    row = connection.execute("SELECT sku FROM products WHERE id = ?", (product_id,)).fetchone()
    assert row["sku"] == "HAM-001"


@pytest.mark.parametrize(
    ("position", "value"),
    [(0, None), (0, "HAM-001"), (3, 999), (4, -1), (5, -1), (6, -1)],
)
def test_invalid_product_fields_are_rejected(connection, product_id, position, value):
    supplier_id = connection.execute(
        "SELECT supplier_id FROM products WHERE id = ?", (product_id,)
    ).fetchone()["supplier_id"]
    values = ["NEW-001", "Screwdriver", "Tools", supplier_id, 500, 5, 2]
    values[position] = value
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO products (sku, name, category, supplier_id, price_cents, quantity, reorder_level) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            values,
        )


def test_invalid_movement_reason_is_rejected(connection, product_id):
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO stock_movements (product_id, sku_snapshot, change, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (product_id, "HAM-001", 1, "invalid", "2026-10-29T12:00:00+00:00"),
        )


def test_sale_items_reference_id_and_prevent_sold_product_deletion(connection, product_id):
    sale_id = connection.execute(
        "INSERT INTO sales (sale_date) VALUES (?)", ("2026-10-29T12:00:00+00:00",)
    ).lastrowid
    statement = "INSERT INTO sale_items (sale_id, product_id, quantity, unit_price_cents) VALUES (?, ?, ?, ?)"
    connection.execute(statement, (sale_id, product_id, 1, 1599))
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(statement, (sale_id, 999, 1, 1599))
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("DELETE FROM products WHERE id = ?", (product_id,))


def test_deleting_unsold_product_preserves_sku_snapshot(connection, product_id):
    connection.execute(
        "INSERT INTO stock_movements (product_id, sku_snapshot, change, reason, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (product_id, "HAM-001", 1, "restock", "2026-10-29T12:00:00+00:00"),
    )
    connection.execute("DELETE FROM products WHERE id = ?", (product_id,))
    row = connection.execute("SELECT product_id, sku_snapshot FROM stock_movements").fetchone()
    assert row["product_id"] is None
    assert row["sku_snapshot"] == "HAM-001"