from __future__ import annotations

import io
import os
from datetime import date
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


# ── Constants ─────────────────────────────────────────────────────────────────

_NAVY   = colors.HexColor("#0b1d3a")
_WHITE  = colors.white
_GREEN  = colors.HexColor("#15803d")
_AMBER  = colors.HexColor("#b45309")
_RED    = colors.HexColor("#be123c")
_LGRAY  = colors.HexColor("#f1f5f9")
_DGRAY  = colors.HexColor("#475569")
_BGRAY  = colors.HexColor("#94a3b8")

PAGE_W, PAGE_H = landscape(A4)          # 841.89 x 595.28 pt
MARGIN         = 18 * mm
CONTENT_W      = PAGE_W - 2 * MARGIN
HEADER_H       = 60
FOOTER_H       = 24
BODY_TOP       = PAGE_H - HEADER_H - 8
BODY_BOTTOM    = FOOTER_H + 8
BODY_H         = BODY_TOP - BODY_BOTTOM


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rag_color(value: str) -> colors.HexColor:
    v = str(value).upper()
    if v in ("GREEN", "HIGH", "READY", "LOW_RISK"):
        return _GREEN
    if v in ("AMBER", "MEDIUM", "REVIEW"):
        return _AMBER
    return _RED


def _effort_rag(weeks) -> colors.HexColor:
    try:
        w = float(weeks)
        if w <= 8:
            return _GREEN
        if w <= 20:
            return _AMBER
        return _RED
    except (TypeError, ValueError):
        return _AMBER


def _risk_rag(risk_label: str) -> colors.HexColor:
    v = str(risk_label).upper()
    if "LOW" in v or v == "0":
        return _GREEN
    if "MEDIUM" in v or "MED" in v:
        return _AMBER
    return _RED


def _truncate(text: str, max_chars: int) -> str:
    s = str(text)
    return s if len(s) <= max_chars else s[: max_chars - 1] + "…"


def _draw_rect_with_top_border(c: canvas.Canvas, x: float, y: float,
                                w: float, h: float,
                                border_color: colors.Color,
                                fill_color: colors.Color = _LGRAY,
                                border_w: float = 3) -> None:
    c.setFillColor(fill_color)
    c.rect(x, y, w, h, fill=1, stroke=0)
    c.setFillColor(border_color)
    c.rect(x, y + h - border_w, w, border_w, fill=1, stroke=0)


# ── Main generator ────────────────────────────────────────────────────────────

