"""Builds the demo data: a small shop database and a folder of policy documents."""
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
rng = random.Random(7)

FIRST = ["Maya", "Liam", "Noah", "Ava", "Omar", "Sofia", "Ethan", "Zara", "Lucas", "Amira", "Ivan", "Chloe",
         "Ravi", "Hana", "Mateo", "Leah", "Yusuf", "Nora", "Owen", "Priya"]
LAST = ["Chen", "Patel", "Smith", "Khan", "Garcia", "Nguyen", "Brown", "Ali", "Kowalski", "Martin"]
CITIES = ["Calgary", "Toronto", "Vancouver", "Montreal", "Edmonton", "Ottawa"]
PRODUCTS = [("Trail Running Shoes", "footwear", 149.0), ("Rain Jacket", "outerwear", 189.0),
            ("Merino Base Layer", "apparel", 89.0), ("Hiking Socks (3 pack)", "apparel", 24.0),
            ("Daypack 25L", "bags", 119.0), ("Insulated Bottle", "accessories", 39.0),
            ("Headlamp", "accessories", 54.0), ("Trekking Poles", "gear", 99.0),
            ("Down Vest", "outerwear", 169.0), ("Camp Stove", "gear", 79.0)]

DOCS = {
    "shipping.md": """# Shipping policy

Orders over $150 (before tax) ship free anywhere in Canada. Smaller orders pay a flat $12.

Orders placed before 2 pm Mountain Time on a business day leave the warehouse the same day.
Standard delivery takes 2 to 5 business days; Calgary and Edmonton usually get next-day delivery.
""",
    "returns.md": """# Returns and refunds

Unworn items can be returned within 30 days of delivery for a full refund.
Footwear can be returned within 60 days, even if worn outdoors once.
Refunds go back to the original payment method within 5 business days of the return arriving.
Final-sale items (marked in the order) cannot be returned.
""",
    "loyalty.md": """# Loyalty program

Customers earn 1 point per dollar spent. Gold status starts at 1,000 points in a calendar year
and gives 10% off every order plus early access to sales. Points expire after 18 months.
""",
    "faq/stoves.md": """# Camp Stove FAQ

The Camp Stove uses standard isobutane canisters (sold separately) and boils 1 litre of water in about
3.5 minutes. It is not allowed on flights, even without a canister attached.
""",
}


def main():
    db_path = HERE / "shop.db"
    db_path.unlink(missing_ok=True)
    db = sqlite3.connect(db_path)
    db.executescript("""
        create table customers (id integer primary key, name text, city text, joined date);
        create table products (id integer primary key, name text, category text, price real);
        create table orders (id integer primary key, customer_id integer, placed date, status text);
        create table order_items (order_id integer, product_id integer, qty integer, unit_price real);
    """)
    names = rng.sample([f"{f} {l}" for f in FIRST for l in LAST], 40)
    for i, n in enumerate(names, 1):
        db.execute("insert into customers values (?,?,?,?)",
                   (i, n, rng.choice(CITIES), str(date(2024, 1, 1) + timedelta(days=rng.randrange(700)))))
    for i, (n, c, p) in enumerate(PRODUCTS, 1):
        db.execute("insert into products values (?,?,?,?)", (i, n, c, p))
    oid = 0
    for _ in range(400):
        oid += 1
        placed = date(2026, 1, 1) + timedelta(days=rng.randrange(270))
        status = rng.choices(["delivered", "shipped", "returned", "cancelled"], [80, 8, 7, 5])[0]
        db.execute("insert into orders values (?,?,?,?)", (oid, rng.randint(1, 40), str(placed), status))
        for pid in rng.sample(range(1, len(PRODUCTS) + 1), rng.randint(1, 3)):
            db.execute("insert into order_items values (?,?,?,?)",
                       (oid, pid, rng.choices([1, 2, 3], [70, 22, 8])[0], PRODUCTS[pid - 1][2]))
    db.commit()
    db.close()
    for rel, text in DOCS.items():
        p = HERE / "docs" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    print("wrote", db_path, "and", len(DOCS), "documents")


if __name__ == "__main__":
    main()
