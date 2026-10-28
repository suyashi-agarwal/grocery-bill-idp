"""Grocery Bill IDP: upload -> extract -> validate -> review -> save -> analyse -> ask."""
import pandas as pd
import streamlit as st

import storage
from extractor import answer_question, extract_bill
from schema import CATEGORIES, Bill, LineItem
from validate import validate_bill
from typing import Optional

bill: Optional[Bill] = st.session_state.get("bill")
st.set_page_config(page_title="Grocery Bill IDP", page_icon="🧾", layout="wide")
storage.init()
st.title("🧾 Grocery Bill Reader")

tab_up, tab_dash, tab_ask = st.tabs(["Upload bill", "My purchases", "Ask a question"])


def _num(v):
    return None if v is None or pd.isna(v) else float(v)


# ---------------------------------------------------------------- upload
with tab_up:
    f = st.file_uploader("Upload a bill (photo or PDF)", type=["jpg", "jpeg", "png", "webp", "pdf"])
    if f:
        if not f.name.lower().endswith(".pdf"):
            st.image(f, width=320)
        if st.button("Extract details", type="primary"):
            with st.spinner("Reading your bill..."):
                try:
                    st.session_state.bill = extract_bill(f.getvalue(), f.name)
                    st.session_state.fname = f.name
                except Exception as e:
                    st.error(f"Extraction failed: {e}")



    bill: Optional[Bill] = st.session_state.get("bill")
    if bill:
        st.subheader("Review & correct")
        c1, c2, c3 = st.columns(3)
        store = c1.text_input("Store", bill.store_name or "")
        date = c2.text_input("Date (YYYY-MM-DD)", bill.date or "")
        currency = c3.text_input("Currency", bill.currency or "")

        df = pd.DataFrame([i.model_dump() for i in bill.items])
        edited = st.data_editor(
            df, num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={"category": st.column_config.SelectboxColumn(options=CATEGORIES)})

        d1, d2, d3, d4 = st.columns(4)
        subtotal = d1.number_input("Subtotal", value=bill.subtotal or 0.0, format="%.2f")
        tax = d2.number_input("Tax", value=bill.tax or 0.0, format="%.2f")
        discount = d3.number_input("Discount", value=bill.discount or 0.0, format="%.2f")
        total = d4.number_input("Total paid", value=bill.total or 0.0, format="%.2f")

        items = [
            LineItem(name=r["name"], quantity=_num(r["quantity"]) or 1, unit_price=_num(r["unit_price"]),
                     total_price=_num(r["total_price"]) or 0.0, category=r["category"] or "Other")
            for r in edited.to_dict("records") if r.get("name")
        ]
        current = Bill(store_name=store or None, date=date or None, currency=currency or None,
                       items=items, subtotal=subtotal or None, tax=tax or None,
                       discount=discount or None, total=total or None,
                       store_address=bill.store_address, payment_method=bill.payment_method)

        warnings = validate_bill(current)
        if warnings:
            for w in warnings:
                st.warning(w)
        else:
            st.success("All checks passed: items and totals are consistent.")

        if st.button("Save bill"):
            storage.save_bill(current, st.session_state.get("fname", ""))
            st.session_state.pop("bill")
            st.success("Saved. See the 'My purchases' tab.")
            st.rerun()

# ------------------------------------------------------------- dashboard
with tab_dash:
    items = storage.load_items()
    if items.empty:
        st.info("No bills saved yet. Upload one first.")
    else:
        bills = storage.load_bills()
        m1, m2, m3 = st.columns(3)
        m1.metric("Bills", len(bills))
        m2.metric("Total spent", f"{items['total_price'].sum():,.2f}")
        m3.metric("Items bought", int(items["quantity"].sum()))

        left, right = st.columns(2)
        left.subheader("Spend by category")
        left.bar_chart(items.groupby("category")["total_price"].sum().sort_values(ascending=False))
        right.subheader("Spend by store")
        right.bar_chart(items.groupby("store")["total_price"].sum().sort_values(ascending=False))

        st.subheader("Most frequently bought")
        st.dataframe(items.groupby("name").agg(times=("name", "size"), spent=("total_price", "sum"))
                     .sort_values("times", ascending=False).head(10), use_container_width=True)

        st.subheader("All items")
        st.dataframe(items, use_container_width=True, hide_index=True)
        st.download_button("Download CSV", items.to_csv(index=False), "purchases.csv", "text/csv")

        with st.expander("Manage bills"):
            st.dataframe(bills, use_container_width=True, hide_index=True)
            bid = st.number_input("Bill id to delete", min_value=0, step=1)
            if st.button("Delete bill") and bid:
                storage.delete_bill(int(bid))
                st.rerun()

# ------------------------------------------------------------------- ask
with tab_ask:
    items = storage.load_items()
    if items.empty:
        st.info("Save at least one bill to ask questions.")
    else:
        q = st.text_input("Ask about your purchases", placeholder="How much did I spend on dairy this month?")
        if q:
            with st.spinner("Thinking..."):
                st.write(answer_question(q, items.tail(500).to_csv(index=False)))
