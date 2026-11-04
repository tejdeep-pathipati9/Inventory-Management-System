import pytest

import main
from seed_db import seed_database


def test_prices_use_whole_cents():
    assert main.parse_price("12.99") == 1299
    assert main.format_money(1299) == "$12.99"
    assert main.format_money(0) == "$0.00"
    for text in ("abc", "NaN", "Infinity", "-1", "1.001"):
        with pytest.raises(ValueError, match="price|Price|decimal"):
            main.parse_price(text)


def test_menu_recovers_from_bad_numbers_and_duplicate_sku(
    connection, product_id, monkeypatch, capsys
):
    answers = iter([
        "2", "abc",
        "3", "HAM-001", "Duplicate Hammer", "Tools", "1", "15.99", "5", "2",
        "0",
    ])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    main.run_menu(connection)
    output = capsys.readouterr().out
    assert "whole number" in output
    assert "SKU already exists" in output
    assert "Goodbye" in output


def test_menu_shows_low_stock_count_once_at_startup(connection, monkeypatch, capsys):
    seed_database(connection)
    answers = iter(["invalid", "0"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    main.run_menu(connection)

    output = capsys.readouterr().out
    banner = "Low stock alert: 3 products are at or below their reorder level."
    assert output.count(banner) == 1
    assert output.index(banner) < output.index("Inventory management")
