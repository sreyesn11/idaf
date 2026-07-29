from __future__ import annotations

import streamlit as st

from core.constants import BASE_DIR

LOGO_PATH = BASE_DIR / "assets" / "logo_unal.png"

PRIMARY_COLOR = "#94b43b"
PRIMARY_COLOR_DARK = "#6f872c"
SURFACE_COLOR = "#f2f6e9"
TEXT_COLOR = "#1b1b1b"

# Radius scale (DESIGN.md "Shapes"): sm for controls, md for containers.
RADIUS_SM = "8px"
RADIUS_MD = "12px"

# Single source of truth for diagnostic-state colors, shared by
# core/branding.py (state_badge) and topology/renderer.py — do not redefine
# this dict elsewhere. Values are the vivid background colors used for
# quick scanning; state_badge() and the topology nodes always pair them
# with TEXT_COLOR (dark), never white, so contrast stays >= 4.5:1 (WCAG AA)
# for every state (verified: HEALTHY 8.2:1, WARNING 10.4:1, DEGRADED 6.1:1,
# CRITICAL 4.5:1, UNKNOWN 6.7:1 — white text instead ranges 1.7:1-3.8:1
# and fails AA in all five cases).
STATE_COLORS: dict[str, str] = {
    "HEALTHY": "#2ecc71",
    "WARNING": "#f1c40f",
    "DEGRADED": "#e67e22",
    "CRITICAL": "#e74c3c",
    "UNREACHABLE": "#e74c3c",
    "UNKNOWN": "#95a5a6",
}

# Darker, same-hue variants for colored *text* on a light/white background
# (e.g. the topology link label). The raw STATE_COLORS values fail AA there
# too (1.7:1-3.8:1 on white); these all clear 4.5:1.
STATE_TEXT_ON_LIGHT_COLORS: dict[str, str] = {
    "HEALTHY": "#1e8449",
    "WARNING": "#8a6d00",
    "DEGRADED": "#a8500a",
    "CRITICAL": "#c0392b",
    "UNREACHABLE": "#c0392b",
    "UNKNOWN": "#5d6d7e",
}

# Kept for backwards compatibility with any external reference; prefer
# STATE_COLORS for new code.
_STATE_BADGE_COLORS = STATE_COLORS


