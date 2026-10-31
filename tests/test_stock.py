import sqlite3

import pytest

from database import get_product, restock_product


def test_restock_increases_stock_and_logs_movement(connection, product_id):
    timestamp = "2026-10-31T12:00:00+00:00"
    assert restock_product(connection, product_id, 5, timestamp) == 15
    assert get_product(connection, product_id)["quantity"] == 15
    movements = connection.execute(
        "SELECT product_id, sku_snapshot, change, reason, created_at FROM stock_movements"
    ).fetchall()
    assert [tuple(row) for row in movements] == [
        (product_id, "HAM-001", 5, "restock", timestamp)
    ]


def test_failed_restock_changes_nothing(connection, product_id):
    for amount in (0, -1):
        with pytest.raises(ValueError, match="positive"):
            restock_product(connection, product_id, amount)
    # A failed movement insert must also undo the stock increase.
    with pytest.raises(sqlite3.IntegrityError):
        restock_product(connection, product_id, 5, created_at=b"invalid")
    assert get_product(connection, product_id)["quantity"] == 10
    assert connection.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0] == 0
