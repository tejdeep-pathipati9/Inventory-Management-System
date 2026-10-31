import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().with_name("inventory.db")
SCHEMA_PATH = Path(__file__).resolve().with_name("schema.sql")


def connect(database_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a database with foreign key checks and rows accessible by name."""
    if database_path is None:
        database_path = os.environ.get("INVENTORY_DB") or DEFAULT_DB_PATH

    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row
    return connection


def setup_database(connection: sqlite3.Connection) -> None:
    """Create missing tables and indexes before starting application transactions."""
    # executescript commits a pending transaction, so refuse to interrupt one.
    if connection.in_transaction:
        raise sqlite3.ProgrammingError(
            "Cannot set up the schema during an active transaction."
        )
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def add_product(connection, sku, name, category, supplier_id, price_cents, quantity, reorder_level):
    """Add a product and return its new ID. Invalid data raises sqlite3.IntegrityError."""
    with connection:
        cursor = connection.execute(
            "INSERT INTO products "
            "(sku, name, category, supplier_id, price_cents, quantity, reorder_level) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sku, name, category, supplier_id, price_cents, quantity, reorder_level),
        )
    return cursor.lastrowid


def get_product(connection, product_id):
    """Return a product with its supplier's name, or None if it is missing."""
    return connection.execute(
        "SELECT p.id, p.sku, p.name, p.category, p.supplier_id, "
        "p.price_cents, p.quantity, p.reorder_level, s.name AS supplier_name "
        "FROM products p JOIN suppliers s ON s.id = p.supplier_id "
        "WHERE p.id = ?",
        (product_id,),
    ).fetchone()


def change_price(connection, product_id, price_cents):
    """Change a price in cents; return False if the product is missing."""
    with connection:
        cursor = connection.execute(
            "UPDATE products SET price_cents = ? WHERE id = ?",
            (price_cents, product_id),
        )
    return cursor.rowcount == 1


def delete_product(connection, product_id):
    """Delete a product; sales history raises sqlite3.IntegrityError."""
    with connection:
        cursor = connection.execute("DELETE FROM products WHERE id = ?", (product_id,))
    return cursor.rowcount == 1


def search_products(connection, text="", category=None, max_price=None, in_stock_only=False, low_stock_only=False):
    """Return matches sorted by name. The maximum price is in whole cents."""
    sql = (
        "SELECT p.id, p.sku, p.name, p.category, p.supplier_id, "
        "p.price_cents, p.quantity, p.reorder_level, s.name AS supplier_name "
        "FROM products p JOIN suppliers s ON s.id = p.supplier_id "
        "WHERE (p.name LIKE ? OR p.sku LIKE ? OR s.name LIKE ?)"
    )
    pattern = f"%{text}%"
    params = [pattern, pattern, pattern]
    if category is not None:
        sql += " AND p.category = ?"
        params.append(category)
    if max_price is not None:
        sql += " AND p.price_cents <= ?"
        params.append(max_price)
    if in_stock_only:
        sql += " AND p.quantity > 0"
    if low_stock_only:
        sql += " AND p.quantity <= p.reorder_level"
    sql += " ORDER BY p.name"
    return connection.execute(sql, params).fetchall()
