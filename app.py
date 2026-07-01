"""
app.py — Sharon Dashboard  (Streamlit entry point)

Run with:
    streamlit run dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
import pyodide_http
import requests
import streamlit as st

pyodide_http.patch_all()    ## <--- comment out this line if you want to run the app locally

# ── make sure project root is on sys.path when run as `streamlit run dashboard/app.py`
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.data import load_invoices, build_monthly_financial
from dashboard.charts import bar_chart_monthly, line_chart_cumulative
from dashboard.config import DASHBOARD_YEAR

# ─────────────────────────────────────────────────────────────────────────────
# Page configuration  (must be first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Sharon Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────────
# Custom CSS — tighten spacing, style metric cards, refine typography
# ─────────────────────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
        /* Remove top padding so the header sits high */
        .block-container { padding-top: 1.5rem; }

        /* Metric card styling */
        [data-testid="stMetric"] {
            background-color: #f0f2f6;
            border-radius: 10px;
            padding: 1rem 1.25rem;
        }
        [data-testid="stMetricLabel"] { font-size: 0.85rem; color: #555; }
        [data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; }

        /* Divider */
        hr { margin: 0.75rem 0; }

        /* Data table header */
        .section-header {
            font-size: 1rem;
            font-weight: 600;
            color: #003f5c;
            margin-bottom: 0.25rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# Header row
# ─────────────────────────────────────────────────────────────────────────────

title_col, refresh_col = st.columns([5, 1])

with title_col:
    st.title("Sharon Dashboard")

with refresh_col:
    st.write("")  # vertical alignment nudge
    st.write("")
    if st.button("🔄 Refresh Data", use_container_width=True):  # noqa: updated below when Streamlit drops deprecated arg
        load_invoices.clear()
        st.rerun()

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Load data
# ─────────────────────────────────────────────────────────────────────────────

invoices = load_invoices()
df = build_monthly_financial(invoices)

last_updated = datetime.now().strftime("%d %b %Y, %I:%M %p")

# ─────────────────────────────────────────────────────────────────────────────
# KPI metric cards
# ─────────────────────────────────────────────────────────────────────────────

# YTD values = sum of rows where actual > 0 (i.e. months that have happened)
ytd_actual  = df.loc[df["actual"] > 0, "actual"].sum()
ytd_happy   = df.loc[df["actual"] > 0, "happy_target"].sum()
ytd_stretch = df.loc[df["actual"] > 0, "stretch_target"].sum()

delta_happy   = ytd_actual - ytd_happy
delta_stretch = ytd_actual - ytd_stretch

kpi1, kpi2, kpi3 = st.columns(3)

with kpi1:
    st.metric(
        label="YTD Actual Revenue",
        value=f"${ytd_actual:,.0f}",
        delta=None,
    )


with kpi2:
    st.metric(
        label="YTD vs Happy Target",
        value=f"${ytd_happy:,.0f}",
        # delta=f"${delta_happy:+,.0f}",
        delta=delta_happy,
        format="$%+,.0f",
        delta_color="normal",
    )

with kpi3:
    st.metric(
        label="YTD vs Stretch Target",
        value=f"${ytd_stretch:,.0f}",
        delta=f"${delta_stretch:+,.0f}",
        delta_color="normal" if delta_stretch >= 0 else "inverse",
    )

st.caption(f"Last updated: {last_updated}")
st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Charts
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("Monthly Revenue")
fig_bar = bar_chart_monthly(df)
st.pyplot(fig_bar)
plt.close(fig_bar)

st.subheader("Cumulative Revenue")
fig_line = line_chart_cumulative(df)
st.pyplot(fig_line)
plt.close(fig_line)

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Data table
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<p class="section-header">Monthly breakdown</p>', unsafe_allow_html=True)

display_df = df[[
    "invoice_date_year_month",
    "actual",
    "happy_target",
    "stretch_target",
    "actual_cum_sum",
    "happy_target_cumsum",
    "stretch_target_cumsum",
]].rename(columns={
    "invoice_date_year_month": "Month",
    "actual":                  "Actual",
    "happy_target":            "Happy Target",
    "stretch_target":          "Stretch Target",
    "actual_cum_sum":          "Actual (Cumulative)",
    "happy_target_cumsum":     "Happy (Cumulative)",
    "stretch_target_cumsum":   "Stretch (Cumulative)",
})

currency_cols = [
    "Actual", "Happy Target", "Stretch Target",
    "Actual (Cumulative)", "Happy (Cumulative)", "Stretch (Cumulative)",
]

st.dataframe(
    display_df.style.format(
        {col: "${:,.0f}" for col in currency_cols},
        na_rep="—",
    ),
    hide_index=True,
)
