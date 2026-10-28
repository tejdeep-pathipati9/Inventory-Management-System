# Inventory Management System — Plan

## 1. Database Design

I'll create five tables in `schema.sql`:

| Table | Fields and Constraints |
|---|---|
| `suppliers` | `id` (PK), `name` (NOT NULL) |
| `products` | `id` (PK), `sku` (UNIQUE, NOT NULL), `name` and `category` (NOT NULL), `supplier_id` (FK, NOT NULL), `price_cents`, `quantity`, and `reorder_level` (NOT NULL, CHECK >= 0) |
| `sales` | `id` (PK), `sale_date` (NOT NULL) |
| `sale_items` | `sale_id` (FK), `product_id` (FK), `quantity` (NOT NULL, CHECK > 0), `unit_price_cents` (NOT NULL, CHECK >= 0). Composite PK: (`sale_id`, `product_id`) |
| `stock_movements` | `id` (PK), `product_id` (FK), `product_sku` (NOT NULL), `change` (NOT NULL, CHECK != 0), `reason` (NOT NULL, CHECK: restock, adjustment, sale), `created_at` (NOT NULL) |

**Relationships:**

- **Suppliers → Products (1:N):** One supplier can supply multiple products. `products.supplier_id` references `suppliers.id`.
- **Sales → Sale Items (1:N):** One sale can contain multiple items. `sale_items.sale_id` references `sales.id`.
- **Products → Sale Items (1:N):** One product can appear in multiple sales. `sale_items.product_id` references `products.id`.
- **Products → Stock Movements (1:N):** One product can have multiple stock movements. `stock_movements.product_id` references `products.id`.

The `sale_items` foreign key will prevent deleting products with sales history. Unsold products can be deleted, while their movement records are preserved using `ON DELETE SET NULL` and the saved SKU.

**Other database rules:**

- Enable foreign key checking on every connection.
- Add an index on `products.supplier_id` for supplier lookups.
- Use `CREATE TABLE IF NOT EXISTS` so rerunning the schema doesn't erase existing data.
- Store prices as whole cents to avoid floating-point rounding issues.

**Seed data:** I'll add 4 suppliers, 12 products across at least 3 categories, 5 sales, and 12 sale items. At least 2 products will have no sales, and 2 will be at or below their reorder level. `stock_movements` will start empty. I'll use placeholders and `executemany` and print the row counts.

## 2. Function Design

All database functions will receive a connection, except `connect()`.

| Function | Inputs (besides connection) | Returns |
|---|---|---|
| `connect` | Optional database path | SQLite connection |
| `setup_database` | None | Nothing; creates tables |
| `seed_database` | None | Row counts |
| `add_product` | SKU, name, category, supplier ID, price, stock, reorder level | New product ID |
| `get_product` | Product ID | Product details with supplier name, or `None` |
| `change_price` | Product ID, new price | `True` if updated, `False` if missing |
| `delete_product` | Product ID | `True` if deleted, `False` if missing; error if sold |
| `search_products` | Search text, optional filters | Matching products sorted by name |
| `stock_value_report` | None | Stock value by supplier, highest first |
| `low_stock_report` | None | Low-stock products and units short |
| `sales_report` | None | Units sold and revenue by product |
| `never_sold_report` | None | Products never sold |
| `restock_product` | Product ID, amount, optional time | Updated stock quantity |
| `adjust_stock` | Product ID, signed change, optional time | Updated stock quantity |
| `record_sale` | Product/quantity pairs, optional time | New sale ID |
| `backup_database` | Backup file path | Nothing on success |
| `run_menu` | None | Nothing; starts the menu |

## 3. Stock Changes and Transactions

**Restock:** Validate the product and positive quantity, increase stock, and record a `restock` movement. If either operation fails, roll back both.

**Adjust:** Validate the product and nonzero change, check that the resulting stock isn't negative, update the quantity, and record an `adjustment` movement. If anything fails, roll back both changes.

**Record a sale:** Reject invalid quantities and duplicate products. Create the sale, then for each item verify stock availability, record the current price, deduct stock, and log a negative `sale` movement.

If any item fails, the entire sale will be rolled back, including the sale record, sale items, stock updates, and movement logs.

Each operation will use one `with connection:` transaction, without commits inside helper functions. I'll test that a failed sale leaves the database unchanged.

## 4. Testing and Deployment

I'll use pytest to test product operations, searches, reports, stock changes, transactions, and backups. I'll also use `ruff` for code quality checks.

The menu will handle invalid inputs without crashing. Docker will use a pinned Python version and a volume to preserve data, with the database path set through `INVENTORY_DB`. I'll verify backups using `PRAGMA integrity_check` and row counts.

## 5. Git and Release Plan

I'll complete the project through six pull requests, each with passing CI checks before merging.

| PR | Branch | Work |
|---|---|---|
| 1 | `feature/database-and-seed` | Schema, seed data, tests |
| 2 | `feature/products-and-search` | Product operations and search |
| 3 | `feature/reports` | Four inventory reports |
| 4 | `feature/stock-and-sales` | Restock, adjustments, sales, transactions |
| 5 | `feature/menu-and-container` | CLI menu, Docker, backup |
| 6 | `feature/low-stock-banner` | Low-stock count at startup |

Only setup files and `PLAN.md` will be committed directly to `main`. All other work will go through pull requests with short descriptions. I'll delete feature branches after merging.

GitHub Actions will run tests, check code quality, build the Docker image, and run tests inside the image.

**Releases:**

- **v1.0.0:** Complete inventory system with tests, menu, Docker, and backup support.
- **v1.1.0:** Add the low-stock banner at startup.

Both releases will have Git tags, Docker image tags, and entries in `CHANGELOG.md`. I'll also test rolling back from v1.1.0 to v1.0.0 without losing data.