"""
Pure-Python diagram renderer — no Graphviz, no Cairo, no native binaries.
Produces SVG strings (for HTML embedding) and PNG bytes (for DOCX/PDF)
using only the Pillow library (ships as self-contained wheels on all platforms).

Three diagram types:
  • Pipeline   — horizontal stage-flow  (Source → … → Target)
  • Flow       — component/subjob clusters, vertical flow within each cluster,
                 horizontal elbow routing between clusters
  • Dependency — parent job → child jobs fan-out
"""
from __future__ import annotations
import io
import math
from typing import Optional

# ── colour palette ────────────────────────────────────────────────────────────
_STAGE_COLORS = {
    "Source":         "#0ea5e9",
    "Validation":     "#f59e0b",
    "Transformation": "#6366f1",
    "Enrichment":     "#10b981",
    "Error Handling": "#dc2626",
    "Target":         "#64748b",
}
_NODE_FILL      = "#6366f1"
_NODE_TEXT      = "#ffffff"
_NODE_SUB_TEXT  = "#c7d2fe"
_CLUSTER_BG     = "#f1f5f9"
_CLUSTER_BORDER = "#94a3b8"
_EDGE_DATA      = "#0ea5e9"
_EDGE_TRIGGER   = "#dc2626"
_EDGE_PLAIN     = "#94a3b8"
_BG             = "#ffffff"
_LABEL_COLOR    = "#64748b"
_PARENT_FILL    = "#6366f1"
_CHILD_FILL     = "#94a3b8"
_FONT           = "Arial, sans-serif"


# ─────────────────────────────────────────────────────────────────────────────
# Low-level SVG helpers
# ─────────────────────────────────────────────────────────────────────────────

def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))

def _cid(color: str) -> str:          # arrowhead marker id suffix
    return color.lstrip("#")

def _svg_rect(x, y, w, h, fill, rx=6, stroke=None, sw=1) -> str:
    s = f'stroke="{stroke}" stroke-width="{sw}"' if stroke else 'stroke="none"'
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" rx="{rx}" {s}/>'

def _svg_text(x, y, text, fill="#ffffff", size=12, bold=False, anchor="middle") -> str:
    w = "bold" if bold else "normal"
    return (f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" '
            f'font-family="{_FONT}" font-weight="{w}" '
            f'text-anchor="{anchor}" dominant-baseline="central">'
            f'{_esc(text)}</text>')

def _arrowhead_defs(*colors) -> str:
    lines = ["<defs>"]
    for c in dict.fromkeys(colors):          # preserve order, deduplicate
        lines.append(
            f'<marker id="ah_{_cid(c)}" markerWidth="8" markerHeight="6" '
            f'refX="7" refY="3" orient="auto">'
            f'<polygon points="0 0, 8 3, 0 6" fill="{c}"/></marker>')
    lines.append("</defs>")
    return "\n".join(lines)

def _marker(color: str) -> str:
    return f'marker-end="url(#ah_{_cid(color)})"'

def _svg_line(x1, y1, x2, y2, color, dashed=False) -> str:
    dash = 'stroke-dasharray="6,3"' if dashed else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="2" {dash} {_marker(color)}/>')

def _svg_path(pts: list[tuple], color: str, dashed=False) -> str:
    """Polyline through pts list with arrowhead at last point."""
    dash = 'stroke-dasharray="6,3"' if dashed else ""
    d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" '
            f'{dash} {_marker(color)}/>')

def _svg_edge_label(x, y, text, color) -> str:
    if not text:
        return ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" fill="{color}" font-size="8" '
            f'font-family="{_FONT}" text-anchor="middle">{_esc(text)}</text>')

def _svg_wrap(w: int, h: int, body: str, defs: str = "") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">'
            f'<rect width="{w}" height="{h}" fill="{_BG}"/>'
            f'{defs}{body}</svg>')

def _wrap_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 1] + "…"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Pipeline SVG  (horizontal stage boxes with arrows)
# ─────────────────────────────────────────────────────────────────────────────

