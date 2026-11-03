import sqlite3
import pytest
from inventory_db import (
    add_product,
    adjust_stock,
    change_price,
    get_product,
    record_sale,
    restock_product,
)


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


def test_adjustment_logs_signed_changes_and_rejects_negative_stock(connection, product_id):
    timestamp = "2026-10-31T12:00:00+00:00"
    assert adjust_stock(connection, product_id, -3, timestamp) == 7
    assert adjust_stock(connection, product_id, 2, timestamp) == 9
    movements = connection.execute(
        "SELECT change, reason, created_at FROM stock_movements ORDER BY id"
    ).fetchall()
    assert [tuple(row) for row in movements] == [
        (-3, "adjustment", timestamp), (2, "adjustment", timestamp)
    ]
    before = list(connection.iterdump())
    with pytest.raises(sqlite3.IntegrityError):
        adjust_stock(connection, product_id, -10, timestamp)
    assert list(connection.iterdump()) == before


def test_sale_uses_current_prices_reduces_stock_and_logs_each_line(connection, product_id):
    second_id = add_product(connection, "NAI-001", "Nails", "Fasteners", 1, 499, 20, 5)
    change_price(connection, product_id, 1299)
    timestamp = "2026-10-31T12:00:00+00:00"
    sale_id = record_sale(connection, [(product_id, 2), (second_id, 3)], timestamp)
    sale = connection.execute("SELECT sale_date FROM sales WHERE id = ?", (sale_id,)).fetchone()
    assert sale["sale_date"] == timestamp
    lines = connection.execute(
        "SELECT product_id, quantity, unit_price_cents FROM sale_items "
        "WHERE sale_id = ? ORDER BY product_id", (sale_id,),
    ).fetchall()
    assert [tuple(row) for row in lines] == [(product_id, 2, 1299), (second_id, 3, 499)]
    assert get_product(connection, product_id)["quantity"] == 8
    assert get_product(connection, second_id)["quantity"] == 17
    movements = connection.execute(
        "SELECT product_id, sku_snapshot, change, reason, created_at "
        "FROM stock_movements ORDER BY id"
    ).fetchall()
    assert [tuple(row) for row in movements] == [
        (product_id, "HAM-001", -2, "sale", timestamp),
        (second_id, "NAI-001", -3, "sale", timestamp),
    ]


@pytest.mark.parametrize(
    ("items", "error"),
    [
        ([(1, 2), (2, 99)], sqlite3.IntegrityError),
        ([(1, 2), (999, 1)], ValueError),
        ([(1, 2), (1, 1)], sqlite3.IntegrityError),
    ],
    ids=["insufficient-stock", "unknown-product", "duplicate-product"],
)
def test_failed_sale_rolls_back_everything(connection, product_id, items, error):
    add_product(connection, "NAI-001", "Nails", "Fasteners", 1, 499, 5, 2)
    before = list(connection.iterdump())
    with pytest.raises(error):
        record_sale(connection, items, "2026-10-31T12:00:00+00:00")
    assert list(connection.iterdump()) == before
