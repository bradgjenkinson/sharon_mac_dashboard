"""
charts.py — Chart builder functions for Sharon Dashboard.

Each function accepts the monthly_financial DataFrame and returns a
matplotlib Figure ready for st.pyplot().  plt.close(fig) is called
internally so callers don't need to manage figure cleanup.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.lines import Line2D
import seaborn as sns
import pandas as pd

from dashboard.config import COL_ACTUAL, COL_HAPPY, COL_STRETCH


def _apply_theme() -> None:
    """Apply a consistent seaborn theme to all charts."""
    sns.set_theme(style="whitegrid", font_scale=1.05)


def _currency_formatter(x, _) -> str:
    """Format y-axis tick labels as compact currency (e.g. $12k)."""
    if x >= 1_000:
        return f"${x/1_000:,.0f}k"
    return f"${x:,.0f}"


# ─────────────────────────────────────────────────────────────────────────────
# Chart 1 — Monthly bar chart with target lines
# ─────────────────────────────────────────────────────────────────────────────

def bar_chart_monthly(df: pd.DataFrame) -> plt.Figure:
    """
    Grouped bar chart of monthly actuals with horizontal lines for
    happy and stretch targets per month.

    Returns a Figure; the caller should pass it to st.pyplot().
    """
    _apply_theme()

    fig, ax = plt.subplots(figsize=(12, 5))

    # — actuals bar —
    sns.barplot(
        data=df,
        x="invoice_date_year_month",
        y="actual",
        color=COL_ACTUAL,
        ax=ax,
    )
    ax.set(xlabel="Month", ylabel="Revenue", title="Monthly Revenue 2026")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_currency_formatter))

    # — data labels inside bars —
    for container in ax.containers:
        ax.bar_label(
            container,
            padding=-20,
            color="white",
            fmt="${:,.0f}",
            fontsize=9,
        )

    # — target hlines per month —
    bar_width = 0.8
    half_width = bar_width / 2

    for i, row in enumerate(df.itertuples()):
        ax.hlines(
            y=row.happy_target,
            xmin=i - half_width,
            xmax=i + half_width,
            color=COL_HAPPY,
            linewidth=2,
        )
        ax.hlines(
            y=row.stretch_target,
            xmin=i - half_width,
            xmax=i + half_width,
            color=COL_STRETCH,
            linewidth=2,
        )

    # — legend —
    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, color=COL_ACTUAL, label="Actual"),
        Line2D([0], [0], color=COL_HAPPY,   lw=2, label="Happy Target"),
        Line2D([0], [0], color=COL_STRETCH, lw=2, label="Stretch Target"),
    ]
    ax.legend(handles=legend_handles, bbox_to_anchor=(1.01, 1), loc="upper left")

    plt.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Chart 2 — Cumulative line chart
# ─────────────────────────────────────────────────────────────────────────────

def line_chart_cumulative(df: pd.DataFrame) -> plt.Figure:
    """
    Line chart of cumulative actuals vs cumulative happy and stretch targets.

    Returns a Figure; the caller should pass it to st.pyplot().
    """
    _apply_theme()

    fig, ax = plt.subplots(figsize=(12, 5))

    sns.lineplot(
        data=df,
        x="invoice_date_year_month",
        y="actual_cum_sum",
        color=COL_ACTUAL,
        label="Actual",
        marker="o",
        ax=ax,
    )
    sns.lineplot(
        data=df,
        x="invoice_date_year_month",
        y="happy_target_cumsum",
        color=COL_HAPPY,
        label="Happy Target",
        marker="o",
        ax=ax,
    )
    sns.lineplot(
        data=df,
        x="invoice_date_year_month",
        y="stretch_target_cumsum",
        color=COL_STRETCH,
        label="Stretch Target",
        marker="o",
        ax=ax,
    )

    ax.set(xlabel="Month", ylabel="Cumulative Revenue", title="Cumulative Revenue 2026")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_currency_formatter))
    ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left")

    plt.tight_layout()
    return fig