def _pipeline_svg(stage_counts: dict, stages: list) -> str:
    BW, BH, GAP, PAD = 130, 56, 30, 20
    W = max(PAD * 2 + len(stages) * BW + (len(stages) - 1) * GAP, 600)
    H = PAD * 2 + BH + 30
    parts = []
    for i, s in enumerate(stages):
        x = PAD + i * (BW + GAP)
        y = PAD + 15
        c = _STAGE_COLORS.get(s, "#6366f1")
        parts.append(_svg_rect(x, y, BW, BH, c, rx=8))
        parts.append(_svg_text(x + BW // 2, y + 18, s, size=11, bold=True))
        parts.append(_svg_text(x + BW // 2, y + 36,
                               f"({stage_counts.get(s, 0)} components)", size=9))
        if i < len(stages) - 1:
            # short horizontal arrow between boxes — stop 4px before next box
            parts.append(_svg_line(x + BW, y + BH // 2,
                                   x + BW + GAP - 4, y + BH // 2, _EDGE_PLAIN))
    defs = _arrowhead_defs(_EDGE_PLAIN)
    return _svg_wrap(W, H, "\n".join(parts), defs)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Flow SVG  (clusters side-by-side, vertical flow within, elbow cross-cluster)
# ─────────────────────────────────────────────────────────────────────────────
#
# Layout strategy
# ───────────────
# • Each subjob cluster is a vertical column of nodes (top-to-bottom).
# • Clusters are arranged left-to-right with a wide gap between them.
# • Within a cluster: edges are VERTICAL arrows (bottom of source → top of target).
#   When source is below target in the same cluster we route a small U-turn
#   to the right of the cluster so the line doesn't pass through boxes.
# • Cross-cluster edges: horizontal elbow that exits the right side of the
#   source cluster, travels horizontally to align with the target, then enters
#   the left side of the target node.

_NODE_W      = 160
_NODE_H      = 40
_NODE_GAP_Y  = 14     # vertical gap between nodes in a cluster
_CLUS_PAD_X  = 16     # horizontal padding inside cluster
_CLUS_PAD_Y  = 30     # top/bottom padding (extra top for label)
_CLUS_GAP_X  = 70     # horizontal gap between clusters (elbow corridor)
_OUTER_PAD   = 20


def _cluster_layout(subjob_list: list[list[str]]) -> list[tuple]:
    """Return list of (cx, cy, cw, ch) per cluster."""
    rects = []
    x = _OUTER_PAD
    for members in subjob_list:
        cw = _NODE_W + _CLUS_PAD_X * 2
        ch = (_CLUS_PAD_Y + len(members) * _NODE_H
              + max(len(members) - 1, 0) * _NODE_GAP_Y + _CLUS_PAD_Y // 2)
        rects.append((x, _OUTER_PAD, cw, ch))
        x += cw + _CLUS_GAP_X
    return rects


def _node_positions(subjob_list, cluster_rects) -> dict[str, tuple[float, float]]:
    """Centre-point of every node."""
    pos = {}
    for idx, members in enumerate(subjob_list):
        cx, cy, cw, ch = cluster_rects[idx]
        nx = cx + _CLUS_PAD_X + _NODE_W / 2          # horizontal centre of column
        for j, name in enumerate(members):
            ny = cy + _CLUS_PAD_Y + j * (_NODE_H + _NODE_GAP_Y) + _NODE_H / 2
            pos[name] = (nx, ny)
    return pos


def _node_cluster_idx(name: str, subjob_list: list[list[str]]) -> int:
    for i, members in enumerate(subjob_list):
        if name in members:
            return i
    return -1


def _draw_within_cluster_edge(nx_src, ny_src, nx_tgt, ny_tgt,
                               cluster_right_x, color, dashed) -> list[str]:
    """
    Route an edge between two nodes in the SAME cluster.
    Vertical arrow: bottom of source → top of target.
    If source is below target (reverse direction) we bow the line
    to the right of the cluster to avoid passing through boxes.
    """
    src_bot = ny_src + _NODE_H / 2    # bottom centre of source node
    tgt_top = ny_tgt - _NODE_H / 2    # top centre of target node

    if ny_src < ny_tgt:
        # Normal top-down: short straight vertical arrow
        # Stop 4px before target top to avoid arrowhead overlap
        return [_svg_line(nx_src, src_bot, nx_tgt, tgt_top - 4, color, dashed)]
    else:
        # Reverse: bow to the right of the cluster
        bow_x = cluster_right_x + 18
        pts = [
            (nx_src + _NODE_W / 2, ny_src),      # right edge of source
            (bow_x,                ny_src),        # exit right
            (bow_x,                tgt_top),       # travel vertically
            (nx_tgt + _NODE_W / 2 - 4, tgt_top),  # enter target from right
        ]
        return [_svg_path(pts, color, dashed)]


def _draw_cross_cluster_edge(nx_src, ny_src, cluster_src_right,
                              nx_tgt, ny_tgt, color, dashed, label="") -> list[str]:
    """
    Route an edge between two nodes in DIFFERENT clusters.
    Exits the right side of source cluster, elbows to target y, enters left of target.
    """
    src_right = nx_src + _NODE_W / 2
    tgt_left  = nx_tgt - _NODE_W / 2 - 4       # 4px gap before arrowhead lands

    # Corridor x: halfway between source cluster right edge and target cluster left
    # But clamp so it stays clearly in the gap
    corridor_x = cluster_src_right + _CLUS_GAP_X / 2

    if abs(ny_src - ny_tgt) < 4:
        # Approximately same height: plain horizontal line
        pts = [(src_right, ny_src), (tgt_left, ny_tgt)]
    else:
        pts = [
            (src_right,  ny_src),
            (corridor_x, ny_src),
            (corridor_x, ny_tgt),
            (tgt_left,   ny_tgt),
        ]
    parts = [_svg_path(pts, color, dashed)]
    if label:
        lx = corridor_x + 4
        ly = (ny_src + ny_tgt) / 2 - 6
        parts.append(_svg_edge_label(lx, ly, label, color))
    return parts


def _flow_svg(subjob_list, type_lookup, data_edges, trigger_edges) -> str:
    cluster_rects = _cluster_layout(subjob_list)
    node_pos      = _node_positions(subjob_list, cluster_rects)

    total_w = max(
        cluster_rects[-1][0] + cluster_rects[-1][2] + _OUTER_PAD + 40
        if cluster_rects else 500,
        500
    )
    max_ch  = max((r[3] for r in cluster_rects), default=100)
    total_h = _OUTER_PAD + max_ch + _OUTER_PAD + 10

    parts = []

    # ── clusters ──────────────────────────────────────────────────────────────
    for idx, (cx, cy, cw, ch) in enumerate(cluster_rects):
        parts.append(_svg_rect(cx, cy, cw, ch, _CLUSTER_BG, rx=8,
                               stroke=_CLUSTER_BORDER, sw=1))
        parts.append(_svg_text(cx + cw // 2, cy + 14,
                               f"Subjob {idx + 1}", fill=_LABEL_COLOR, size=9, bold=True))

    # ── nodes ─────────────────────────────────────────────────────────────────
    for name, (nx, ny) in node_pos.items():
        parts.append(_svg_rect(nx - _NODE_W / 2, ny - _NODE_H / 2,
                               _NODE_W, _NODE_H, _NODE_FILL, rx=5))
        parts.append(_svg_text(nx, ny - 6,  _wrap_text(name, 20), size=8))
        ctype = type_lookup.get(name, "")
        parts.append(_svg_text(nx, ny + 8,  f"({_wrap_text(ctype, 22)})",
                               size=7, fill=_NODE_SUB_TEXT))

    # ── edges ─────────────────────────────────────────────────────────────────
    all_edge_colors = [_EDGE_DATA, _EDGE_TRIGGER, _EDGE_PLAIN]

    for edge_list, color, dashed in [
        (data_edges,    _EDGE_DATA,    False),
        (trigger_edges, _EDGE_TRIGGER, True),
    ]:
        for s, t, ct in edge_list:
            if s not in node_pos or t not in node_pos:
                continue
            sx, sy = node_pos[s]
            tx, ty = node_pos[t]
            ci_s = _node_cluster_idx(s, subjob_list)
            ci_t = _node_cluster_idx(t, subjob_list)

            if ci_s == ci_t and ci_s >= 0:
                # Same cluster — vertical routing
                cr = cluster_rects[ci_s]
                cluster_right = cr[0] + cr[2]
                parts.extend(_draw_within_cluster_edge(
                    sx, sy, tx, ty, cluster_right, color, dashed))
            else:
                # Cross-cluster — horizontal elbow
                cr_s = cluster_rects[ci_s] if ci_s >= 0 else (sx, 0, 0, 0)
                cluster_src_right = cr_s[0] + cr_s[2]
                parts.extend(_draw_cross_cluster_edge(
                    sx, sy, cluster_src_right, tx, ty, color, dashed, ct))

    defs = _arrowhead_defs(*all_edge_colors)
    return _svg_wrap(total_w, total_h, "\n".join(parts), defs)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Dependency SVG  (parent → children fan-out)
# ─────────────────────────────────────────────────────────────────────────────

def _dependency_svg(job_name: str, child_jobs: list[str]) -> str:
    NW, NH = 180, 42
    PAD, GAP = 30, 16
    CORRIDOR = 50

    no_children = not child_jobs
    if no_children:
        child_jobs = ["No child jobs"]

    n  = len(child_jobs)
    W  = PAD * 2 + NW + CORRIDOR + NW + PAD
    H  = max(PAD * 2 + n * NH + (n - 1) * GAP, NH + PAD * 2)

    px = PAD
    py = H / 2 - NH / 2

    parts = []
    parts.append(_svg_rect(px, py, NW, NH, _PARENT_FILL, rx=6))
    parts.append(_svg_text(px + NW / 2, py + NH / 2,
                           _wrap_text(job_name, 22), size=10, bold=True))

    cx = PAD + NW + CORRIDOR
    for i, child in enumerate(child_jobs):
        cy = PAD + i * (NH + GAP)
        fill  = "#e2e8f0" if no_children else _CHILD_FILL
        tclr  = "#64748b" if no_children else _NODE_TEXT
        stroke = _CLUSTER_BORDER if no_children else None
        parts.append(_svg_rect(cx, cy, NW, NH, fill, rx=6, stroke=stroke))
        parts.append(_svg_text(cx + NW / 2, cy + NH / 2,
                               _wrap_text(child, 22), fill=tclr, size=10))

        src_x = px + NW
        src_y = py + NH / 2
        tgt_x = cx - 4
        tgt_y = cy + NH / 2
        corridor_x = px + NW + CORRIDOR / 2

        if abs(src_y - tgt_y) < 4:
            parts.append(_svg_line(src_x, src_y, tgt_x, tgt_y,
                                   _EDGE_PLAIN, dashed=no_children))
        else:
            pts = [(src_x, src_y),
                   (corridor_x, src_y),
                   (corridor_x, tgt_y),
                   (tgt_x, tgt_y)]
            parts.append(_svg_path(pts, _EDGE_PLAIN, dashed=no_children))

    defs = _arrowhead_defs(_EDGE_PLAIN)
    return _svg_wrap(W, H, "\n".join(parts), defs)


# ─────────────────────────────────────────────────────────────────────────────
# Public SVG entry points
# ─────────────────────────────────────────────────────────────────────────────

def build_pipeline_svg(job_data: dict, stages: list, stage_counts: dict) -> str:
    return _pipeline_svg(stage_counts, stages)

def build_flow_svg(job_data: dict, subjob_list, type_lookup,
                   data_edges, trigger_edges) -> str:
    if not subjob_list:
        return '<p style="color:#64748b;font-style:italic">No components found.</p>'
    return _flow_svg(subjob_list, type_lookup, data_edges, trigger_edges)

def build_dependency_svg(job_name: str, child_jobs: list) -> str:
    return _dependency_svg(job_name, child_jobs)


# ─────────────────────────────────────────────────────────────────────────────
# PNG via Pillow  (for DOCX / PDF)
# ─────────────────────────────────────────────────────────────────────────────

def _hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _get_fonts():
    try:
        from PIL import ImageFont
        try:
            reg  = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
            bold = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
            return (ImageFont.truetype(reg, 11),
                    ImageFont.truetype(bold, 12),
                    ImageFont.truetype(reg, 9))
        except Exception:
            f = ImageFont.load_default()
            return f, f, f
    except Exception:
        return None, None, None

def _draw_rr(draw, x, y, w, h, fill, radius=6, outline=None):
    draw.rounded_rectangle(
        [int(x), int(y), int(x+w), int(y+h)],
        radius=radius,
        fill=_hex_to_rgb(fill),
        outline=_hex_to_rgb(outline) if outline else None)

def _draw_txt(draw, cx, cy, text, font, fill="#ffffff"):
    rgb = _hex_to_rgb(fill) if isinstance(fill, str) else fill
    if font is None:
        draw.text((int(cx - len(text)*3), int(cy - 5)), text, fill=rgb)
        return
    bb  = draw.textbbox((0, 0), text, font=font)
    tw, th = bb[2]-bb[0], bb[3]-bb[1]
    draw.text((int(cx - tw/2), int(cy - th/2)), text, font=font, fill=rgb)

def _pil_arrow(draw, x1, y1, x2, y2, color, dashed=False, width=2):
    """Straight line segment with arrowhead — used for multi-segment paths."""
    rgb = _hex_to_rgb(color)
    if dashed:
        dx, dy = x2-x1, y2-y1
        length = math.hypot(dx, dy)
        if length < 1:
            return
        ux, uy = dx/length, dy/length
        d = 0.0
        on = True
        while d < length:
            nxt = min(d + (7 if on else 4), length)
            if on:
                draw.line([(x1+ux*d, y1+uy*d), (x1+ux*nxt, y1+uy*nxt)],
                          fill=rgb, width=width)
            d = nxt
            on = not on
    else:
        draw.line([(x1, y1), (x2, y2)], fill=rgb, width=width)

def _pil_arrowhead(draw, x2, y2, x1, y1, color, size=8):
    """Triangle arrowhead pointing from (x1,y1) toward (x2,y2)."""
    rgb = _hex_to_rgb(color)
    angle = math.atan2(y2-y1, x2-x1)
    p1 = (x2 - size*math.cos(angle-0.4), y2 - size*math.sin(angle-0.4))
    p2 = (x2 - size*math.cos(angle+0.4), y2 - size*math.sin(angle+0.4))
    draw.polygon([(x2, y2), p1, p2], fill=rgb)

def _pil_polyline_arrow(draw, pts, color, dashed=False):
    """Draw a multi-segment line with arrowhead at the last point."""
    for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
        _pil_arrow(draw, ax, ay, bx, by, color, dashed=dashed)
    if len(pts) >= 2:
        _pil_arrowhead(draw, pts[-1][0], pts[-1][1],
                       pts[-2][0], pts[-2][1], color)


def build_pipeline_png(job_data: dict, stages: list, stage_counts: dict) -> Optional[bytes]:
    try:
        from PIL import Image, ImageDraw
        BW, BH, GAP, PAD = 130, 56, 30, 20
        W = max(PAD*2 + len(stages)*BW + (len(stages)-1)*GAP, 600)
        H = PAD*2 + BH + 30
        img  = Image.new("RGB", (W, H), _hex_to_rgb(_BG))
        draw = ImageDraw.Draw(img)
        _, bfont, sfont = _get_fonts()
        for i, s in enumerate(stages):
            x = PAD + i*(BW+GAP); y = PAD+15
            _draw_rr(draw, x, y, BW, BH, _STAGE_COLORS.get(s,"#6366f1"), radius=8)
            _draw_txt(draw, x+BW//2, y+18, s, bfont)
            _draw_txt(draw, x+BW//2, y+36, f"({stage_counts.get(s,0)} comp.)", sfont)
            if i < len(stages)-1:
                ax1, ay = x+BW, y+BH//2
                _pil_polyline_arrow(draw, [(ax1,ay),(ax1+GAP-4,ay)], _EDGE_PLAIN)
        buf = io.BytesIO(); img.save(buf, "PNG"); return buf.getvalue()
    except Exception:
        return None


def build_flow_png(job_data: dict, subjob_list, type_lookup,
                   data_edges, trigger_edges) -> Optional[bytes]:
    if not subjob_list:
        return None
    try:
        from PIL import Image, ImageDraw
        cluster_rects = _cluster_layout(subjob_list)
        node_pos      = _node_positions(subjob_list, cluster_rects)
        W = max((cluster_rects[-1][0]+cluster_rects[-1][2]+_OUTER_PAD+40
                 if cluster_rects else 500), 500)
        H = _OUTER_PAD + max((r[3] for r in cluster_rects), default=100) + _OUTER_PAD + 10
        img  = Image.new("RGB", (int(W), int(H)), _hex_to_rgb(_BG))
        draw = ImageDraw.Draw(img)
        _, bfont, sfont = _get_fonts()
        rfont, _, _ = _get_fonts()

        for idx, (cx, cy, cw, ch) in enumerate(cluster_rects):
            _draw_rr(draw, cx, cy, cw, ch, _CLUSTER_BG, radius=8,
                     outline=_CLUSTER_BORDER)
            _draw_txt(draw, cx+cw//2, cy+14, f"Subjob {idx+1}", sfont,
                      fill=_LABEL_COLOR)

        for name, (nx, ny) in node_pos.items():
            _draw_rr(draw, nx-_NODE_W/2, ny-_NODE_H/2, _NODE_W, _NODE_H,
                     _NODE_FILL, radius=5)
            _draw_txt(draw, nx, ny-6, _wrap_text(name, 20), rfont)
            _draw_txt(draw, nx, ny+8,
                      f"({_wrap_text(type_lookup.get(name,''), 22)})",
                      sfont, fill=_NODE_SUB_TEXT)

        for edge_list, color, dashed in [
            (data_edges,    _EDGE_DATA,    False),
            (trigger_edges, _EDGE_TRIGGER, True),
        ]:
            for s, t, ct in edge_list:
                if s not in node_pos or t not in node_pos:
                    continue
                sx, sy = node_pos[s]; tx, ty = node_pos[t]
                ci_s = _node_cluster_idx(s, subjob_list)
                ci_t = _node_cluster_idx(t, subjob_list)
                if ci_s == ci_t >= 0:
                    cr = cluster_rects[ci_s]
                    cr_right = cr[0]+cr[2]
                    src_bot = sy + _NODE_H/2
                    tgt_top = ty - _NODE_H/2
                    if sy < ty:
                        _pil_polyline_arrow(draw, [(sx, src_bot),(sx, tgt_top-4)],
                                            color, dashed)
                    else:
                        bow_x = cr_right + 18
                        _pil_polyline_arrow(draw,
                            [(sx+_NODE_W/2, sy),
                             (bow_x, sy),(bow_x, tgt_top),
                             (tx+_NODE_W/2-4, tgt_top)], color, dashed)
                else:
                    cr_s = cluster_rects[ci_s] if ci_s>=0 else (sx,0,0,0)
                    csr  = cr_s[0]+cr_s[2]
                    corridor_x = csr + _CLUS_GAP_X/2
                    src_right  = sx + _NODE_W/2
                    tgt_left   = tx - _NODE_W/2 - 4
                    if abs(sy-ty) < 4:
                        _pil_polyline_arrow(draw, [(src_right,sy),(tgt_left,ty)],
                                            color, dashed)
                    else:
                        _pil_polyline_arrow(draw,
                            [(src_right, sy),(corridor_x, sy),
                             (corridor_x, ty),(tgt_left,  ty)], color, dashed)

        buf = io.BytesIO(); img.save(buf, "PNG"); return buf.getvalue()
    except Exception:
        return None


def build_dependency_png(job_name: str, child_jobs: list) -> Optional[bytes]:
    try:
        from PIL import Image, ImageDraw
        NW, NH, PAD, GAP, CORR = 180, 42, 30, 16, 50
        no_ch = not child_jobs
        if no_ch: child_jobs = ["No child jobs"]
        n = len(child_jobs)
        W = PAD*2 + NW + CORR + NW + PAD
        H = max(PAD*2 + n*NH + (n-1)*GAP, NH+PAD*2)
        img  = Image.new("RGB", (W, H), _hex_to_rgb(_BG))
        draw = ImageDraw.Draw(img)
        rfont, bfont, _ = _get_fonts()
        px, py = PAD, H//2 - NH//2
        _draw_rr(draw, px, py, NW, NH, _PARENT_FILL, radius=6)
        _draw_txt(draw, px+NW//2, py+NH//2, _wrap_text(job_name,22), bfont)
        cx2 = PAD+NW+CORR
        for i, child in enumerate(child_jobs):
            cy2 = PAD + i*(NH+GAP)
            fill = "#e2e8f0" if no_ch else _CHILD_FILL
            tc   = "#64748b" if no_ch else _NODE_TEXT
            _draw_rr(draw, cx2, cy2, NW, NH, fill, radius=6,
                     outline=_CLUSTER_BORDER if no_ch else None)
            _draw_txt(draw, cx2+NW//2, cy2+NH//2, _wrap_text(child,22), rfont, fill=tc)
            src_x, src_y = px+NW, py+NH//2
            tgt_x, tgt_y = cx2-4, cy2+NH//2
            corr_x = px+NW+CORR//2
            if abs(src_y-tgt_y) < 4:
                _pil_polyline_arrow(draw, [(src_x,src_y),(tgt_x,tgt_y)],
                                    _EDGE_PLAIN, dashed=no_ch)
            else:
                _pil_polyline_arrow(draw,
                    [(src_x,src_y),(corr_x,src_y),(corr_x,tgt_y),(tgt_x,tgt_y)],
                    _EDGE_PLAIN, dashed=no_ch)
        buf = io.BytesIO(); img.save(buf, "PNG"); return buf.getvalue()
    except Exception:
        return None
