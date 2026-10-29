import seed_db


def test_seed_creates_required_row_counts(connection):
    assert seed_db.seed_database(connection) == {
        "suppliers": 4,
        "products": 12,
        "sales": 5,
        "sale_items": 12,
        "stock_movements": 0,
    }
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_sample_has_categories_unsold_and_low_stock_products(connection):
    seed_db.seed_database(connection)
    assert connection.execute("SELECT COUNT(DISTINCT category) FROM products").fetchone()[0] >= 3
    assert connection.execute(
        "SELECT COUNT(*) FROM products p "
        "LEFT JOIN sale_items si ON si.product_id = p.id "
        "WHERE si.product_id IS NULL"
    ).fetchone()[0] >= 2
    assert connection.execute(
        "SELECT COUNT(*) FROM products WHERE quantity <= reorder_level"
    ).fetchone()[0] >= 2
