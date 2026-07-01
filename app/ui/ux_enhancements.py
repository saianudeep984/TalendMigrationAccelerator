"""
TMA UX Enhancements — Commercial Polish Layer
Implements: Home landing, error cards, nav grouping, session restore,
settings toast, AI chips, terminology standardization, cleanup.
All business logic untouched. Drop-in import.
"""
import html as _html
import json
import os
import time

import streamlit as st

from app.ui.design_system_v2 import _load_logo_data_uri

# ── Recent projects (persisted history for the landing page) ──────────────────
_RECENT_PROJECTS_FILE = os.path.join("cache", "recent_projects.json")
_MAX_RECENT_PROJECTS = 5


def record_recent_project(
    name: str, job_count: int, readiness: str = "",
    source_version: str = "", target_version: str = "",
) -> None:
    """Append a just-completed analysis to the recent-projects history.

    Best-effort and non-fatal: any I/O problem is silently ignored so this
    never interrupts the analysis flow.
    """
    try:
        entries = get_recent_projects(limit=_MAX_RECENT_PROJECTS)
        entries = [e for e in entries if e.get("name") != name]
        entries.insert(0, {
            "name": name or "Untitled repository",
            "jobs": int(job_count or 0),
            "readiness": readiness or "—",
            "source_version": source_version or "",
            "target_version": target_version or "",
            "analyzed_at": time.time(),
        })
        entries = entries[:_MAX_RECENT_PROJECTS]
        os.makedirs(os.path.dirname(_RECENT_PROJECTS_FILE), exist_ok=True)
        with open(_RECENT_PROJECTS_FILE, "w") as f:
            json.dump(entries, f, indent=2)
    except Exception:
        pass


