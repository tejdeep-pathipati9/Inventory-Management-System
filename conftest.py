from contextlib import closing

import pytest

from database import connect, setup_database


@pytest.fixture
def connection():
    with closing(connect(":memory:")) as connection:
        setup_database(connection)
        yield connection


@pytest.fixture
def product_id(connection):
    with connection:
        supplier_id = connection.execute(
            "INSERT INTO suppliers (name) VALUES (?)", ("Hardware Supply",)
        ).lastrowid
        product_id = connection.execute(
            """
            INSERT INTO products
                (sku, name, category, supplier_id, price_cents, quantity, reorder_level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("HAM-001", "Claw Hammer", "Tools", supplier_id, 1599, 10, 3),
        ).lastrowid
    return product_id
