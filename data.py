"""
data.py — Data loading and transformation for Sharon Dashboard.

All Xero API calls happen here.  Results are cached by Streamlit for 1 hour
so the API is not called on every page interaction.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

from xero_client import XeroAuth, XeroClient
from config import (
    HAPPY_TARGETS,
    STRETCH_TARGETS,
    INVOICE_START_DATE,
    DASHBOARD_YEAR,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def financial_year(input_date) -> str:
    """
    Return the Australian financial year label for a given date.

    Examples:
        2025-06-30  →  "FY2025"
        2025-07-01  →  "FY2026"
    """
    if isinstance(input_date, str):
        input_date = datetime.strptime(input_date, "%Y-%m-%d").date()
    fy = input_date.year + 1 if input_date.month >= 7 else input_date.year
    return f"FY{fy}"


# ─────────────────────────────────────────────────────────────────────────────
# Data loading  (cached — Xero API called at most once per hour)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner="Fetching data from Xero…")
def load_invoices() -> pd.DataFrame:
    """
    Fetch all invoices from Xero, apply standard filters, and return a
    cleaned DataFrame.

    Token file is resolved relative to the project root so the app works
    regardless of which directory it is launched from.
    """
    token_path = PROJECT_ROOT / "tokens" / "xero_tokens.json"
    auth = XeroAuth(token_file=str(token_path))
    client = XeroClient(auth=auth)

    invoices = pd.DataFrame(client.get_invoices())

    # parse dates
    invoices["DateString"] = pd.to_datetime(invoices["DateString"])

    # filter: issued invoices only, paid or authorised, from start date
    invoices = (
        invoices
        .query(
            "Type=='ACCREC' "
            "& Status.isin(['PAID', 'AUTHORISED']) "
            f"& DateString >= '{INVOICE_START_DATE}'"
        )
        .assign(
            invoice_date_year_month=lambda x: x["DateString"].dt.strftime("%Y-%m"),
            invoice_date_financial_year=lambda x: x["DateString"].apply(financial_year),
        )
    )
    return invoices


def build_monthly_financial(invoices: pd.DataFrame) -> pd.DataFrame:
    """
    Build the monthly financials DataFrame for the dashboard year,
    joining actuals against happy/stretch targets and computing
    cumulative sums.
    """
    months = [f"{DASHBOARD_YEAR}-{str(i).zfill(2)}" for i in range(1, 13)]

    targets = pd.DataFrame({
        "invoice_date_year_month": months,
        "happy_target":   HAPPY_TARGETS,
        "stretch_target": STRETCH_TARGETS,
    })

    # actuals for the dashboard year only
    actuals = (
        invoices
        .query(f"DateString >= '{DASHBOARD_YEAR}-01-01'")
        .groupby("invoice_date_year_month", as_index=False)
        .agg(actual=("SubTotal", "sum"))
    )

    df = (
        targets
        .merge(actuals, how="left", on="invoice_date_year_month")
        .fillna({"actual": 0})
        .assign(
            actual_cum_sum=lambda x: x["actual"].cumsum(),
            happy_target_cumsum=lambda x: x["happy_target"].cumsum(),
            stretch_target_cumsum=lambda x: x["stretch_target"].cumsum(),
        )
        # mask future months (no actual data) so the cumulative line doesn't
        # extend as a flat zero
        .assign(
            actual_cum_sum=lambda x: np.where(
                x["actual"] == 0, np.nan, x["actual_cum_sum"]
            )
        )
    )
    return df
