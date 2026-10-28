"""Step 4: persist bills in SQLite so spending can be tracked over time."""
import sqlite3
from pathlib import Path

import pandas as pd

from schema import Bill

DB = Path(__file__).parent / "bills.db"


def _conn():
    return sqlite3.connect(DB)


def init():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS bills(
            id INTEGER PRIMARY KEY AUTOINCREMENT, store TEXT, address TEXT, date TEXT,
            currency TEXT, subtotal REAL, tax REAL, discount REAL, total REAL,
            payment TEXT, filename TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS items(
            id INTEGER PRIMARY KEY AUTOINCREMENT, bill_id INTEGER REFERENCES bills(id),
            name TEXT, quantity REAL, unit_price REAL, total_price REAL, category TEXT);
        """)


def save_bill(b: Bill, filename: str) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO bills(store,address,date,currency,subtotal,tax,discount,total,payment,filename) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (b.store_name, b.store_address, b.date, b.currency, b.subtotal, b.tax,
             b.discount, b.total, b.payment_method, filename))
        bid = cur.lastrowid
        c.executemany(
            "INSERT INTO items(bill_id,name,quantity,unit_price,total_price,category) VALUES(?,?,?,?,?,?)",
            [(bid, i.name, i.quantity, i.unit_price, i.total_price, i.category) for i in b.items])
        return bid


def load_items() -> pd.DataFrame:
    with _conn() as c:
        df = pd.read_sql_query(
            "SELECT i.name, i.quantity, i.unit_price, i.total_price, i.category, "
            "b.id AS bill_id, b.store, b.date, b.currency "
            "FROM items i JOIN bills b ON b.id = i.bill_id", c)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def load_bills() -> pd.DataFrame:
    with _conn() as c:
        return pd.read_sql_query(
            "SELECT id, store, date, currency, subtotal, tax, discount, total, payment, filename FROM bills "
            "ORDER BY date DESC", c)


def delete_bill(bill_id: int):
    with _conn() as c:
        c.execute("DELETE FROM items WHERE bill_id=?", (bill_id,))
        c.execute("DELETE FROM bills WHERE id=?", (bill_id,))
