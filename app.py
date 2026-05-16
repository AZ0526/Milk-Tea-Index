# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path

DB_PATH = "milk_tea.db"
SEED_CSV = Path.home() / "OneDrive" / "桌面" / "BevFood" / "product_lists_combined.csv"


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                client    TEXT NOT NULL,
                category  TEXT NOT NULL,
                item_name TEXT NOT NULL,
                sku       TEXT DEFAULT '',
                cost      TEXT DEFAULT ''
            )
        """)
        count = c.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count == 0 and Path(SEED_CSV).exists():
            df = pd.read_csv(
                SEED_CSV,
                names=["client", "category", "item_name", "sku", "cost"],
                skiprows=1,
            )
            df = df[df["item_name"].notna() & (df["item_name"].str.strip() != "")]
            df["sku"]  = df["sku"].fillna("").astype(str).replace("nan", "")
            df["cost"] = df["cost"].fillna("").astype(str).replace("nan", "")
            df[["client", "category", "item_name", "sku", "cost"]].to_sql(
                "products", c, if_exists="append", index=False
            )


def fetch_all() -> pd.DataFrame:
    with get_conn() as c:
        return pd.read_sql(
            "SELECT * FROM products ORDER BY client, category, item_name", c
        )


def fetch_distinct(col: str) -> list[str]:
    with get_conn() as c:
        rows = c.execute(
            f"SELECT DISTINCT {col} FROM products ORDER BY {col}"
        ).fetchall()
    return [r[0] for r in rows]


def insert_item(client, category, item_name, sku, cost):
    with get_conn() as c:
        c.execute(
            "INSERT INTO products (client,category,item_name,sku,cost) VALUES (?,?,?,?,?)",
            (client, category, item_name, sku, cost),
        )


def update_item(id_, client, category, item_name, sku, cost):
    with get_conn() as c:
        c.execute(
            "UPDATE products SET client=?,category=?,item_name=?,sku=?,cost=? WHERE id=?",
            (client, category, item_name, sku, cost, id_),
        )


def delete_item(id_):
    with get_conn() as c:
        c.execute("DELETE FROM products WHERE id=?", (id_,))


# ── Pages ─────────────────────────────────────────────────────────────────────

def page_add():
    st.header("Add New Item")

    clients    = fetch_distinct("client")
    categories = fetch_distinct("category")

    with st.form("add_form", clear_on_submit=True):
        st.markdown("**Client Name**")
        c1, c2 = st.columns(2)
        with c1:
            client_sel = st.selectbox("Select existing client", [""] + clients, label_visibility="collapsed")
        with c2:
            client_new = st.text_input("Or type a new client name", placeholder="New client…")

        st.markdown("**Category**")
        c3, c4 = st.columns(2)
        with c3:
            cat_sel = st.selectbox("Select existing category", [""] + categories, label_visibility="collapsed")
        with c4:
            cat_new = st.text_input("Or type a new category", placeholder="New category…")

        item_name = st.text_input("Item Name *")

        submitted = st.form_submit_button("Add Item", type="primary", use_container_width=True)

    if submitted:
        final_client = client_new.strip() or client_sel
        final_cat    = cat_new.strip()    or cat_sel

        if not final_client:
            st.error("Client name is required.")
        elif not final_cat:
            st.error("Category is required.")
        elif not item_name.strip():
            st.error("Item name is required.")
        else:
            insert_item(final_client, final_cat, item_name.strip(), "", "")
            st.success(f"✅ **{item_name.strip()}** added to **{final_client} / {final_cat}**.")


def page_edit_delete():
    st.header("Edit / Delete Items")

    df = fetch_all()
    if df.empty:
        st.info("No items in the database yet.")
        return

    # ── Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        f_client = st.selectbox("Client", ["All"] + sorted(df["client"].unique().tolist()))
    with col2:
        f_cat = st.selectbox("Category", ["All"] + sorted(df["category"].unique().tolist()))
    with col3:
        f_search = st.text_input("Search item name", placeholder="Type to filter…")

    filtered = df.copy()
    if f_client != "All":
        filtered = filtered[filtered["client"] == f_client]
    if f_cat != "All":
        filtered = filtered[filtered["category"] == f_cat]
    if f_search.strip():
        filtered = filtered[
            filtered["item_name"].str.contains(f_search.strip(), case=False, na=False)
        ]

    st.dataframe(
        filtered[["id", "client", "category", "item_name", "sku", "cost"]].rename(
            columns={"id": "ID", "client": "Client", "category": "Category",
                     "item_name": "Item Name", "sku": "SKU", "cost": "Cost"}
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(f"{len(filtered)} item(s) shown")

    if filtered.empty:
        return

    st.divider()
    st.subheader("Select an item to edit or delete")

    label_map = {
        row["id"]: f"[{row['id']}]  {row['client']}  ›  {row['category']}  ›  {row['item_name']}"
        for _, row in filtered.iterrows()
    }
    selected_id = st.selectbox(
        "Item", options=list(label_map.keys()), format_func=lambda x: label_map[x]
    )

    row = df[df["id"] == selected_id].iloc[0]
    all_clients    = fetch_distinct("client")
    all_categories = fetch_distinct("category")

    with st.form("edit_form"):
        ec1, ec2 = st.columns(2)
        with ec1:
            e_client = st.selectbox(
                "Client Name",
                all_clients,
                index=all_clients.index(row["client"]) if row["client"] in all_clients else 0,
            )
        with ec2:
            e_cat = st.selectbox(
                "Category",
                all_categories,
                index=all_categories.index(row["category"]) if row["category"] in all_categories else 0,
            )
        e_name = st.text_input("Item Name", value=row["item_name"])
        e_sku  = st.text_input("SKU",  value=row["sku"]  or "")
        e_cost = st.text_input("Cost", value=row["cost"] or "")

        btn1, btn2 = st.columns(2)
        with btn1:
            save = st.form_submit_button("Save Changes", type="primary", use_container_width=True)
        with btn2:
            remove = st.form_submit_button("Delete Item", use_container_width=True)

    if save:
        if not e_name.strip():
            st.error("Item name cannot be empty.")
        else:
            update_item(selected_id, e_client, e_cat, e_name.strip(), e_sku.strip(), e_cost.strip())
            st.success("✅ Item updated.")
            st.rerun()

    if remove:
        delete_item(selected_id)
        st.success("🗑️ Item deleted.")
        st.rerun()


def page_import_export():
    st.header("Import / Export")

    # Export
    st.subheader("Export")
    df = fetch_all()
    st.download_button(
        label="Download all data as CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="milk_tea_products.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.divider()

    # Import
    st.subheader("Import")
    st.info(
        "Upload a CSV with columns: **client** (or *store*), **category**, **item_name**. "
        "SKU and cost columns are optional."
    )
    uploaded = st.file_uploader("Choose a CSV file", type="csv")

    if uploaded:
        try:
            imp = pd.read_csv(uploaded)
            imp.columns = [c.lower().strip().replace(" ", "_") for c in imp.columns]
            imp = imp.rename(columns={"store": "client", "client_name": "client"})

            required = {"client", "category", "item_name"}
            missing = required - set(imp.columns)
            if missing:
                st.error(f"Missing required columns: {missing}. Found: {list(imp.columns)}")
                return

            imp = imp[imp["item_name"].notna()]
            st.dataframe(imp.head(10), use_container_width=True, hide_index=True)
            st.caption(f"{len(imp)} row(s) ready to import")

            if st.button("Confirm Import", type="primary", use_container_width=True):
                for _, r in imp.iterrows():
                    insert_item(
                        str(r.get("client", "")),
                        str(r.get("category", "")),
                        str(r["item_name"]),
                        str(r.get("sku", "") or ""),
                        str(r.get("cost", "") or ""),
                    )
                st.success(f"✅ {len(imp)} items imported.")
                st.rerun()

        except Exception as e:
            st.error(f"Failed to read CSV: {e}")


# ── App shell ─────────────────────────────────────────────────────────────────

PAGES = {
    "➕  Add Item":       page_add,
    "✏️  Edit / Delete":  page_edit_delete,
    "📥  Import / Export": page_import_export,
}


def main():
    st.set_page_config(
        page_title="Milk Tea Ingredient Manager",
        page_icon="🧋",
        layout="wide",
    )
    init_db()

    with st.sidebar:
        st.title("🧋 MTI Manager")
        st.caption("Milk Tea Ingredient Manager")
        st.divider()
        choice = st.radio("Navigation", list(PAGES.keys()), label_visibility="collapsed")

    PAGES[choice]()


if __name__ == "__main__":
    main()