def generate_executive_pdf(
    session_state: dict,
    client_name: str,
    logo_path: Optional[bytes] = None,
) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))

    today_str = date.today().strftime("%d %B %Y")

    # ── Session reads (all defensive) ────────────────────────────────────────
    all_jobs      = session_state.get("last_analysis_jobs") or []
    repo_path_raw = session_state.get("last_repo_path") or "—"
    repo_name     = os.path.basename(repo_path_raw.rstrip("/\\")) or repo_path_raw
    total_jobs    = len(all_jobs)

    readiness_score = session_state.get("readiness_score") or {}
    mrs_score = readiness_score.get("score") or readiness_score.get("overallScore") or "—"
    mrs_rag   = readiness_score.get("overall") or readiness_score.get("overallRag") or "AMBER"

    effort_estimate = session_state.get("effort_estimate") or {}
    est_weeks  = effort_estimate.get("estimated_weeks") or "—"
    est_hours  = effort_estimate.get("estimated_hours") or "—"

    risk_label = (session_state.get("readiness_score") or {}).get("risk") or "MEDIUM"
    cloud_status = "GREEN"
    if all_jobs:
        red_c   = sum(1 for j in all_jobs if (j.get("cloud_readiness") or {}).get("readiness") == "LOW")
        amber_c = sum(1 for j in all_jobs if (j.get("cloud_readiness") or {}).get("readiness") == "MEDIUM")
        if red_c > total_jobs * 0.3:
            cloud_status = "RED"
        elif amber_c > total_jobs * 0.3:
            cloud_status = "AMBER"

    qlik_results = session_state.get("qlik_readiness") or []
    qlik_native  = sum(1 for r in qlik_results if r.get("qlik_path") == "QLIK_NATIVE")
    qlik_partial = sum(1 for r in qlik_results if r.get("qlik_path") == "QLIK_PARTIAL")
    qlik_manual  = sum(1 for r in qlik_results if r.get("qlik_path") == "MANUAL_REWRITE")

    # ── HEADER BAND ──────────────────────────────────────────────────────────
    c.setFillColor(_NAVY)
    c.rect(0, PAGE_H - HEADER_H, PAGE_W, HEADER_H, fill=1, stroke=0)

    if logo_path:
        try:
            img_reader = ImageReader(io.BytesIO(logo_path))
            c.drawImage(img_reader, MARGIN, PAGE_H - HEADER_H + 8,
                        width=120, height=HEADER_H - 16,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            c.setFillColor(_WHITE)
            c.setFont("Helvetica-Bold", 18)
            c.drawString(MARGIN, PAGE_H - HEADER_H + 22, "ARTHA TALEND")
    else:
        c.setFillColor(_WHITE)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(MARGIN, PAGE_H - HEADER_H + 22, "ARTHA TALEND")

    c.setFillColor(_WHITE)
    c.setFont("Helvetica-Bold", 12)
    label = "Migration Assessment Report"
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - HEADER_H + 30, label)
    c.setFont("Helvetica", 9)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - HEADER_H + 16, today_str)

    # ── SECTION 1 — Client info (left ~40%) ──────────────────────────────────
    S1_X  = MARGIN
    S1_W  = CONTENT_W * 0.38
    S1_Y  = BODY_TOP - 10
    LINE  = 14

    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(_NAVY)
    c.drawString(S1_X, S1_Y, "Assessment Details")
    c.setStrokeColor(_NAVY)
    c.setLineWidth(0.5)
    c.line(S1_X, S1_Y - 3, S1_X + S1_W, S1_Y - 3)

    info_lines = [
        ("Prepared for",    _truncate(client_name, 40)),
        ("Repository",      _truncate(repo_name, 40)),
        ("Jobs in scope",   str(total_jobs)),
        ("Assessment date", today_str),
        ("Assessed by",     "Artha Solutions — TMA v3.0"),
    ]
    c.setFont("Helvetica", 9)
    cy = S1_Y - LINE - 4
    for label, value in info_lines:
        c.setFillColor(_BGRAY)
        c.setFont("Helvetica", 8)
        c.drawString(S1_X, cy, label + ":")
        c.setFillColor(_NAVY)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(S1_X + 80, cy, value)
        cy -= LINE

    # ── SECTION 2 — KPI 2×2 grid (right ~60%) ────────────────────────────────
    S2_X  = MARGIN + CONTENT_W * 0.42
    S2_W  = CONTENT_W * 0.58
    S2_Y  = BODY_TOP - 10
    BOX_W = (S2_W - 8) / 2
    BOX_H = 52

    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(_NAVY)
    c.drawString(S2_X, S2_Y, "Key Performance Indicators")
    c.setStrokeColor(_NAVY)
    c.line(S2_X, S2_Y - 3, S2_X + S2_W, S2_Y - 3)

    kpis = [
        ("Migration Readiness", str(mrs_score) + ("%" if str(mrs_score).isdigit() else ""), _rag_color(mrs_rag)),
        ("Cloud Readiness",     cloud_status,                                                 _rag_color(cloud_status)),
        ("Total Effort",        f"{est_weeks} wks",                                          _effort_rag(est_weeks)),
        ("Risk Level",          str(risk_label),                                              _risk_rag(str(risk_label))),
    ]

    box_positions = [
        (S2_X,             S2_Y - BOX_H - 12),
        (S2_X + BOX_W + 8, S2_Y - BOX_H - 12),
        (S2_X,             S2_Y - BOX_H * 2 - 20),
        (S2_X + BOX_W + 8, S2_Y - BOX_H * 2 - 20),
    ]

    for (label, value, color), (bx, by) in zip(kpis, box_positions):
        _draw_rect_with_top_border(c, bx, by, BOX_W, BOX_H, color)
        c.setFillColor(color)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(bx + BOX_W / 2, by + BOX_H - 26, _truncate(str(value), 12))
        c.setFillColor(_DGRAY)
        c.setFont("Helvetica", 8)
        c.drawCentredString(bx + BOX_W / 2, by + 8, label)

    # ── SECTION 3 — Wave plan table ───────────────────────────────────────────
    waves: dict[int, list[dict]] = {1: [], 2: [], 3: []}
    for j in all_jobs:
        est  = j.get("estimation") or {}
        comp = est.get("complexity") or j.get("complexity", {}).get("level") or "UNKNOWN"
        comp = str(comp).upper()
        hrs  = est.get("estimated_hours") or 0
        try:
            hrs = float(hrs)
        except (TypeError, ValueError):
            hrs = 0.0
        entry = {"name": (j.get("job_data") or {}).get("job_name", "?"), "complexity": comp, "hours": hrs}
        if comp in ("HIGH", "CRITICAL"):
            waves[3].append(entry)
        elif comp == "MEDIUM":
            waves[2].append(entry)
        else:
            waves[1].append(entry)

    TABLE_Y   = S2_Y - BOX_H * 2 - 38
    TABLE_X   = MARGIN
    TABLE_W   = CONTENT_W
    ROW_H     = 16
    HDR_H     = 18

    col_widths = [TABLE_W * f for f in [0.08, 0.08, 0.14, 0.14, 0.12, 0.44]]
    headers    = ["Wave", "Jobs", "Complexity", "Est. Hours", "Est. Weeks", "Recommended Start"]
    start_dates = {1: "Month 1", 2: "Month 3", 3: "Month 6"}
    complexities = {1: "LOW", 2: "MEDIUM", 3: "HIGH / CRITICAL"}

    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(_NAVY)
    c.drawString(TABLE_X, TABLE_Y + HDR_H + 4, "Wave Plan")
    c.line(TABLE_X, TABLE_Y + HDR_H + 1, TABLE_X + TABLE_W, TABLE_Y + HDR_H + 1)

    c.setFillColor(_NAVY)
    c.rect(TABLE_X, TABLE_Y, TABLE_W, HDR_H, fill=1, stroke=0)
    cx = TABLE_X
    c.setFillColor(_WHITE)
    c.setFont("Helvetica-Bold", 8)
    for w, hdr in zip(col_widths, headers):
        c.drawString(cx + 3, TABLE_Y + 5, hdr)
        cx += w

    wave_colors = {1: colors.HexColor("#dcfce7"), 2: colors.HexColor("#fef9c3"), 3: colors.HexColor("#fee2e2")}
    total_h_all = 0.0
    row_y = TABLE_Y - ROW_H

    for wnum in (1, 2, 3):
        wjobs  = waves[wnum]
        w_h    = sum(e["hours"] for e in wjobs)
        w_wks  = round(w_h / 40, 1) if w_h else 0
        total_h_all += w_h
        c.setFillColor(wave_colors[wnum])
        c.rect(TABLE_X, row_y, TABLE_W, ROW_H, fill=1, stroke=0)
        c.setStrokeColor(colors.HexColor("#e2e8f0"))
        c.setLineWidth(0.3)
        c.line(TABLE_X, row_y, TABLE_X + TABLE_W, row_y)
        row_vals = [
            f"Wave {wnum}",
            str(len(wjobs)),
            complexities[wnum],
            f"{w_h:.0f}",
            f"{w_wks}",
            start_dates[wnum],
        ]
        cx = TABLE_X
        c.setFillColor(_NAVY)
        c.setFont("Helvetica", 8)
        for ww, val in zip(col_widths, row_vals):
            c.drawString(cx + 3, row_y + 4, _truncate(val, 30))
            cx += ww
        row_y -= ROW_H

    total_wks = round(total_h_all / 40, 1)
    c.setFillColor(colors.HexColor("#e2e8f0"))
    c.rect(TABLE_X, row_y, TABLE_W, ROW_H, fill=1, stroke=0)
    c.setFillColor(_NAVY)
    c.setFont("Helvetica-Bold", 8)
    footer_vals = ["Total", str(total_jobs), "—", f"{total_h_all:.0f}", f"{total_wks}", "—"]
    cx = TABLE_X
    for ww, val in zip(col_widths, footer_vals):
        c.drawString(cx + 3, row_y + 4, val)
        cx += ww

    # ── SECTION 4 — Qlik readiness (optional) ────────────────────────────────
    if qlik_results:
        Q_Y = row_y - ROW_H - 10
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(_NAVY)
        c.drawString(TABLE_X, Q_Y + 10, "Talend Migration Readiness")
        c.line(TABLE_X, Q_Y + 8, TABLE_X + TABLE_W, Q_Y + 8)

        summary = (
            f"{qlik_native} jobs Qlik-native  ·  "
            f"{qlik_partial} jobs partial  ·  "
            f"{qlik_manual} jobs manual rewrite"
        )
        c.setFont("Helvetica", 8)
        c.setFillColor(_DGRAY)
        c.drawString(TABLE_X, Q_Y - 2, summary)

        BAR_Y   = Q_Y - 18
        BAR_H   = 10
        BAR_W   = TABLE_W
        q_total = max(qlik_native + qlik_partial + qlik_manual, 1)
        seg_widths = [
            BAR_W * qlik_native  / q_total,
            BAR_W * qlik_partial / q_total,
            BAR_W * qlik_manual  / q_total,
        ]
        seg_colors = [_GREEN, _AMBER, _RED]
        bx = TABLE_X
        for sw, sc in zip(seg_widths, seg_colors):
            if sw > 0:
                c.setFillColor(sc)
                c.rect(bx, BAR_Y, sw, BAR_H, fill=1, stroke=0)
                bx += sw

    # ── FOOTER BAND ───────────────────────────────────────────────────────────
    c.setFillColor(_LGRAY)
    c.rect(0, 0, PAGE_W, FOOTER_H, fill=1, stroke=0)

    c.setFont("Helvetica", 7)
    c.setFillColor(_DGRAY)
    c.drawString(MARGIN, FOOTER_H / 2 - 3, "Confidential — prepared by Artha Solutions")
    c.drawCentredString(PAGE_W / 2, FOOTER_H / 2 - 3, "Approved by: _____________  Date: _______")
    c.drawRightString(PAGE_W - MARGIN, FOOTER_H / 2 - 3, "Page 1 of 1")

    c.save()
    buf.seek(0)
    return buf.read()