def _inject_css() -> None:
    st.markdown(
        f"""
        <style>
        /* Fetched from Google Fonts CDN. If the lab LAN has no general internet
        egress this silently falls back to the system sans-serif stack below —
        an accepted, legible degradation, not a broken state. */
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
        html, body, [class*="css"] {{
            font-family: "IBM Plex Sans", -apple-system, "Segoe UI", Arial, sans-serif;
        }}
        [data-testid="stSidebarNav"] {{
            padding-top: 0.5rem;
        }}
        [data-testid="stSidebarNav"] a {{
            border-radius: {RADIUS_SM};
            margin: 2px 6px;
        }}
        [data-testid="stSidebarNav"] a:hover {{
            background-color: {SURFACE_COLOR};
        }}

        /* Full-size logo while the sidebar is open (st.logo()'s own "large"
        option only renders ~32px tall; this is the actual prominent mark).
        stSidebarHeader's own height is a fixed 60px sized for that small
        default, so it needs to grow too or the logo clips against the top
        of the viewport. */
        [data-testid="stSidebarLogo"] {{
            height: 96px;
            width: auto;
            max-width: 220px;
            /* Nav links sit 14px further right than the header's own left
            edge (their own margin/padding stack: 6px link margin + 8px
            internal padding) — nudge the logo the same 14px so its left
            edge lines up with the nav icons' left edge instead of the
            header box's raw edge. */
            margin-left: 14px;
        }}
        [data-testid="stSidebarHeader"] {{
            min-height: 116px;
            padding: 10px 0;
        }}

        /* Persistent icon rail: Streamlit's native sidebar collapse hides the
        whole nav (animates to width 0, translateX off-screen). Override both
        so collapsing instead leaves a narrow rail with just the nav icons —
        driven by the stable `aria-expanded` attribute, not by Streamlit's
        internal (version-fragile) emotion-hashed class names. */
        [data-testid="stSidebar"][aria-expanded="false"] {{
            min-width: 68px !important;
            width: 68px !important;
            transform: none !important;
            visibility: visible !important;
        }}
        /* stSidebarHeader packs the logo *and* the collapse arrow into one
        `justify-content: space-between` flex row sized off the same broken
        calc() as the nav (see below) — fighting that row's own layout to
        center just the logo inside it was unreliable. Instead, take the
        logo out of that flow entirely and center it against the sidebar's
        own (reliable, explicitly-set) 68px width. */
        [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarHeader"] {{
            position: relative;
            min-height: 60px;
        }}
        [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarLogo"] {{
            position: absolute;
            top: 14px;
            left: 50%;
            transform: translateX(-50%);
            height: 32px;
            max-width: 40px;
            margin-left: 0;
        }}
        [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarCollapseButton"] {{
            position: absolute;
            top: 4px;
            right: 4px;
        }}
        /* stSidebarNav sizes itself as calc(100% - 60px), a fixed pixel
        padding meant for the original 300px-wide sidebar; at 68px that
        resolves to ~8px instead of the rail's real width, which is why the
        nav icons were landing squeezed against the left edge. */
        [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarNav"] {{
            width: 100% !important;
            padding-left: 0 !important;
            padding-right: 0 !important;
        }}
        [data-testid="stSidebar"][aria-expanded="false"] span[label] {{
            display: none;
        }}
        [data-testid="stSidebar"][aria-expanded="false"] li,
        [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarNavLinkContainer"] {{
            width: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
        }}
        [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarNavLink"] {{
            width: 100% !important;
            min-width: 44px;
            /* The link's own left edge still inherits its position from an
            ancestor whose width resolves incorrectly at this rail width
            (a Streamlit-internal calc(), not one of our rules) even though
            the link's own width is reliable. Empirically-measured shift so
            the icon's center lands on the rail's true center, matching the
            logo above (see the absolutely-positioned stSidebarLogo rule). */
            margin-left: -18px !important;
            margin-right: 0 !important;
            justify-content: center;
            padding-left: 0;
            padding-right: 0;
        }}
        /* Streamlit's own fallback badge for a fully-collapsed sidebar is
        redundant once the rail above keeps its own small logo visible. */
        [data-testid="stHeaderLogo"] {{
            display: none;
        }}
        [data-testid="stMetric"] {{
            background-color: {SURFACE_COLOR};
            border: 1px solid rgba(148, 180, 59, 0.35);
            border-radius: {RADIUS_MD};
            padding: 0.9rem 1rem 0.6rem;
        }}
        [data-testid="stMetricLabel"] {{
            font-weight: 600;
        }}
        h1 {{
            color: {PRIMARY_COLOR_DARK};
            font-weight: 600;
        }}
        div.stButton > button[kind="primary"] {{
            background-color: {PRIMARY_COLOR};
            color: {TEXT_COLOR};
            border-radius: {RADIUS_SM};
        }}
        div.stButton > button[kind="primary"]:hover {{
            background-color: {PRIMARY_COLOR_DARK};
            color: {TEXT_COLOR};
        }}
        div[data-testid="stExpander"] {{
            border: 1px solid {SURFACE_COLOR};
            border-radius: {RADIUS_MD};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_branding() -> None:
    """Injects the UNAL logo above the sidebar nav and the app-wide visual theme.

    Call once in app.py, before `st.navigation(...)`. `st.logo()` (unlike a
    manual `st.image()` inside `st.sidebar`) is docked above Streamlit's
    auto-generated nav rather than after it, and keeps a small badge visible
    when the user collapses the sidebar.
    """
    _inject_css()
    st.logo(str(LOGO_PATH), size="large", icon_image=str(LOGO_PATH))


def state_badge(state: str) -> str:
    """Small inline colored pill for a DiagnosticState value, for use in st.markdown.

    Text is always dark (TEXT_COLOR), never white: white-on-state-color fails
    WCAG AA contrast for every state in STATE_COLORS (see the comment above
    that dict), while dark text clears 4.5:1 in all five cases.
    """
    color = STATE_COLORS.get(state, "#95a5a6")
    return (
        f'<span style="background-color:{color};color:{TEXT_COLOR};padding:2px 10px;'
        f'border-radius:{RADIUS_SM};font-size:0.85rem;font-weight:600;">{state}</span>'
    )
