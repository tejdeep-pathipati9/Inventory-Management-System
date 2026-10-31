import os
import sqlite3
from datetime import UTC, datetime
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

"""
Write four reports, each a function that returns rows:
Stock value by supplier: the supplier name and the total value of its stock (price times quantity), highest first.
Low stock: every product at or below its reorder level, with how many units short of the level it is.
Sales by product: each product with the units sold and the revenue, highest revenue first.
Never sold: products that appear in no sale.

"""
def stock_value_report(connection):
    """Return supplier stock values in cents, highest first."""
    return connection.execute(
        "SELECT s.name AS supplier_name, "
        "COALESCE(SUM(p.price_cents * p.quantity), 0) AS stock_value_cents "
        "FROM suppliers s "
        "LEFT JOIN products p "
            "ON p.supplier_id = s.id "
        "GROUP BY s.id, s.name "
        "ORDER BY stock_value_cents DESC, s.name"
    ).fetchall()


def low_stock_report(connection):
    """Return products at or below reorder level with their units short."""
    return connection.execute(
        "SELECT p.id, p.sku, p.name, p.quantity, p.reorder_level, "
        "p.reorder_level - p.quantity AS units_short "
        "FROM products p WHERE p.quantity <= p.reorder_level "
        "ORDER BY p.name"
    ).fetchall()


def sales_report(connection):
    """Return all products with units sold and historical revenue in cents."""
    return connection.execute(
        "SELECT p.id, p.sku, p.name, "
        "COALESCE(SUM(si.quantity), 0) AS units_sold, "
        "COALESCE(SUM(si.quantity * si.unit_price_cents), 0) AS revenue_cents "
        "FROM products p LEFT JOIN sale_items si ON si.product_id = p.id "
        "GROUP BY p.id, p.sku, p.name "
        "ORDER BY revenue_cents DESC, p.name"
    ).fetchall()


def never_sold_report(connection):
    """Return products that have never appeared in a sale, sorted by name."""
    return connection.execute(
        "SELECT p.id, p.sku, p.name "
        "FROM products p LEFT JOIN sale_items si ON si.product_id = p.id "
        "WHERE si.product_id IS NULL ORDER BY p.name"
    ).fetchall()


def restock_product(connection, product_id, amount, created_at=None):
    """Increase stock and log the movement atomically; return the new quantity."""
    if amount <= 0:
        raise ValueError("Restock amount must be positive.")
    if created_at is None:
        created_at = datetime.now(UTC).isoformat()
    with connection:
        product = get_product(connection, product_id)
        if product is None:
            raise ValueError(f"No product with id {product_id}")
        connection.execute(
            "UPDATE products SET quantity = quantity + ? WHERE id = ?",
            (amount, product_id),
        )
        connection.execute(
            "INSERT INTO stock_movements "
            "(product_id, sku_snapshot, change, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (product_id, product["sku"], amount, "restock", created_at),
        )
        updated_quantity = get_product(connection, product_id)["quantity"]
    return updated_quantity
