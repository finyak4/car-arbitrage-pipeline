"""
Streamlit dashboard — Toyota Deal Viewer
Reads from data/selected_deals.db → selected_deals table.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Toyota Deal Finder",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR = Path(os.getenv("APP_DIR", "."), "data")
DB_PATH = DATA_DIR / "selected_deals.db"

# ---------------------------------------------------------------------------
# Custom CSS — dark premium theme
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* ── Background ────────────────────────────────── */
    .stApp {
        background: linear-gradient(135deg, #0f0f1a 0%, #12121f 60%, #0d1a26 100%);
        color: #e2e8f0;
    }

    /* ── Sidebar ────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #161626 0%, #0f0f1e 100%);
        border-right: 1px solid rgba(0, 201, 167, 0.15);
    }
    [data-testid="stSidebar"] * { color: #cbd5e1 !important; }

    /* ── Metric cards ───────────────────────────────── */
    [data-testid="metric-container"] {
        background: rgba(0, 201, 167, 0.07);
        border: 1px solid rgba(0, 201, 167, 0.2);
        border-radius: 12px;
        padding: 16px 20px;
        backdrop-filter: blur(6px);
    }
    [data-testid="metric-container"] label { color: #94a3b8 !important; font-size: 0.78rem !important; }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #00c9a7 !important;
        font-weight: 700 !important;
        font-size: 1.6rem !important;
    }

    /* ── Deal cards ─────────────────────────────────── */
    .deal-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(0, 201, 167, 0.12);
        border-radius: 14px;
        padding: 18px 22px;
        margin-bottom: 12px;
        transition: border-color 0.25s, background 0.25s, transform 0.2s;
    }
    .deal-card:hover {
        border-color: rgba(0, 201, 167, 0.45);
        background: rgba(0, 201, 167, 0.06);
        transform: translateY(-2px);
        box-shadow: 0 8px 32px rgba(0, 201, 167, 0.10);
    }
    .deal-title {
        font-size: 1.05rem;
        font-weight: 600;
        color: #f1f5f9;
        margin-bottom: 6px;
    }
    .deal-badge {
        display: inline-block;
        background: rgba(0, 201, 167, 0.15);
        color: #00c9a7;
        border: 1px solid rgba(0, 201, 167, 0.3);
        border-radius: 20px;
        padding: 2px 10px;
        font-size: 0.72rem;
        font-weight: 600;
        margin-right: 6px;
        margin-bottom: 4px;
    }
    .deal-stat { color: #94a3b8; font-size: 0.82rem; }
    .deal-stat span { color: #e2e8f0; font-weight: 500; }

    /* ── Headings ───────────────────────────────────── */
    h1 { color: #00c9a7 !important; font-weight: 700 !important; }
    h2, h3 { color: #f1f5f9 !important; font-weight: 600 !important; }

    /* ── Divider ────────────────────────────────────── */
    hr { border-color: rgba(0, 201, 167, 0.15) !important; }

    /* ── Link button override ───────────────────────── */
    a[data-testid="stLinkButton"] > button, .stLinkButton > button {
        background: linear-gradient(135deg, #00c9a7, #00a086) !important;
        color: #0f0f1a !important;
        font-weight: 600 !important;
        border: none !important;
        border-radius: 8px !important;
        transition: opacity 0.2s !important;
    }
    a[data-testid="stLinkButton"] > button:hover { opacity: 0.85 !important; }

    /* ── Empty-state ────────────────────────────────── */
    .empty-state {
        text-align: center;
        padding: 60px 20px;
        color: #475569;
    }
    .empty-state .icon { font-size: 3.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data(ttl=60)
def load_deals(date_from: str | None = None, date_to: str | None = None) -> pd.DataFrame:
    """Load deals from SQLite, optionally filtering by date_added range."""
    if not DB_PATH.exists():
        return pd.DataFrame()

    with sqlite3.connect(DB_PATH) as conn:
        query = "SELECT * FROM selected_deals"
        params: list[str] = []

        conditions: list[str] = []
        if date_from:
            conditions.append("date_added >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("date_added <= ?")
            params.append(date_to)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY date_added DESC"
        df = pd.read_sql_query(query, conn, params=params)

    # Coerce numeric columns
    for col in ["year", "mileage", "engine_power", "predicted_pln", "margin_pct", "price", "engine_capacity"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


@st.cache_data(ttl=300)
def get_available_dates() -> tuple[str | None, str | None]:
    """Return (min_date, max_date) from the DB for the date picker bounds."""
    if not DB_PATH.exists():
        return None, None
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT MIN(date_added), MAX(date_added) FROM selected_deals WHERE date_added IS NOT NULL"
        ).fetchone()
    return row if row else (None, None)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
col_logo, col_title = st.columns([0.07, 0.93])
with col_logo:
    st.markdown("<div style='font-size:2.8rem;padding-top:6px'>🚗</div>", unsafe_allow_html=True)
with col_title:
    st.markdown("# Toyota Deal Finder")
    st.markdown(
        "<p style='color:#64748b;margin-top:-12px;font-size:0.9rem'>"
        "Curated arbitrage opportunities — predicted Polish market price vs. listing price"
        "</p>",
        unsafe_allow_html=True,
    )
st.markdown("---")


# ---------------------------------------------------------------------------
# Sidebar — filters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🔍 Filters")
    st.markdown("---")

    # Date range
    st.markdown("### 📅 Date Added")
    min_d, max_d = get_available_dates()

    use_date_filter = st.toggle("Filter by date", value=False)
    date_from_val: str | None = None
    date_to_val: str | None = None

    if use_date_filter:
        import datetime

        default_start = datetime.date.fromisoformat(min_d) if min_d else datetime.date.today()
        default_end = datetime.date.fromisoformat(max_d) if max_d else datetime.date.today()

        d_from = st.date_input(
            "From",
            value=default_start,
            format="YYYY-MM-DD",
            key="date_from",
        )
        d_to = st.date_input(
            "To",
            value=default_end,
            format="YYYY-MM-DD",
            key="date_to",
        )

        if d_from and d_to:
            date_from_val = str(d_from)
            date_to_val = str(d_to)

    st.markdown("---")

    # Load data for filter options
    all_df = load_deals()

    # Model filter
    st.markdown("### 🏎️ Model")
    models = sorted(all_df["model"].dropna().unique().tolist()) if not all_df.empty else []
    sel_models = st.multiselect("Select models", models, placeholder="All models")

    # Fuel type filter
    st.markdown("### ⛽ Fuel Type")
    fuels = sorted(all_df["fuel_type"].dropna().unique().tolist()) if not all_df.empty else []
    sel_fuels = st.multiselect("Select fuel types", fuels, placeholder="All fuel types")

    # Body type filter
    st.markdown("### 🚙 Body Type")
    bodies = sorted(all_df["body_type"].dropna().unique().tolist()) if not all_df.empty else []
    sel_bodies = st.multiselect("Select body types", bodies, placeholder="All body types")

    # Margin slider
    st.markdown("### 📈 Min Margin %")
    min_margin = st.slider("Minimum margin", min_value=0, max_value=100, value=0, step=1, format="%d%%")

    st.markdown("---")
    if st.button("🔄 Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ---------------------------------------------------------------------------
# Load + filter data
# ---------------------------------------------------------------------------
df = load_deals(date_from=date_from_val, date_to=date_to_val)

if not df.empty:
    if sel_models:
        df = df[df["model"].isin(sel_models)]
    if sel_fuels:
        df = df[df["fuel_type"].isin(sel_fuels)]
    if sel_bodies:
        df = df[df["body_type"].isin(sel_bodies)]
    if min_margin > 0 and "margin_pct" in df.columns:
        df = df[df["margin_pct"] >= min_margin / 100]


# ---------------------------------------------------------------------------
# Metrics row
# ---------------------------------------------------------------------------
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Total Deals", len(df))
with m2:
    avg_margin = df["margin_pct"].mean() * 100 if not df.empty and "margin_pct" in df.columns else 0
    st.metric("Avg Margin", f"{avg_margin:.1f}%")
with m3:
    avg_pred = df["predicted_pln"].mean() if not df.empty and "predicted_pln" in df.columns else 0
    st.metric("Avg Predicted (PLN)", f"{avg_pred:,.0f}")
with m4:
    avg_list = df["price"].mean() if not df.empty and "price" in df.columns else 0
    st.metric("Avg Listed Price", f"{avg_list:,.0f}")

st.markdown("---")

# ---------------------------------------------------------------------------
# Deal cards
# ---------------------------------------------------------------------------
if df.empty:
    st.markdown(
        """
        <div class="empty-state">
            <div class="icon">🔍</div>
            <h3 style="color:#475569">No deals found</h3>
            <p style="color:#334155">Try adjusting your filters or refresh the data.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(f"### Showing {len(df)} deal{'s' if len(df) != 1 else ''}")

    for _, row in df.iterrows():
        model_name = row.get("model", "Unknown Model")
        year = int(row["year"]) if pd.notna(row.get("year")) else "—"
        mileage = f"{int(row['mileage']):,} km" if pd.notna(row.get("mileage")) else "—"
        fuel = row.get("fuel_type") or "—"
        power = f"{int(row['engine_power'])} HP" if pd.notna(row.get("engine_power")) else "—"
        body = row.get("body_type") or "—"
        gearbox = row.get("gearbox") or "—"
        predicted = f"{float(row['predicted_pln']):,.0f} PLN" if pd.notna(row.get("predicted_pln")) else "—"
        listed = f"{float(row['price']):,.0f} PLN" if pd.notna(row.get("price")) else "—"
        margin = f"{float(row['margin_pct']) * 100:.1f}%" if pd.notna(row.get("margin_pct")) else "—"
        date_added = row.get("date_added") or "—"
        url = row.get("url", "")

        margin_color = "#00c9a7" if pd.notna(row.get("margin_pct")) and row["margin_pct"] > 0.25 else "#f59e0b"

        card_html = f"""
        <div class="deal-card">
            <div class="deal-title">{year} &nbsp;{model_name}</div>
            <div style="margin-bottom:10px">
                <span class="deal-badge">{fuel}</span>
                <span class="deal-badge">{body}</span>
                <span class="deal-badge">{gearbox}</span>
            </div>
            <div style="display:flex;flex-wrap:wrap;gap:20px;margin-bottom:6px">
                <div class="deal-stat">🛣️ Mileage &nbsp;<span>{mileage}</span></div>
                <div class="deal-stat">⚡ Power &nbsp;<span>{power}</span></div>
                <div class="deal-stat">🏷️ Listed &nbsp;<span>{listed}</span></div>
                <div class="deal-stat">🎯 Predicted &nbsp;<span>{predicted}</span></div>
                <div class="deal-stat">📈 Margin &nbsp;<span style="color:{margin_color};font-weight:700">{margin}</span></div>
                <div class="deal-stat">📅 Added &nbsp;<span>{date_added}</span></div>
            </div>
        </div>
        """
        col_card, col_btn = st.columns([0.85, 0.15])
        with col_card:
            st.markdown(card_html, unsafe_allow_html=True)
        with col_btn:
            # Vertically centre the button relative to the card
            st.markdown("<div style='padding-top:30px'></div>", unsafe_allow_html=True)
            if url:
                st.link_button("🔗 Visit", url, use_container_width=True)
            else:
                st.markdown("<span style='color:#475569;font-size:0.8rem'>No URL</span>", unsafe_allow_html=True)
