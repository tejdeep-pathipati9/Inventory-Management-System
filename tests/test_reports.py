from database import (
    change_price,
    low_stock_report,
    never_sold_report,
    sales_report,
    stock_value_report,
)
from seed_db import seed_database


def test_stock_value_by_supplier(connection):
    seed_database(connection)
    rows = stock_value_report(connection)
    assert [tuple(row) for row in rows] == [
        ("Bolt and Nut Supply", 30945),
        ("Forge Tools", 27780),
        ("Everyday Hardware", 18559),
        ("Clearflow Plumbing", 14078),
    ]


def test_low_stock_includes_products_at_the_reorder_level(connection):
    seed_database(connection)
    rows = low_stock_report(connection)
    assert [(row["sku"], row["units_short"]) for row in rows] == [
        ("BLT-001", 0),
        ("TAP-001", 2),
        ("SCR-001", 3),
    ]


def test_sales_use_recorded_prices_and_include_unsold_products(connection):
    seed_database(connection)
    change_price(connection, 1, 9999)
    rows = sales_report(connection)
    assert [(row["sku"], row["units_sold"], row["revenue_cents"]) for row in rows] == [
        ("HAM-001", 2, 3198),
        ("NAI-001", 5, 2495),
        ("SCR-001", 2, 1398),
        ("WRE-001", 1, 1299),
        ("SCW-001", 2, 1198),
        ("PLI-001", 1, 1099),
        ("BLT-001", 1, 799),
        ("NUT-001", 2, 798),
        ("PVC-001", 2, 498),
        ("TAP-001", 1, 199),
        ("VAL-001", 0, 0),
        ("WAS-001", 0, 0),
    ]


def test_never_sold_products(connection):
    seed_database(connection)
    rows = never_sold_report(connection)
    assert [(row["sku"], row["name"]) for row in rows] == [
        ("VAL-001", "Ball Valve"),
        ("WAS-001", "Rubber Washers"),
    ]
