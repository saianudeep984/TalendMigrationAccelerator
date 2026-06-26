import html
from typing import Iterable, Optional

import streamlit as st


def apply_enterprise_theme() -> None:
    """Microsoft Fabric / Databricks-inspired enterprise theme."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        :root {
            --f-bg: #f3f4f6;
            --f-surface: #ffffff;
            --f-surface-2: #f9fafb;
            --f-border: #e5e7eb;
            --f-border-strong: #d1d5db;
            --f-text: #111827;
            --f-text-2: #374151;
            --f-muted: #6b7280;
            --f-muted-light: #9ca3af;
            --f-blue: #0f6cbd;
            --f-blue-dark: #0d5aa7;
            --f-blue-light: #eff6ff;
            --f-teal: #0e7c69;
            --f-green: #107c10;
            --f-green-bg: #f0fdf4;
            --f-amber: #9d5d00;
            --f-amber-bg: #fffbeb;
            --f-red: #bc2f32;
            --f-red-bg: #fff1f2;
            --f-purple: #6b21a8;
            --f-shadow-sm: 0 1px 2px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.04);
            --f-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 4px 12px rgba(0,0,0,0.06);
            --f-radius: 8px;
            --f-radius-lg: 12px;
        }

        /* ---- Base ---- */
        html, body, [class*="css"], .stApp {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
            background-color: var(--f-bg) !important;
            color: var(--f-text) !important;
        }
        .block-container {
            padding: 1.5rem 2rem 4rem !important;
            max-width: 1360px !important;
        }

        /* ---- Headings ---- */
        h1 { font-size: 20px !important; font-weight: 700 !important; color: var(--f-text) !important; margin: 0 0 4px !important; }
        h2 { font-size: 16px !important; font-weight: 600 !important; color: var(--f-text) !important; margin: 0 !important; }
        h3 { font-size: 13px !important; font-weight: 600 !important; color: var(--f-text) !important; }

        /* ---- Sidebar ---- */
        section[data-testid="stSidebar"] {
            background: var(--f-surface) !important;
            border-right: 1px solid var(--f-border) !important;
        }
        section[data-testid="stSidebar"] > div { padding-top: 0 !important; }

        /* ---- Streamlit native metrics ---- */
        div[data-testid="stMetric"] {
            background: var(--f-surface) !important;
            border: 1px solid var(--f-border) !important;
            border-radius: var(--f-radius) !important;
            padding: 14px 16px !important;
            box-shadow: var(--f-shadow-sm) !important;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 11px !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.06em !important;
            color: var(--f-muted) !important;
        }
        div[data-testid="stMetricValue"] {
            font-size: 22px !important;
            font-weight: 700 !important;
            color: var(--f-text) !important;
        }

        /* ---- Tabs ---- */
        .stTabs [data-baseweb="tab-list"] {
            border-bottom: 1px solid var(--f-border) !important;
            background: transparent !important;
            gap: 0 !important;
        }
        .stTabs [data-baseweb="tab"] {
            font-size: 13px !important;
            font-weight: 500 !important;
            color: var(--f-muted) !important;
            padding: 10px 18px !important;
            border-bottom: 2px solid transparent !important;
            background: transparent !important;
        }
        .stTabs [aria-selected="true"] {
            color: var(--f-blue) !important;
            border-bottom-color: var(--f-blue) !important;
            font-weight: 600 !important;
        }
        .stTabs [data-baseweb="tab-panel"] {
            padding-top: 16px !important;
        }

        /* ---- Buttons ---- */
        .stButton > button {
            font-size: 13px !important;
            font-weight: 500 !important;
            border-radius: 6px !important;
            padding: 7px 16px !important;
            border: 1px solid var(--f-border-strong) !important;
            background: var(--f-surface) !important;
            color: var(--f-text-2) !important;
            box-shadow: var(--f-shadow-sm) !important;
            transition: all 0.15s !important;
        }
        .stButton > button:hover {
            background: var(--f-blue-light) !important;
            border-color: var(--f-blue) !important;
            color: var(--f-blue) !important;
        }
        .stDownloadButton > button {
            font-size: 13px !important;
            font-weight: 600 !important;
            border-radius: 6px !important;
            background: var(--f-blue) !important;
            color: #fff !important;
            border: none !important;
            padding: 8px 18px !important;
            box-shadow: var(--f-shadow-sm) !important;
        }
        .stDownloadButton > button:hover { background: var(--f-blue-dark) !important; }

        /* ---- File uploader ---- */
        [data-testid="stFileUploader"] {
            border: 2px dashed var(--f-border-strong) !important;
            border-radius: var(--f-radius-lg) !important;
            padding: 24px !important;
            background: var(--f-surface-2) !important;
            transition: border-color 0.2s !important;
        }
        [data-testid="stFileUploader"]:hover {
            border-color: var(--f-blue) !important;
        }

        /* ---- Inputs / Selects ---- */
        .stSelectbox > div > div,
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea,
        .stNumberInput > div > div > input {
            border-radius: 6px !important;
            border-color: var(--f-border-strong) !important;
            font-size: 13px !important;
            font-family: 'Inter', sans-serif !important;
            background: var(--f-surface) !important;
        }

        /* ---- Expanders ---- */
        .streamlit-expanderHeader {
            font-size: 13px !important;
            font-weight: 600 !important;
            color: var(--f-text-2) !important;
            background: var(--f-surface) !important;
            border-radius: 6px !important;
            border: 1px solid var(--f-border) !important;
            padding: 10px 14px !important;
        }
        .streamlit-expanderContent {
            border: 1px solid var(--f-border) !important;
            border-top: none !important;
            border-radius: 0 0 6px 6px !important;
            background: var(--f-surface) !important;
        }

        /* ---- Progress bar ---- */
        .stProgress > div > div {
            background: var(--f-blue) !important;
            border-radius: 4px !important;
        }
        .stProgress > div { border-radius: 4px !important; background: var(--f-border) !important; }

        /* ---- Alerts ---- */
        .stAlert { border-radius: var(--f-radius) !important; font-size: 13px !important; }

        /* ---- Dataframe ---- */
        .dataframe { font-size: 12px !important; }

        /* ---- Scrollbar ---- */
        ::-webkit-scrollbar { width: 5px; height: 5px; }
        ::-webkit-scrollbar-track { background: var(--f-bg); }
        ::-webkit-scrollbar-thumb { background: var(--f-border-strong); border-radius: 3px; }

        /* ======================================================
           CUSTOM COMPONENTS
        ====================================================== */

        /* Topbar / app header */
        .f-topbar {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 0 0 14px;
            border-bottom: 1px solid var(--f-border);
            margin-bottom: 16px;
        }
        .f-topbar-logo { height: 30px; width: auto; border-radius: 4px; }
        .f-topbar-name { font-size: 15px; font-weight: 700; color: var(--f-text); line-height: 1.2; }
        .f-topbar-sub  { font-size: 11px; color: var(--f-muted); font-weight: 500; }

        /* Sidebar nav label */
        .f-nav-label {
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--f-muted-light);
            padding: 16px 14px 4px;
            display: block;
        }

        /* Status dot in sidebar */
        .f-status-dot {
            display: inline-block;
            width: 6px; height: 6px;
            border-radius: 50%;
            margin-right: 6px;
            vertical-align: middle;
        }
        .f-status-ready { background: var(--f-green); }
        .f-status-warn  { background: var(--f-amber); }
        .f-status-idle  { background: var(--f-muted-light); }

        /* Page hero */
        .f-hero {
            background: linear-gradient(118deg, #0f172a 0%, #1e3a5f 60%, #0f4c75 100%);
            border-radius: var(--f-radius-lg);
            padding: 22px 26px;
            color: #fff;
            margin-bottom: 20px;
        }
        .f-hero-title { font-size: 19px; font-weight: 700; margin: 0 0 3px; letter-spacing: -0.01em; }
        .f-hero-sub   { font-size: 12px; color: rgba(255,255,255,0.7); margin: 0 0 12px; line-height: 1.5; }
        .f-pill-row   { display: flex; flex-wrap: wrap; gap: 6px; }
        .f-pill {
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.18);
            border-radius: 999px;
            padding: 3px 10px;
            font-size: 11px;
            font-weight: 600;
            color: rgba(255,255,255,0.88);
        }

        /* Section divider */
        .f-section {
            display: flex;
            align-items: baseline;
            gap: 10px;
            margin: 20px 0 10px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--f-border);
        }
        .f-section-title { font-size: 13px; font-weight: 600; color: var(--f-text); }
        .f-section-sub   { font-size: 12px; color: var(--f-muted); }

        /* KPI scorecard */
        .f-kpi {
            background: var(--f-surface);
            border: 1px solid var(--f-border);
            border-radius: var(--f-radius);
            padding: 14px 16px;
            box-shadow: var(--f-shadow-sm);
            min-height: 86px;
        }
        .f-kpi-label   { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--f-muted); margin-bottom: 5px; }
        .f-kpi-value   { font-size: 22px; font-weight: 700; color: var(--f-text); line-height: 1.1; margin-bottom: 3px; }
        .f-kpi-caption { font-size: 11px; color: var(--f-muted-light); line-height: 1.4; }
        .f-kpi-bar     { height: 2px; border-radius: 999px; margin-top: 9px; }

        /* Insight / narrative card */
        .f-insight {
            background: var(--f-surface);
            border: 1px solid var(--f-border);
            border-left: 3px solid var(--f-blue);
            border-radius: var(--f-radius);
            padding: 14px 16px;
            box-shadow: var(--f-shadow-sm);
        }
        .f-insight-title { font-size: 13px; font-weight: 600; color: var(--f-text); margin-bottom: 5px; }
        .f-insight-body  { font-size: 12px; color: var(--f-muted); line-height: 1.5; }

        /* Action panel (report cards) */
        .f-action {
            background: var(--f-surface);
            border: 1px solid var(--f-border);
            border-left: 3px solid var(--f-blue);
            border-radius: var(--f-radius);
            padding: 12px 14px;
            box-shadow: var(--f-shadow-sm);
            height: 100%;
        }
        .f-action-title  { font-size: 13px; font-weight: 600; color: var(--f-text); margin-bottom: 4px; }
        .f-action-body   { font-size: 12px; color: var(--f-muted); line-height: 1.4; margin-bottom: 6px; }
        .f-action-status { font-size: 11px; font-weight: 600; }

        /* Roadmap steps */
        .f-roadmap { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin: 8px 0 16px; }
        .f-step {
            background: var(--f-surface);
            border: 1px solid var(--f-border);
            border-radius: var(--f-radius);
            padding: 12px 14px;
            box-shadow: var(--f-shadow-sm);
        }
        .f-step-num   { font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--f-blue); margin-bottom: 4px; }
        .f-step-title { font-size: 13px; font-weight: 600; color: var(--f-text); margin-bottom: 3px; }
        .f-step-desc  { font-size: 11px; color: var(--f-muted); line-height: 1.4; }

        /* Upload box hint */
        .f-upload-hint {
            background: var(--f-blue-light);
            border: 1px solid #bfdbfe;
            border-radius: var(--f-radius);
            padding: 12px 16px;
            font-size: 12px;
            color: #1e40af;
            margin-bottom: 12px;
            line-height: 1.5;
        }

        /* Success callout after analysis */
        .f-callout {
            background: var(--f-green-bg);
            border: 1px solid #bbf7d0;
            border-left: 4px solid var(--f-green);
            border-radius: var(--f-radius);
            padding: 14px 18px;
            margin: 12px 0;
        }
        .f-callout-title { font-size: 13px; font-weight: 700; color: #14532d; margin-bottom: 4px; }
        .f-callout-body  { font-size: 12px; color: #166534; line-height: 1.5; }

        /* Download card */
        .f-dl-card {
            background: var(--f-surface);
            border: 1px solid var(--f-border);
            border-radius: var(--f-radius);
            padding: 14px 16px;
            box-shadow: var(--f-shadow-sm);
            text-align: center;
        }
        .f-dl-icon  { font-size: 22px; margin-bottom: 6px; }
        .f-dl-title { font-size: 13px; font-weight: 600; color: var(--f-text); margin-bottom: 3px; }
        .f-dl-desc  { font-size: 11px; color: var(--f-muted); margin-bottom: 10px; }

        /* Inline breadcrumb */
        .f-breadcrumb { font-size: 12px; color: var(--f-muted); margin-bottom: 10px; }
        .f-breadcrumb-sep { margin: 0 6px; color: var(--f-muted-light); }
        .f-breadcrumb-current { font-weight: 600; color: var(--f-text); }

        /* Config panel */
        .f-config-row {
            display: flex;
            align-items: center;
            gap: 16px;
            background: var(--f-surface);
            border: 1px solid var(--f-border);
            border-radius: var(--f-radius);
            padding: 10px 16px;
            margin-bottom: 8px;
        }
        .f-config-label { font-size: 12px; font-weight: 600; color: var(--f-text-2); min-width: 140px; }
        .f-config-hint  { font-size: 11px; color: var(--f-muted); }

        @media (max-width: 900px) {
            .f-roadmap { grid-template-columns: repeat(2, 1fr); }
            .f-hero-title { font-size: 17px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---- Component helpers ----------------------------------------

def hero(title: str, subtitle: str, pills: Optional[Iterable[str]] = None) -> None:
    pill_html = ""
    if pills:
        pill_html = '<div class="f-pill-row">' + "".join(
            f'<span class="f-pill">{html.escape(str(p))}</span>' for p in pills
        ) + "</div>"
    st.markdown(
        f'<div class="f-hero">'
        f'<div class="f-hero-title">{html.escape(title)}</div>'
        f'<div class="f-hero-sub">{html.escape(subtitle)}</div>'
        f'{pill_html}</div>',
        unsafe_allow_html=True,
    )


def section(title: str, subtitle: str = "") -> None:
    sub = f'<span class="f-section-sub">{html.escape(subtitle)}</span>' if subtitle else ""
    st.markdown(
        f'<div class="f-section"><span class="f-section-title">{html.escape(title)}</span>{sub}</div>',
        unsafe_allow_html=True,
    )


_ACCENT_COLORS = {
    "blue":   "#0f6cbd",
    "teal":   "#0e7c69",
    "green":  "#107c10",
    "amber":  "#9d5d00",
    "red":    "#bc2f32",
    "purple": "#6b21a8",
}


def metric_card(label: str, value: str, caption: str = "", accent: str = "blue") -> None:
    color = _ACCENT_COLORS.get(accent, _ACCENT_COLORS["blue"])
    st.markdown(
        f'<div class="f-kpi">'
        f'<div class="f-kpi-label">{html.escape(label)}</div>'
        f'<div class="f-kpi-value">{html.escape(str(value))}</div>'
        f'<div class="f-kpi-caption">{html.escape(caption)}</div>'
        f'<div class="f-kpi-bar" style="background:{color};opacity:.65;"></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def insight(title: str, body: str, accent: str = "#0f6cbd") -> None:
    st.markdown(
        f'<div class="f-insight" style="border-left-color:{accent};">'
        f'<div class="f-insight-title">{html.escape(title)}</div>'
        f'<div class="f-insight-body">{html.escape(body)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def action_panel(title: str, body: str, status: str = "Ready", accent: str = "#0f6cbd") -> None:
    status_color = "#107c10" if status.lower() in ("ready", "available") \
        else "#9d5d00" if status.lower() in ("planned", "pending") \
        else "#6b7280"
    st.markdown(
        f'<div class="f-action" style="border-left-color:{accent};">'
        f'<div class="f-action-title">{html.escape(title)}</div>'
        f'<div class="f-action-body">{html.escape(body)}</div>'
        f'<div class="f-action-status" style="color:{status_color};">{html.escape(status)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def roadmap(steps: Iterable[tuple[str, str]]) -> None:
    step_html = "".join(
        f'<div class="f-step">'
        f'<div class="f-step-num">Step {i + 1}</div>'
        f'<div class="f-step-title">{html.escape(t)}</div>'
        f'<div class="f-step-desc">{html.escape(d)}</div>'
        f'</div>'
        for i, (t, d) in enumerate(steps)
    )
    st.markdown(f'<div class="f-roadmap">{step_html}</div>', unsafe_allow_html=True)


def upload_hint(text: str) -> None:
    st.markdown(f'<div class="f-upload-hint">{html.escape(text)}</div>', unsafe_allow_html=True)


def success_callout(title: str, body: str) -> None:
    st.markdown(
        f'<div class="f-callout">'
        f'<div class="f-callout-title">✅ {html.escape(title)}</div>'
        f'<div class="f-callout-body">{html.escape(body)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def download_card(icon: str, title: str, desc: str) -> None:
    st.markdown(
        f'<div class="f-dl-card">'
        f'<div class="f-dl-icon">{icon}</div>'
        f'<div class="f-dl-title">{html.escape(title)}</div>'
        f'<div class="f-dl-desc">{html.escape(desc)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def breadcrumb(parts: list[str], current: str) -> None:
    sep = '<span class="f-breadcrumb-sep">›</span>'
    inner = sep.join(f'<span>{html.escape(p)}</span>' for p in parts)
    inner += sep + f'<span class="f-breadcrumb-current">{html.escape(current)}</span>'
    st.markdown(f'<div class="f-breadcrumb">{inner}</div>', unsafe_allow_html=True)