def get_recent_projects(limit: int = 5) -> list:
    """Return the most recent analyzed-repository entries, newest first."""
    try:
        with open(_RECENT_PROJECTS_FILE, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data[:limit]
    except Exception:
        pass
    return []


def _relative_time(epoch_seconds) -> str:
    try:
        delta = max(0, time.time() - float(epoch_seconds))
    except (TypeError, ValueError):
        return ""
    if delta < 3600:
        return f"{max(1, int(delta // 60))}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


# ── 1. HOME LANDING PAGE ───────────────────────────────────────────────────────

def render_home_landing(on_get_started) -> None:
    """
    Professional landing state for first-time and returning sessions.
    on_get_started: callable — called when the CTA button is clicked.
    """
    has_repo = "last_analysis_jobs" in st.session_state
    has_prev  = bool(st.session_state.get("last_repo_path"))
    job_count = len(st.session_state.get("last_analysis_jobs", []))
    repo_name = st.session_state.get("wizard_uploaded_file_name", "")
    if repo_name:
        repo_name = repo_name.replace(".zip", "")

    # Responsive tweaks for the hero/cards below ~640px (phones) — native
    # st.columns already stack on narrow viewports; this just keeps type
    # and spacing comfortable at small sizes without touching nav/upload CSS.
    st.markdown(
        """
        <style>
        @media (max-width: 640px) {
            .tma-landing-hero { padding: 24px 20px 22px !important; }
            .tma-landing-title { font-size: 22px !important; }
            .tma-landing-tagline { font-size: 13px !important; max-width: 100% !important; }
            .tma-landing-brandrow { gap: 10px !important; }
            .tma-landing-logo { height: 40px !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Returning session banner ──────────────────────────────────────────────
    if has_prev and not has_repo:
        st.markdown(
            f"""
            <div style="background:#eff6ff;border:1px solid #bfdbfe;border-left:4px solid #2563eb;
            border-radius:10px;padding:14px 18px;margin-bottom:16px;display:flex;
            align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;">
              <div>
                <div style="font-size:13px;font-weight:700;color:#1d4ed8;">
                  🔄 Resume Previous Session
                </div>
                <div style="font-size:12px;color:#475569;margin-top:2px;">
                  Repository: <strong>{_html.escape(repo_name or "last session")}</strong>
                  &nbsp;·&nbsp; Re-upload your ZIP to restore full analysis.
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif has_repo:
        # Derive session banner status from health score (single source of truth).
        # overall_status is GREEN / AMBER / RED; fall back to readiness_score["overall"]
        # only if health score is not yet computed.
        try:
            from app.analyzers.health_score import get_health_score
            _home_hs = get_health_score()
        except Exception:
            _home_hs = {}
        overall_status = (
            _home_hs.get("overall_status")
            or st.session_state.get("readiness_score", {}).get("overall", "—")
        )
        _STATUS_COLOR = {"GREEN": "#15803d", "AMBER": "#b45309", "RED": "#be123c"}
        _STATUS_ICON  = {"GREEN": "🟢", "AMBER": "🟡", "RED": "🔴"}
        _STATUS_LBL   = {"GREEN": "Green", "AMBER": "Amber", "RED": "Red"}
        ov_color = _STATUS_COLOR.get(overall_status, "#64748b")
        ov_icon  = _STATUS_ICON.get(overall_status, "⚪")
        ov_lbl   = _STATUS_LBL.get(overall_status, overall_status)
        st.markdown(
            f"""
            <div style="background:#f0fdf4;border:1px solid #86efac;border-left:4px solid #15803d;
            border-radius:10px;padding:14px 18px;margin-bottom:16px;display:flex;
            align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;">
              <div>
                <div style="font-size:13px;font-weight:700;color:#15803d;">
                  ✅ Active Session — {_html.escape(repo_name or "Repository")}
                </div>
                <div style="font-size:12px;color:#475569;margin-top:2px;">
                  <strong>{job_count}</strong> jobs loaded &nbsp;·&nbsp;
                  Overall Status: <strong style="color:{ov_color};">{ov_icon} {ov_lbl}</strong>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Health Score (only when a repo is loaded — uses shared engine) ─────────
    if has_repo:
        try:
            from app.analyzers.health_score import get_health_score, render_health_score_widget
            _hs_result = get_health_score()
            if _hs_result:
                render_health_score_widget(_hs_result)
        except Exception:
            pass

    # ── Hero section (logo · product name · short tagline · capabilities) ────
    _logo_uri = _load_logo_data_uri()
    _logo_html = (
        f'<img class="tma-landing-logo" src="{_logo_uri}" alt="Artha logo" '
        f'style="height:52px;width:auto;background:#fff;border-radius:10px;'
        f'padding:6px;flex-shrink:0;"/>'
        if _logo_uri else ""
    )
    st.markdown(
        f"""
        <div class="tma-landing-hero" style="background:linear-gradient(118deg,var(--tma-text,#0f172a) 0%,
        #1e3a5f 60%,var(--tma-primary-dark,#1d4ed8) 100%);
        border-radius:var(--tma-radius,16px);padding:32px 32px 28px;color:#fff;margin-bottom:20px;">
          <div class="tma-landing-brandrow" style="display:flex;align-items:center;gap:14px;margin-bottom:14px;flex-wrap:wrap;">
            {_logo_html}
            <div>
              <div style="font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
              color:rgba(255,255,255,.6);margin-bottom:4px;">Artha Solutions · Enterprise ETL Intelligence</div>
              <div class="tma-landing-title" style="font-size:28px;font-weight:900;line-height:1.2;">
                Talend Migration Accelerator
              </div>
            </div>
          </div>
          <div class="tma-landing-tagline" style="font-size:14px;color:rgba(255,255,255,.85);line-height:1.6;max-width:560px;margin-bottom:20px;">
            Analyze, assess, and migrate Talend repositories with AI-powered intelligence.
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:8px;">
            <span style="background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);
            border-radius:999px;padding:4px 12px;font-size:12px;font-weight:600;">
              🔍 Job 360 Analysis
            </span>
            <span style="background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);
            border-radius:999px;padding:4px 12px;font-size:12px;font-weight:600;">
              📊 Executive RAG Dashboard
            </span>
            <span style="background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);
            border-radius:999px;padding:4px 12px;font-size:12px;font-weight:600;">
              🤖 AI Recommendations
            </span>
            <span style="background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);
            border-radius:999px;padding:4px 12px;font-size:12px;font-weight:600;">
              🗺️ Migration Playbook
            </span>
            <span style="background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);
            border-radius:999px;padding:4px 12px;font-size:12px;font-weight:600;">
              ⚡ Auto-Fix Engine
            </span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Feature summary ───────────────────────────────────────────────────────
    features = [
        ("🔍", "Analyse",    "Scan jobs, detect complexity, map dependencies and unsupported components."),
        ("📋", "Plan",       "RAG readiness scoring, effort estimation, wave planning and migration playbook."),
        ("🤖", "AI Insights","AI-generated recommendations, auto-fix patterns and documentation."),
        ("📤", "Export",     "Excel reports, branded PDF, JSON lineage and Migration Runbook."),
    ]
    cols = st.columns(len(features))
    for col, (icon, title, desc) in zip(cols, features):
        with col:
            st.markdown(
                f"""
                <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;
                padding:16px 14px;height:100%;text-align:center;">
                  <div style="font-size:26px;margin-bottom:6px;">{icon}</div>
                  <div style="font-size:13px;font-weight:700;color:#0f172a;margin-bottom:4px;">
                    {title}
                  </div>
                  <div style="font-size:11px;color:#64748b;line-height:1.5;">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Recent projects (only rendered when history is available) ────────────
    _recent = get_recent_projects(limit=3)
    if _recent:
        st.markdown(
            '<div style="font-size:11px;font-weight:700;color:var(--tma-text-muted,#64748b);'
            'text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;">Recent Projects</div>',
            unsafe_allow_html=True,
        )
        _rag_color = {"GREEN": "#15803d", "AMBER": "#b45309", "RED": "#be123c"}
        _rag_icon  = {"GREEN": "🟢", "AMBER": "🟡", "RED": "🔴"}
        _rp_cols = st.columns(len(_recent))
        for _col, _proj in zip(_rp_cols, _recent):
            _readiness = _proj.get("readiness", "—")
            _color = _rag_color.get(_readiness, "#64748b")
            _icon  = _rag_icon.get(_readiness, "⚪")
            _ver   = _proj.get("target_version", "")
            with _col:
                st.markdown(
                    f"""
                    <div style="background:var(--tma-surface,#fff);border:1px solid var(--tma-border,#e2e8f0);
                    border-radius:12px;padding:12px 14px;height:100%;">
                      <div style="font-size:13px;font-weight:700;color:var(--tma-text,#0f172a);
                      white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                        {_html.escape(str(_proj.get("name", "Untitled")))}
                      </div>
                      <div style="font-size:11px;color:var(--tma-text-muted,#64748b);margin-top:4px;">
                        {_proj.get("jobs", 0)} jobs{f" · → {_html.escape(_ver)}" if _ver else ""}
                      </div>
                      <div style="font-size:11px;margin-top:4px;color:{_color};font-weight:700;">
                        {_icon} {_html.escape(str(_readiness))}
                      </div>
                      <div style="font-size:10px;color:#94a3b8;margin-top:4px;">
                        {_relative_time(_proj.get("analyzed_at"))}
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)


    # ── CTA: "Get Started" button → directly navigates to upload step ────────
    # Uses Streamlit's on_click= callback (not "if st.button(): handler()")
    # so the session-state mutation that flips the home→upload gate is
    # guaranteed to run BEFORE this script rerun starts, instead of being
    # applied mid-script on the same pass the gate condition is read. The
    # inline-call pattern previously used here required two clicks on a
    # fresh app start: the first click's handler ran, but the surrounding
    # column/container nesting meant the rerun it triggered re-evaluated
    # the gate condition before Streamlit had fully committed the click's
    # own widget state, so the Home page rendered again; the second click
    # then worked because the state from click 1 was already committed.
    cta_label = "🔄 Get Started — Upload New Repository" if has_repo else "🚀 Get Started — Upload Repository"
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.button(
            cta_label,
            type="primary",
            use_container_width=True,
            key="home_cta_get_started",
            on_click=on_get_started,
        )



# ── 2. ERROR CARDS ─────────────────────────────────────────────────────────────

def render_error_card(
    title: str,
    message: str,
    detail: str = "",
    show_retry: bool = True,
    show_reload: bool = True,
    retry_key: str = "err_retry",
    help_url: str = "",
) -> bool:
    """
    Friendly error card. Returns True when Retry is clicked.
    Never exposes Python tracebacks.
    """
    safe_title   = _html.escape(str(title))
    safe_message = _html.escape(str(message))
    safe_detail  = _html.escape(str(detail)) if detail else ""

    detail_html = (
        f'<div style="font-size:11px;color:#94a3b8;margin-top:6px;font-family:monospace;'
        f'background:#fff1f2;padding:8px;border-radius:6px;word-break:break-all;">'
        f'{safe_detail}</div>'
    ) if safe_detail else ""

    st.markdown(
        f"""
        <div style="background:#fff1f2;border:1px solid #fda4af;border-left:4px solid #be123c;
        border-radius:10px;padding:18px 20px;margin:8px 0;">
          <div style="font-size:15px;font-weight:800;color:#be123c;margin-bottom:4px;">
            ⚠️ {safe_title}
          </div>
          <div style="font-size:13px;color:#475569;line-height:1.6;">{safe_message}</div>
          {detail_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    actions = []
    if show_retry:
        actions.append(("retry", "🔄 Retry"))
    if show_reload:
        actions.append(("reload", "↺ Reload Page"))
    if help_url:
        actions.append(("help", "❓ Help"))

    if not actions:
        return False

    cols = st.columns(len(actions) + 2)
    clicked_retry = False
    for col, (action_id, label) in zip(cols, actions):
        with col:
            if action_id == "retry":
                if st.button(label, key=retry_key, use_container_width=True):
                    clicked_retry = True
            elif action_id == "reload":
                if st.button(label, key=f"{retry_key}_reload", use_container_width=True):
                    st.rerun()
            elif action_id == "help" and help_url:
                st.link_button(label, help_url, use_container_width=True)
    return clicked_retry


def render_warning_card(title: str, message: str, detail: str = "") -> None:
    """Friendly amber warning card without traceback exposure."""
    safe_title   = _html.escape(str(title))
    safe_message = _html.escape(str(message))
    detail_html = (
        f'<div style="font-size:11px;color:#78716c;margin-top:4px;">'
        f'{_html.escape(str(detail))}</div>'
    ) if detail else ""
    st.markdown(
        f"""
        <div style="background:#fffbeb;border:1px solid #fcd34d;border-left:4px solid #b45309;
        border-radius:10px;padding:14px 18px;margin:6px 0;">
          <div style="font-size:13px;font-weight:700;color:#b45309;margin-bottom:3px;">
            ⚠️ {safe_title}
          </div>
          <div style="font-size:12px;color:#475569;line-height:1.5;">{safe_message}</div>
          {detail_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_no_repo_card(page_name: str = "") -> None:
    """Standard 'no repository loaded' empty state."""
    where = f" on {page_name}" if page_name else ""
    render_warning_card(
        "No Repository Loaded",
        f"Upload a Talend ZIP and run analysis to use this feature{where}. "
        "Use the ↑ Home tab to get started.",
    )


# ── 3. NAVIGATION GROUP LABELS ─────────────────────────────────────────────────

NAV_GROUPS = {
    "home":                 ("Home",    "🏠"),
    "command_center":       ("Analyse", "🔬"),
    "executive_dashboard":  ("Analyse", "🔬"),
    "portfolio":            ("Analyse", "🔬"),
    "job_analysis":         ("Explore", "🔭"),
    "repository_search":    ("Explore", "🔭"),
    "testing_architecture": ("Plan",    "📋"),
    "version_converter":    ("Plan",    "📋"),
    "settings":             ("Settings","⚙️"),
}

JOB360_ICON = "🔭"  # unique icon for Job 360


# ── 4. TERMINOLOGY STANDARDISATION ─────────────────────────────────────────────

def readiness_label(status: str) -> str:
    """Convert any RAG/status string to standardised 'Readiness Status (Color)' label."""
    s = str(status or "").upper().strip()
    mapping = {
        "GREEN":  "Readiness Status (Green)",
        "AMBER":  "Readiness Status (Amber)",
        "RED":    "Readiness Status (Red)",
        "READY":  "Readiness Status (Green)",
        "NOT READY": "Readiness Status (Red)",
    }
    return mapping.get(s, f"Readiness Status ({s.capitalize() or 'Unknown'})")


def rag_pill(status: str, compact: bool = False) -> str:
    """Return HTML pill for a RAG status using standardised terminology."""
    s = str(status or "").upper().strip()
    styles = {
        "GREEN": ("#f0fdf4", "#86efac", "#15803d", "🟢", "Green"),
        "AMBER": ("#fffbeb", "#fcd34d", "#b45309", "🟡", "Amber"),
        "RED":   ("#fff1f2", "#fda4af", "#be123c", "🔴", "Red"),
    }
    bg, bd, fg, icon, label = styles.get(s, ("#f8fafc", "#cbd5e1", "#64748b", "⚪", s.capitalize() or "Unknown"))
    text = label if compact else f"Readiness Status ({label})"
    return (
        f'<span style="display:inline-flex;align-items:center;gap:4px;padding:3px 10px;'
        f'border-radius:999px;background:{bg};border:1px solid {bd};color:{fg};'
        f'font-size:12px;font-weight:700;">{icon} {text}</span>'
    )


# ── 5. AI COPILOT CHIPS ────────────────────────────────────────────────────────

def render_ai_prompt_chips(prompts: list[dict], on_select_key: str = "_ai_chip_prompt") -> str | None:
    """
    Render AI suggestion prompts as compact inline chips instead of full buttons.
    prompts: list of {label, prompt, icon?}
    Returns selected prompt text or None.
    """
    if not prompts:
        return None

    chips_html = ""
    for i, p in enumerate(prompts):
        icon  = p.get("icon", "💡")
        label = _html.escape(str(p.get("label", "")))
        chips_html += (
            f'<span class="tma-chip" data-idx="{i}">'
            f'{icon} {label}</span>'
        )

    st.markdown(
        f"""
        <style>
        .tma-chip-row {{
            display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 12px;
        }}
        .tma-chip {{
            display:inline-flex;align-items:center;gap:4px;
            padding:4px 10px;border-radius:999px;
            background:#eff6ff;border:1px solid #bfdbfe;color:#1d4ed8;
            font-size:11px;font-weight:600;cursor:pointer;
            transition:background .12s,border-color .12s;white-space:nowrap;
        }}
        .tma-chip:hover {{
            background:#dbeafe;border-color:#93c5fd;
        }}
        </style>
        <div class="tma-chip-row">{chips_html}</div>
        """,
        unsafe_allow_html=True,
    )

    # Native Streamlit buttons for actual selection (hidden by CSS overlay is tricky;
    # use a pills widget or plain radio with label_visibility collapsed).
    options   = [f"{p.get('icon','💡')} {p.get('label','')}" for p in prompts]
    selection = st.radio(
        "Quick prompts",
        options=["— Select a suggestion —"] + options,
        key=on_select_key,
        label_visibility="collapsed",
        horizontal=True,
    )
    if selection and selection != "— Select a suggestion —":
        idx = options.index(selection)
        return prompts[idx].get("prompt", "")
    return None


# ── 6. SETTINGS SAVE TOAST / UNSAVED WARNING ──────────────────────────────────

_SETTINGS_SAVED_KEY   = "_settings_last_saved_section"
_SETTINGS_DIRTY_KEY   = "_settings_dirty"


def mark_settings_dirty() -> None:
    st.session_state[_SETTINGS_DIRTY_KEY] = True


def mark_settings_saved(section: str) -> None:
    st.session_state[_SETTINGS_DIRTY_KEY] = False
    st.session_state[_SETTINGS_SAVED_KEY] = section
    st.toast(f"✅ {section} saved successfully", icon="✅")


def render_unsaved_settings_warning() -> None:
    if st.session_state.get(_SETTINGS_DIRTY_KEY):
        st.markdown(
            """
            <div style="background:#fffbeb;border:1px solid #fcd34d;border-left:3px solid #b45309;
            border-radius:8px;padding:8px 14px;font-size:12px;color:#b45309;font-weight:600;
            margin-bottom:8px;">
              ⚠️ You have unsaved changes — click Save to persist.
            </div>
            """,
            unsafe_allow_html=True,
        )


def settings_save_button(section: str, key: str, cfg, save_fn, session_key: str = "assessment_config") -> bool:
    """
    Unified Settings save button that shows toast on success.
    Returns True when saved.
    """
    render_unsaved_settings_warning()
    if st.button(f"💾 Save Changes", type="primary", key=key, use_container_width=False):
        st.session_state[session_key] = cfg
        save_fn(cfg, actor=f"settings_{section.lower().replace(' ','_')}")
        mark_settings_saved(section)
        return True
    return False


# ── 7. SESSION RESTORE ─────────────────────────────────────────────────────────

def try_restore_session(cache_manager) -> bool:
    """
    Attempt to restore last repo/job/page from CacheManager.
    Returns True if something was restored.
    """
    if "last_analysis_jobs" in st.session_state:
        return True  # already active
    try:
        cached = cache_manager.load_latest()
        if cached and cached.get("jobs"):
            st.session_state["last_analysis_jobs"] = cached["jobs"]
            if cached.get("repo_path"):
                st.session_state["last_repo_path"] = cached["repo_path"]
            if cached.get("selected_job"):
                st.session_state["selected_job"] = cached["selected_job"]
            if cached.get("nav_idx") is not None:
                st.session_state["_nav_idx2"] = cached["nav_idx"]
            return True
    except Exception:
        pass
    return False


def render_session_restore_banner(cache_manager) -> bool:
    """
    Show 'Resume Previous Session' banner if cache has data.
    Returns True when user clicks Resume.
    """
    try:
        cached = cache_manager.load_latest()
        if not cached or not cached.get("jobs"):
            return False
    except Exception:
        return False

    job_count = len(cached.get("jobs", []))
    repo_name = cached.get("repo_path", "").split("/")[-1] or "Previous repository"

    st.markdown(
        f"""
        <div style="background:#f0fdf4;border:1px solid #86efac;border-left:4px solid #15803d;
        border-radius:10px;padding:12px 18px;margin-bottom:12px;display:flex;
        align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;">
          <div>
            <div style="font-size:13px;font-weight:700;color:#15803d;">
              🔄 Previous session available
            </div>
            <div style="font-size:12px;color:#475569;margin-top:2px;">
              <strong>{_html.escape(repo_name)}</strong> · {job_count} jobs cached
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Resume Previous Session", key="restore_session_banner", type="primary"):
        restored = try_restore_session(cache_manager)
        if restored:
            st.session_state["_nav_idx2"] = 1  # Command Center
            st.rerun()
        return True
    return False


# ── 8. SECTION HEADER (design-system replacement) ──────────────────────────────

def ds_section_header(title: str, subtitle: str = "", icon: str = "") -> None:
    """Design-system section header — replaces raw st.header/st.subheader calls."""
    icon_html = f'<span style="margin-right:6px;">{icon}</span>' if icon else ""
    sub_html  = (
        f'<div style="font-size:11px;color:#64748b;margin-top:2px;">{_html.escape(subtitle)}</div>'
    ) if subtitle else ""
    st.markdown(
        f"""
        <div style="display:flex;align-items:baseline;gap:8px;margin:16px 0 8px;
        padding-bottom:6px;border-bottom:1px solid #e2e8f0;">
          <div style="font-size:14px;font-weight:700;color:#0f172a;">{icon_html}{_html.escape(title)}</div>
          {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── 9. SINGLE EXPORT PATTERN ───────────────────────────────────────────────────

def export_row(items: list[dict], key_prefix: str = "export") -> None:
    """
    Unified export button row.
    items: list of {label, data, filename, mime, icon?}
    """
    if not items:
        return
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        with col:
            icon  = item.get("icon", "⬇️")
            label = item.get("label", "Download")
            st.download_button(
                f"{icon} {label}",
                data=item["data"],
                file_name=item["filename"],
                mime=item.get("mime", "application/octet-stream"),
                key=f"{key_prefix}_{label.lower().replace(' ', '_')}",
                use_container_width=True,
            )


# ── Analyze New Repository ──────────────────────────────────────────────────────

_ANALYZE_NEW_REPO_SESSION_KEYS = [
    "wizard_step", "last_analysis_jobs", "readiness_score", "effort_estimate",
    "auto_fix_recs", "wizard_report_file", "wizard_patch_file",
    "wizard_uploaded_file_data", "wizard_uploaded_file_name",
    "_analysis_complete", "repository_health_score",
    "custom_analysis", "deprecated_rows", "qlik_readiness",
    "tiap_context_profile", "tiap_component_profile", "tiap_routine_profile",
    "java_risk_analysis", "routine_analysis", "joblet_analysis",
    "repository_ai_context", "unsupported_component_report",
    "executive_dashboard_model", "migration_intelligence",
    "impact_intelligence", "upgrade_advisor", "migration_runbook",
    "framework_intelligence", "architecture_autofix_intelligence",
    "last_repo_path", "wizard_source_version", "wizard_target_version_val",
]


def render_analyze_new_repo_button(
    key: str = "analyze_new_repo_btn",
    label: str = "🔄 Analyze New Repository",
    use_container_width: bool = False,
    help: str = "Clear current analysis and return to the upload screen.",
) -> bool:
    """Render a button that clears session/cache and returns to the upload screen.

    Returns True if the button was clicked (caller does not need to st.rerun()).
    """
    if st.button(label, key=key, use_container_width=use_container_width, help=help):
        for _k in _ANALYZE_NEW_REPO_SESSION_KEYS:
            st.session_state.pop(_k, None)
        # Clearing state alone does not move the user off whatever page
        # they were on — nav selection is driven by the separate
        # "_nav_idx2" session key. Without resetting it, the click
        # appeared to do nothing: the user stayed on e.g. Job 360 /
        # Search / Executive Dashboard and just saw a "Load a
        # repository first" warning instead of being returned to the
        # upload screen. Explicitly send the user back to Home and
        # straight to the upload form (skip the marketing landing page)
        # so "Analyze New Repository" always results in a visible,
        # actionable change.
        st.session_state["_nav_idx2"] = 0  # Home
        st.session_state["_home_show_upload"] = True
        st.session_state["wizard_step"] = 1
        st.rerun()
    return False
