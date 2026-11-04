import sqlite3
from contextlib import closing
from decimal import Decimal, DecimalException

import inventory_db as db


def parse_price(text):
    """Convert a price such as 12.99 to whole cents without rounding."""
    try:
        price = Decimal(text)
        if not price.is_finite() or price < 0:
            raise ValueError("Enter a price of zero or more.")
        if price != price.quantize(Decimal("0.01")):
            raise ValueError("Use at most two decimal places.")
        return int(price * 100)
    except DecimalException:
        raise ValueError("Enter a valid price, such as 12.99.") from None


def format_money(cents):
    return f"${cents // 100}.{cents % 100:02d}"


def _read_required_text(prompt):
    text = input(prompt).strip()
    if not text:
        raise ValueError("This field cannot be empty.")
    return text


def _read_integer(prompt):
    try:
        return int(input(prompt))
    except ValueError:
        raise ValueError("Enter a whole number.") from None


def _read_yes_no(prompt):
    answer = input(prompt).strip().lower()
    if answer not in ("", "n", "no", "y", "yes"):
        raise ValueError("Enter y or n.")
    return answer in ("y", "yes")


def _show_products(products):
    if not products:
        print("No products found.")
    for product in products:
        print(
            f"ID: {product['id']} | SKU: {product['sku']} | {product['name']} "
            f"| Category: {product['category']} | Price: {format_money(product['price_cents'])} "
            f"| Stock: {product['quantity']} | Reorder: {product['reorder_level']} "
            f"| Supplier: {product['supplier_name']} (ID {product['supplier_id']})"
        )


def _show_report(rows, choice):
    if choice == "9":
        for row in rows:
            print(f"{row['supplier_name']} | Stock value: {format_money(row['stock_value_cents'])}")
    elif choice == "10":
        for row in rows:
            print(
                f"{row['sku']} | {row['name']} | Stock: {row['quantity']} "
                f"| Reorder: {row['reorder_level']} | Units short: {row['units_short']}"
            )
    elif choice == "11":
        for row in rows:
            print(
                f"{row['sku']} | {row['name']} | Units sold: {row['units_sold']} "
                f"| Revenue: {format_money(row['revenue_cents'])}"
            )
    else:
        for row in rows:
            print(f"{row['sku']} | {row['name']}")
    if not rows:
        print("No results found.")


def _search_products(connection):
    text = input("Search text (blank for all): ").strip()
    category = input("Category (blank for any): ").strip() or None
    price = input("Maximum price (blank for any): ").strip()
    maximum = parse_price(price) if price else None
    in_stock = _read_yes_no("In stock only? [y/N]: ")
    low_stock = _read_yes_no("Low stock only? [y/N]: ")
    products = db.search_products(
        connection, text, category=category, max_price=maximum,
        in_stock_only=in_stock, low_stock_only=low_stock,
    )
    _show_products(products)


def _look_up_product(connection):
    product = db.get_product(connection, _read_integer("Product ID: "))
    if product is None:
        print("Product not found.")
    else:
        _show_products([product])


def _add_product(connection):
    sku = _read_required_text("SKU: ")
    name = _read_required_text("Name: ")
    category = _read_required_text("Category: ")
    supplier_id = _read_integer("Supplier ID: ")
    price = parse_price(input("Unit price (for example 12.99): "))
    quantity = _read_integer("Quantity in stock: ")
    reorder_level = _read_integer("Reorder level: ")
    product_id = db.add_product(
        connection, sku, name, category, supplier_id, price, quantity, reorder_level
    )
    print(f"Added product {product_id}.")


def _change_product_price(connection):
    product_id = _read_integer("Product ID: ")
    price = parse_price(input("New price: "))
    found = db.change_price(connection, product_id, price)
    print("Price updated." if found else "Product not found.")


def _delete_product(connection):
    product_id = _read_integer("Product ID: ")
    found = db.delete_product(connection, product_id)
    print("Product deleted." if found else "Product not found.")


def _restock_product(connection):
    product_id = _read_integer("Product ID: ")
    amount = _read_integer("Amount to add: ")
    quantity = db.restock_product(connection, product_id, amount)
    print(f"Stock is now {quantity}.")


def _adjust_stock(connection):
    product_id = _read_integer("Product ID: ")
    change = _read_integer("Signed change (for example -2 or 3): ")
    quantity = db.adjust_stock(connection, product_id, change)
    print(f"Stock is now {quantity}.")


def _record_sale(connection):
    count = _read_integer("Number of different products: ")
    if count <= 0:
        raise ValueError("Add at least one product to the sale.")
    items = []
    for number in range(1, count + 1):
        product_id = _read_integer(f"Line {number} product ID: ")
        quantity = _read_integer(f"Line {number} quantity: ")
        items.append((product_id, quantity))
    sale_id = db.record_sale(connection, items)
    print(f"Recorded sale {sale_id}.")


def _backup_database(connection):
    folder = _read_required_text("Backup folder: ")
    path = db.backup_database(connection, folder)
    print(f"Backup saved to {path}.")


def _integrity_error_message(error, choice):
    message = str(error)
    if "products.sku" in message:
        return "That SKU already exists."
    if "sale_items.sale_id" in message:
        return "A product appears more than once in the sale."
    if "FOREIGN KEY" in message:
        if choice == "5":
            return "That product has sales history and cannot be deleted."
        return "That supplier or related product does not exist."
    if "reorder_level" in message:
        return "Reorder level cannot be negative."
    if "price_cents" in message:
        return "Price cannot be negative."
    if "quantity" in message:
        return "That operation would make the stock quantity invalid."
    return "The supplied values violate a database rule."


def run_menu(connection):
    try:
        low_stock_count = len(db.low_stock_report(connection))
        print(f"Low stock alert: {low_stock_count} products are at or below their reorder level.")

    except sqlite3.Error as error:
        print("Could not load low stock alert:", error)

    menu = {
        "1": ("Search products", _search_products),
        "2": ("Look up a product", _look_up_product),
        "3": ("Add a product", _add_product),
        "4": ("Change a price", _change_product_price),
        "5": ("Delete a product", _delete_product),
        "6": ("Restock", _restock_product),
        "7": ("Adjust stock", _adjust_stock),
        "8": ("Record a sale", _record_sale),
        "9": ("Stock value by supplier", db.stock_value_report),
        "10": ("Low stock", db.low_stock_report),
        "11": ("Sales by product", db.sales_report),
        "12": ("Never sold", db.never_sold_report),
        "13": ("Back up the database", _backup_database),
    }
    while True:
        print("\nInventory management")
        for number, (label, _) in menu.items():
            print(f"{number}. {label}")
        print("0. Exit")
        choice = ""
        try:
            choice = input("Choose an option: ").strip()
            if choice == "0":
                print("Goodbye.")
                return
            if choice not in menu:
                print("Choose one of the listed options.")
                continue
            label, action = menu[choice]
            rows = action(connection)
            if choice in ("9", "10", "11", "12"):
                _show_report(rows, choice)
        except sqlite3.IntegrityError as error:
            print(_integrity_error_message(error, choice))
        except sqlite3.Error as error:
            print("Database error:", error)
        except ValueError as error:
            print("Could not complete the operation:", error)
        except OverflowError:
            print("That number is too large.")
        except OSError as error:
            print("Could not access that file:", error)
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return


def main():
    try:
        with closing(db.connect()) as connection:
            db.setup_database(connection)
            run_menu(connection)
    except (sqlite3.Error, OSError) as error:
        print("Could not open the inventory database:", error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
