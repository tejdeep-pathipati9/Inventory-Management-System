import sqlite3

import pytest

from database import (
    add_product,
    change_price,
    delete_product,
    get_product,
)
from seed_db import seed_database


def test_add_product_returns_new_id(connection, product_id):
    new_id = add_product(connection, "SCR-002", "Screwdriver", "Tools", 1, 599, 4, 2)
    assert new_id == product_id + 1
    assert get_product(connection, new_id)["sku"] == "SCR-002"


def test_get_product_includes_supplier_name(connection, product_id):
    product = get_product(connection, product_id)
    assert product["name"] == "Claw Hammer"
    assert product["supplier_name"] == "Hardware Supply"
    assert get_product(connection, 999) is None


def test_duplicate_sku_is_refused(connection, product_id):
    with pytest.raises(sqlite3.IntegrityError):
        add_product(connection, "HAM-001", "Hammer", "Tools", 1, 500, 5, 2)


def test_unknown_supplier_is_refused(connection):
    with pytest.raises(sqlite3.IntegrityError):
        add_product(connection, "NEW-001", "Hammer", "Tools", 999, 500, 5, 2)


@pytest.mark.parametrize(("price_cents", "quantity"), [(-1, 5), (500, -1)])
def test_negative_values_are_refused(connection, product_id, price_cents, quantity):
    with pytest.raises(sqlite3.IntegrityError):
        add_product(connection, "NEW-001", "Hammer", "Tools", 1, price_cents, quantity, 2)


def test_change_price_and_delete_product(connection):
    seed_database(connection)
    assert change_price(connection, 1, 1299) is True
    assert get_product(connection, 1)["price_cents"] == 1299
    assert change_price(connection, 999, 1299) is False
    with pytest.raises(sqlite3.IntegrityError):
        delete_product(connection, 1)
    assert delete_product(connection, 11) is True
    assert get_product(connection, 11) is None