"""Evaluation tasks with answers computed from the demo data, so the expected values are always right."""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "examples" / "shop.db"


def one(db, sql, *args):
    return db.execute(sql, args).fetchone()


def build():
    db = sqlite3.connect(DB)
    spend = """select c.name, round(sum(oi.qty * oi.unit_price), 2) s from orders o
               join order_items oi on oi.order_id = o.id join customers c on c.id = o.customer_id
               where o.status = 'delivered' and o.placed between ? and ? group by c.id order by s desc limit 1"""
    tasks = []

    name, total = one(db, spend, "2026-03-01", "2026-03-31")
    tasks.append({"id": "top_march", "q": "Which customer spent the most on delivered orders in March 2026, and how much?",
                  "expect": [name.split()[0], f"{total:,.0f}"], "kind": "db"})

    name, total = one(db, spend, "2026-06-01", "2026-06-30")
    tasks.append({"id": "top_june_ship", "q": "Who was the top spender on delivered orders in June 2026, and would an order "
                  "of that total ship free under our shipping policy?",
                  "expect": [name.split()[0], "free" if total > 150 else "12"], "kind": "db+docs"})

    (n,) = one(db, "select count(*) from orders where status = 'returned'")
    tasks.append({"id": "returned_count", "q": "How many orders have the status 'returned'?", "expect": [str(n)], "kind": "db"})

    p, q = one(db, """select p.name, sum(oi.qty) q from order_items oi join products p on p.id = oi.product_id
                      group by p.id order by q desc limit 1""")
    tasks.append({"id": "best_seller", "q": "Which product has sold the most units across all orders?",
                  "expect": [p.split()[0]], "kind": "db"})

    city, n = one(db, "select city, count(*) n from customers group by city order by n desc limit 1")
    tasks.append({"id": "top_city", "q": "Which city has the most customers?", "expect": [city], "kind": "db"})

    (rev,) = one(db, """select round(sum(oi.qty * oi.unit_price), 2) from orders o join order_items oi on oi.order_id = o.id
                        join products p on p.id = oi.product_id where p.category = 'outerwear' and o.status = 'delivered'""")
    tasks.append({"id": "outerwear_rev", "q": "What is the total revenue from delivered orders in the outerwear category?",
                  "expect": [f"{rev:,.0f}"], "kind": "db"})

    tasks += [
        {"id": "shoe_returns", "q": "How long do customers have to return trail running shoes?", "expect": ["60"], "kind": "docs"},
        {"id": "gold", "q": "How many loyalty points do you need for Gold status, and what discount does it give?",
         "expect": ["1,000", "10"], "kind": "docs"},
        {"id": "stove_flight", "q": "Can I take the Camp Stove on a plane?", "expect": ["not"], "kind": "docs"},
        {"id": "small_order_ship", "q": "What does shipping cost for a $40 order?", "expect": ["12"], "kind": "docs"},
    ]

    (price,) = one(db, "select price from products where name = 'Camp Stove'")
    tasks.append({"id": "stove_ship", "q": "If I buy two Camp Stoves, does my order ship free?",
                  "expect": ["free" if 2 * price > 150 else "12"], "kind": "db+docs"})

    name, pts = one(db, """select c.name, sum(oi.qty * oi.unit_price) s from orders o join order_items oi on oi.order_id = o.id
                           join customers c on c.id = o.customer_id where o.status = 'delivered'
                           and o.placed between '2026-01-01' and '2026-12-31' group by c.id order by s desc limit 1""")
    tasks.append({"id": "gold_customer", "q": "Did the customer who spent the most on delivered orders in 2026 reach Gold "
                  "loyalty status? Say who it is.", "expect": [name.split()[0], ["yes", "reached", "qualif", "has gold", "achieved"] if pts >= 1000
                                                else ["no", "not reach", "did not", "didn't"]],
                  "kind": "db+docs"})
    return tasks


def score(answer: str, expect: list) -> bool:
    """Every item must appear in the answer; an item can be a list of acceptable alternatives."""
    a = answer.lower().replace(",", "")
    norm = lambda x: x.lower().replace(",", "")  # noqa: E731
    return all(any(norm(o) in a for o in (e if isinstance(e, list) else [e])) for e in expect)
