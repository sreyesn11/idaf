from __future__ import annotations

import streamlit as st

from core.constants import BASE_DIR

LOGO_PATH = BASE_DIR / "assets" / "logo_unal.png"

PRIMARY_COLOR = "#94b43b"
PRIMARY_COLOR_DARK = "#6f872c"
SURFACE_COLOR = "#f2f6e9"

_STATE_BADGE_COLORS = {
    "HEALTHY": "#2ecc71",
    "WARNING": "#f1c40f",
    "DEGRADED": "#e67e22",
    "CRITICAL": "#e74c3c",
    "UNREACHABLE": "#e74c3c",
    "UNKNOWN": "#95a5a6",
}


def _inject_css() -> None:
    st.markdown(
        f"""
        <style>
        [data-testid="stSidebarNav"] {{
            padding-top: 0.5rem;
        }}
        [data-testid="stSidebarNav"] a {{
            border-radius: 8px;
            margin: 2px 6px;
        }}
        [data-testid="stSidebarNav"] a:hover {{
            background-color: {SURFACE_COLOR};
        }}
        [data-testid="stMetric"] {{
            background-color: {SURFACE_COLOR};
            border-left: 4px solid {PRIMARY_COLOR};
            border-radius: 10px;
            padding: 0.9rem 1rem 0.6rem;
        }}
        [data-testid="stMetricLabel"] {{
            font-weight: 600;
        }}
        h1 {{
            color: {PRIMARY_COLOR_DARK};
            border-bottom: 3px solid {PRIMARY_COLOR};
            padding-bottom: 0.3rem;
        }}
        div.stButton > button[kind="primary"] {{
            background-color: {PRIMARY_COLOR};
            border-radius: 8px;
        }}
        div.stButton > button[kind="primary"]:hover {{
            background-color: {PRIMARY_COLOR_DARK};
        }}
        div[data-testid="stExpander"] {{
            border: 1px solid {SURFACE_COLOR};
            border-radius: 10px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_branding() -> None:
    """Injects the UNAL logo in the sidebar and the app-wide visual theme.

    Call once near the top of every page, right after `st.set_page_config`.
    """
    _inject_css()
    with st.sidebar:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            st.image(str(LOGO_PATH), width=120)


def state_badge(state: str) -> str:
    """Small inline colored pill for a DiagnosticState value, for use in st.markdown."""
    color = _STATE_BADGE_COLORS.get(state, "#95a5a6")
    return (
        f'<span style="background-color:{color};color:white;padding:2px 10px;'
        f'border-radius:12px;font-size:0.85rem;font-weight:600;">{state}</span>'
    )
