import pytest

import main


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
