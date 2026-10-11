"""Render the profile README's images from shaheem.dev/api/me.json.

    python scripts/render.py <out-dir> [--profile path/to/me.json]

Writes <section>-<theme>.svg for the hero, metrics, work, experience, stack,
activity and contact cards. .github/workflows/render.yml runs this every few
hours and publishes the files to the `output` branch, so the README follows
the site without being edited.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from typing import List

from activity import fetch_activity, render_activity
from svgkit import THEMES, Doc, measure, section_heading, wrap

PROFILE_URL = "https://www.shaheem.dev/api/me.json"
W = 1000


def load_profile(path: str | None) -> dict:
    if path:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    req = urllib.request.Request(PROFILE_URL, headers={"User-Agent": "shaheem-pp-readme"})
    with urllib.request.urlopen(req, timeout=20) as res:
        return json.load(res)


def common_defs(doc: Doc) -> None:
    t = doc.t
    doc.defs.append(
        f'<pattern id="dots" width="16" height="16" patternUnits="userSpaceOnUse">'
        f'<circle cx="1.5" cy="1.5" r="1" fill="{t["dot"]}"/></pattern>'
        f'<radialGradient id="glow"><stop offset="0" stop-color="{t["accent"]}" stop-opacity=".2"/>'
        f'<stop offset="1" stop-color="{t["accent"]}" stop-opacity="0"/></radialGradient>'
    )


def pulse_dot(doc: Doc, cx: float, cy: float, colour: str, r: float = 4) -> None:
    """A filled dot with a ring that breathes out of it (the site's live indicator)."""
    doc.styles.append(
        ".ring{transform-box:fill-box;transform-origin:center;animation:ring 2.4s ease-in-out infinite}"
        "@keyframes ring{0%,100%{transform:scale(.6);opacity:.35}50%{transform:scale(1.2);opacity:0}}"
    )
    doc.add(
        f'<circle class="ring" cx="{cx}" cy="{cy}" r="{r * 2.2:.1f}" fill="{colour}" opacity=".35"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{colour}"/>',
    )


# ---------------------------------------------------------------- hero


def json_preview(p: dict) -> List[List[tuple]]:
    """The hero card's slice of /api/me.json, as lines of (text, class) tokens."""
    def kv(key, value, comma=True, indent="  "):
        return [(indent, "muted"), (f'"{key}"', "accent"), (": ", "muted"),
                (f'"{value}"', "success"), ("," if comma else "", "muted")]

    loc = p["location"]
    now = p["current"]
    lines = [[("{", "muted")],
             kv("name", p["name"]),
             kv("role", p["role"]),
             kv("based_in", f'{loc["city"]}, {loc["country"]}'),
             kv("now", f'{now["title"]} @ {now["company"]}'),
             [("  ", "muted"), ('"shipped"', "accent"), (": [", "muted")]]
    shipped = [proj["name"] for proj in p["projects"][:3]]
    for i, name in enumerate(shipped):
        lines.append([("    ", "muted"), (f'"{name}"', "success"), ("," if i < len(shipped) - 1 else "", "muted")])
    lines.append([("  ],", "muted")])
    lines.append(kv("cares_about", p["caresAbout"], comma=False))
    lines.append([("}", "muted")])
    return lines


def hero(theme: str, p: dict) -> str:
    doc = Doc(theme, W)
    t = doc.t
    common_defs(doc)
    doc.styles.append(
        ".drift{animation:drift 14s ease-in-out infinite}"
        "@keyframes drift{0%,100%{transform:translate(0,0)}50%{transform:translate(-40px,18px)}}"
        ".caret{animation:blink 1.1s steps(1) infinite}@keyframes blink{50%{opacity:0}}"
    )
    doc.defs.append(
        '<radialGradient id="fade" cx=".78" cy=".35" r=".75"><stop offset="0" stop-color="#fff"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        '<mask id="dotmask"><rect width="100%" height="100%" fill="url(#fade)"/></mask>'
        '<filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="22"/></filter>'
    )

    left, col = 44, 470
    # Response card geometry (right column)
    cx, cw, cy = 548, 408, 40
    mono = 12.5
    lines = json_preview(p)
    body_top = cy + 40
    card_h = 40 + 22 + len(lines) * 19 + 46

    # Left column, top to bottom
    now = p["current"]
    pill_runs = [(f'{now["title"]} at {now["company"]}', "sans5", 14, "fg"),
                 (f' · {p["location"]["city"]}', "sans", 14, "muted")]
    pill_w = 34 + sum(measure(r[0], r[1], r[2]) for r in pill_runs) + 14
    name = p["name"]
    name_size = min(104.0, (col + 10) / measure(name + ".", "display", 1))
    name_base = 80 + name_size * 0.78
    tag_runs = [(p["tagline"]["lead"], "lead", 22, "fg"), (" " + p["tagline"]["trail"], "lead", 22, "muted")]
    tag_lines = wrap(tag_runs, col)
    tag_top = name_base + 48
    about_top = tag_top + (len(tag_lines) - 1) * 29 + 36
    about_lines = wrap([(p["about"], "sans", 15, "muted")], col)
    left_bottom = about_top + (len(about_lines) - 1) * 23
    H = max(left_bottom + 40, cy + card_h + 40)

    # Panel, dotted blueprint and drifting accent light
    doc.add(
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="16" fill="{t["bg"]}" stroke="{t["border"]}"/>',
        f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="16" fill="url(#dots)" mask="url(#dotmask)"/>',
        f'<g class="drift"><ellipse cx="{cx + cw * 0.55}" cy="{H * 0.55}" rx="330" ry="210" fill="url(#glow)"/></g>',
    )

    doc.add(f'<rect x="{left}" y="36" width="{pill_w:.1f}" height="32" rx="16" fill="{t["surface"]}" stroke="{t["border"]}"/>')
    pulse_dot(doc, left + 17, 52, t["success"])
    doc.add(doc.line(left + 31, 57, pill_runs))
    doc.add(doc.line(left - 3, name_base, [(name, "display", round(name_size, 1), "fg"), (".", "display", round(name_size, 1), "accent")]))
    for i, line in enumerate(tag_lines):
        doc.add(doc.line(left, tag_top + i * 29, line))
    for i, line in enumerate(about_lines):
        doc.add(doc.line(left, about_top + i * 23, line))

    # Response card with an accent shadow
    doc.add(
        f'<rect x="{cx + 40}" y="{cy + 60}" width="{cw - 80}" height="{card_h - 50}" rx="20" fill="{t["accent"]}" opacity=".35" filter="url(#soft)"/>',
        f'<rect x="{cx}" y="{cy}" width="{cw}" height="{card_h}" rx="12" fill="{t["surface"]}" stroke="{t["border"]}"/>',
        f'<path d="M{cx} {body_top}h{cw}" stroke="{t["border"]}"/>',
        doc.line(cx + 18, cy + 25, [("GET", "mono5", 13, "accent"), (" /api/me.json", "mono", 13, "muted")]),
        doc.text(cx + cw - 18, cy + 25, "200 OK", "mono", 13, "success", anchor="end"),
    )
    ch = mono * 0.6
    y = body_top + 30
    for i, tokens in enumerate(lines):
        runs = [(text, "mono", mono, cls) for text, cls in tokens if text]
        doc.add(doc.line(cx + 18, y + i * 19, runs))
    last = "".join(text for text, _ in lines[-1])
    doc.add(
        f'<rect class="caret" x="{cx + 18 + (len(last) + 1) * ch:.1f}" y="{y + (len(lines) - 1) * 19 - 11}" '
        f'width="7" height="14" fill="{t["accent"]}" opacity=".7"/>'
    )
    foot = cy + card_h - 18
    doc.add(
        doc.text(cx + 18, foot, "application/json", "mono", 12, "muted"),
        doc.text(cx + cw - 18, foot, "View full response →", "mono", 12, "accent", anchor="end"),
    )
    title = f'{name}. {p["role"]}. {p["tagline"]["lead"]} {p["tagline"]["trail"]}'
    return doc.render(H, title)


# ---------------------------------------------------------------- metrics


def metrics(theme: str, p: dict) -> str:
    doc = Doc(theme, W)
    t = doc.t
    H = 92
    colours = [t["python"], t["dotnet"], t["mobile"], t["web"]]
    gap = 44
    items, x = [], 0.0
    for m in p["metrics"]:
        vw = measure(m["value"], "display", 34)
        lw = measure(m["label"], "sans", 15)
        items.append((x, m, vw))
        x += vw + 14 + lw + gap + 8 + gap
    period = x
    copies = int(W // period) + 2
    parts = []
    for c in range(copies):
        for i, (ix, m, vw) in enumerate(items):
            px = c * period + ix
            parts.append(doc.text(px, 58, m["value"], "display", 34))
            parts.append(doc.text(px + vw + 14, 56, m["label"], "sans", 15, "muted"))
            sx = px + vw + 14 + measure(m["label"], "sans", 15) + gap
            parts.append(f'<rect x="{sx:.1f}" y="42" width="8" height="8" rx="2" fill="{colours[i % 4]}"/>')
    doc.styles.append(
        f".run{{animation:run {period / 38:.1f}s linear infinite}}"
        f"@keyframes run{{to{{transform:translateX(-{period:.1f}px)}}}}"
    )
    doc.defs.append(
        '<linearGradient id="edge"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".08" stop-color="#fff"/>'
        '<stop offset=".92" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        f'<mask id="m"><rect width="{W}" height="{H}" fill="url(#edge)"/></mask>'
    )
    doc.add(
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="14" fill="{t["surface"]}" stroke="{t["border"]}"/>',
        f'<g mask="url(#m)"><g transform="translate(32 0)"><g class="run">{"".join(parts)}</g></g></g>',
    )
    title = " · ".join(f'{m["value"]} {m["label"]}' for m in p["metrics"])
    return doc.render(H, title)


# ---------------------------------------------------------------- work


def flow_diagram(doc: Doc, n: int, x0: float, width: float, cy: float, flow: List[dict]) -> None:
    """Services left to right on a wire, with a request packet travelling through them."""
    t = doc.t
    size = 12.0
    pad, gap, h = 10, 26, 28

    def total(sz):
        return sum(measure(node["label"], "mono", sz) + pad * 2 for node in flow) + gap * (len(flow) - 1)

    while total(size) > width and size > 9.5:
        size -= 0.5
    start = x0 + (width - total(size)) / 2
    boxes, x = [], start
    for node in flow:
        w = measure(node["label"], "mono", size) + pad * 2
        boxes.append((x, w, node))
        x += w + gap
    first, last = boxes[0], boxes[-1]
    x_from, x_to = first[0] + first[1] / 2, last[0] + last[1] / 2

    # Wire under the boxes, so the packet shows between services and hides inside them
    doc.add(f'<path d="M{x_from:.1f} {cy}H{x_to:.1f}" stroke="{t["muted"]}" stroke-opacity=".45" stroke-dasharray="2 4"/>')
    travel = x_to - x_from
    key_at = next(((bx + bw / 2 - x_from) / travel for bx, bw, nd in boxes if nd.get("key")), None)
    move_end = 78
    doc.styles.append(
        f".pk{n}{{animation:pk{n} 3.6s cubic-bezier(.45,0,.55,1) infinite;animation-delay:-{n * 0.9:.1f}s}}"
        f"@keyframes pk{n}{{0%{{transform:translateX(0);opacity:0}}6%{{opacity:1}}"
        f"{move_end}%{{transform:translateX({travel:.1f}px);opacity:1}}88%,100%{{transform:translateX({travel:.1f}px);opacity:0}}}}"
    )
    doc.add(
        f'<g class="pk{n}"><circle cx="{x_from:.1f}" cy="{cy}" r="9" fill="{t["accent"]}" opacity=".22"/>'
        f'<circle cx="{x_from:.1f}" cy="{cy}" r="4" fill="{t["accent"]}"/></g>'
    )
    if key_at is not None:
        hit = key_at * move_end
        doc.styles.append(
            f".hit{n}{{animation:hit{n} 3.6s ease-out infinite;animation-delay:-{n * 0.9:.1f}s}}"
            f"@keyframes hit{n}{{0%,{max(hit - 4, 0):.0f}%{{stroke-opacity:.14;stroke-width:6}}"
            f"{hit + 2:.0f}%{{stroke-opacity:.5;stroke-width:10}}{min(hit + 22, 100):.0f}%,100%{{stroke-opacity:.14;stroke-width:6}}}}"
        )
    for i, (bx, bw, node) in enumerate(boxes):
        key = node.get("key")
        if key:
            doc.add(f'<rect class="hit{n}" x="{bx:.1f}" y="{cy - h / 2}" width="{bw:.1f}" height="{h}" rx="6" fill="none" stroke="{t["accent"]}" stroke-opacity=".14" stroke-width="6"/>')
        doc.add(
            f'<rect x="{bx:.1f}" y="{cy - h / 2}" width="{bw:.1f}" height="{h}" rx="6" fill="{t["surface"]}" '
            f'stroke="{t["accent"] if key else t["border"]}"/>',
            doc.text(bx + pad, cy + size * 0.36, node["label"], "mono", size, "accent" if key else "fg"),
        )
        if i:  # chevron into each service
            doc.add(f'<path d="M{bx - 9:.1f} {cy - 4}l4.5 4-4.5 4" fill="none" stroke="{t["muted"]}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>')


def project_card_height(proj: dict, inner: float) -> float:
    h = 112 + 38
    h += 26 + (len(wrap([(proj["summary"], "sans", 15, "fg")], inner)) - 1) * 22
    h += 26 + (len(wrap([(proj["result"], "sans", 13.5, "muted")], inner)) - 1) * 20
    h += 30 + 22
    d = proj["decision"]
    h += 22 + (len(wrap([(d["title"], "sans6", 14, "fg"), (" " + d["detail"], "sans", 13.5, "muted")], inner)) - 1) * 20
    return h + 50


def project_card(doc: Doc, n: int, x: float, y: float, w: float, h: float, proj: dict) -> None:
    t = doc.t
    inner = w - 40
    doc.defs.append(f'<clipPath id="c{n}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14"/></clipPath>')
    doc.add(
        f'<g clip-path="url(#c{n})"><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{t["surface"]}"/>'
        f'<rect x="{x}" y="{y}" width="{w}" height="112" fill="{t["bg"]}"/>'
        f'<rect x="{x}" y="{y}" width="{w}" height="112" fill="url(#dots)"/></g>',
        f'<path d="M{x} {y + 112}h{w}" stroke="{t["border"]}"/>',
        f'<rect x="{x + .5}" y="{y + .5}" width="{w - 1}" height="{h - 1}" rx="14" fill="none" stroke="{t["border"]}"/>',
    )
    flow_diagram(doc, n, x + 20, inner, y + 56, proj["flow"])

    cy = y + 112 + 38
    doc.add(doc.text(x + 20, cy, proj["name"], "title", 22))
    status = ("● " if proj["live"] else "") + proj["status"]
    doc.add(doc.text(x + w - 20, cy - 2, status, "mono", 11.5, "success" if proj["live"] else "muted", anchor="end"))
    cy = doc.paragraph(x + 20, cy + 26, [(proj["summary"], "sans", 15, "fg")], inner, 22)
    cy = doc.paragraph(x + 20, cy + 26, [(proj["result"], "sans", 13.5, "muted")], inner, 20)
    cy += 20
    doc.add(f'<path d="M{x + 20} {cy}h{inner}" stroke="{t["border"]}" stroke-dasharray="3 3"/>')
    cy += 22
    doc.add(doc.text(x + 20, cy, "KEY DECISION", "mono5", 10.5, "accent", spacing_px=1.2))
    d = proj["decision"]
    doc.paragraph(x + 20, cy + 22, [(d["title"], "sans6", 14, "fg"), (" " + d["detail"], "sans", 13.5, "muted")], inner, 20)

    fy = y + h - 20
    stack = " · ".join(proj["stack"])
    doc.add(doc.text(x + 20, fy, stack, "mono", 11.5, "muted"))
    links = "   ".join(f'{link["label"]} ↗' for link in proj["links"])
    if links:
        doc.add(doc.text(x + w - 20, fy, links, "sans5", 13, "accent", anchor="end"))


PANEL = 36
INNER = W - 2 * PANEL


def work(theme: str, p: dict) -> str:
    doc = Doc(theme, INNER, PANEL)
    common_defs(doc)
    top = section_heading(doc, 0, 12, "Selected work", "Things I've shipped",
                          "How each one works, and the decision behind it.") + 32
    gap = 20
    cw = (INNER - gap) / 2
    y = top
    projects = p["projects"]
    for row in range(0, len(projects), 2):
        pair = projects[row:row + 2]
        h = max(project_card_height(proj, cw - 40) for proj in pair)
        for i, proj in enumerate(pair):
            project_card(doc, row + i, i * (cw + gap), y, cw, h, proj)
        y += h + gap
    title = "Selected work: " + "; ".join(f'{q["name"]} ({q["status"]}): {q["summary"]} {q["result"]}' for q in projects)
    return doc.render(y - gap, title)


# ---------------------------------------------------------------- experience


def years(role: dict) -> str:
    start, end = role["start"], role["end"]
    if end is None:
        return f"{start} – now"
    if end == start:
        return str(start)
    return f"{start} – {str(end)[2:]}"


def experience(theme: str, p: dict) -> str:
    doc = Doc(theme, INNER, PANEL)
    t = doc.t
    top = section_heading(doc, 0, 12, "Experience", "Where I've worked",
                          "Backends for delivery, e-commerce and legal teams.")
    roles = list(reversed(p["experience"]))  # oldest on the left
    col = INNER / len(roles)
    text_w = col - 30
    line_y = top + 78
    xs = [i * col + 6 for i in range(len(roles))]

    # Rail: one segment per role in its runtime colour, the current one fading onward
    for i, role in enumerate(roles):
        c = t[role["runtime"]]
        x_end = xs[i + 1] if i + 1 < len(roles) else INNER
        if i + 1 < len(roles):
            doc.add(f'<path d="M{xs[i]} {line_y}H{x_end}" stroke="{c}" stroke-width="2" stroke-opacity=".7"/>')
        else:
            doc.defs.append(
                f'<linearGradient id="tail"><stop offset="0" stop-color="{c}" stop-opacity=".7"/>'
                f'<stop offset="1" stop-color="{c}" stop-opacity="0"/></linearGradient>'
            )
            doc.add(f'<rect x="{xs[i]}" y="{line_y - 1}" width="{x_end - xs[i]}" height="2" fill="url(#tail)"/>')

    bottom = 0.0
    for i, role in enumerate(roles):
        x = xs[i]
        c = t[role["runtime"]]
        current = role["end"] is None
        doc.add(doc.text(x - 6, line_y - 22, years(role), "mono", 12.5, "muted"))
        if current:
            pulse_dot(doc, x, line_y, c, 6)
        else:
            doc.add(f'<circle cx="{x}" cy="{line_y}" r="5.5" fill="{t["bg"]}" stroke="{c}" stroke-width="2.5"/>')
        y = doc.paragraph(x - 6, line_y + 38, [(role["title"], "sans6", 15.5, "fg")], text_w, 21)
        y = doc.paragraph(x - 6, y + 21, [(role["company"], "sans", 14.5, "muted")], text_w, 21)
        y = doc.paragraph(x - 6, y + 26, [(role["summary"], "sans", 13.5, "muted")], text_w, 20)
        y += 26
        doc.add(f'<rect x="{x - 6}" y="{y - 8.5}" width="8" height="8" rx="2" fill="{c}"/>')
        doc.add(doc.text(x + 8, y, " · ".join(role["stack"]), "mono", 11.5, "muted"))
        bottom = max(bottom, y)
    title = "Experience: " + "; ".join(f'{r["title"]} at {r["company"]}, {years(r)}: {r["summary"]}' for r in p["experience"])
    return doc.render(bottom + 4, title)


# ---------------------------------------------------------------- stack


def stack(theme: str, p: dict) -> str:
    doc = Doc(theme, INNER, PANEL)
    t = doc.t
    top = section_heading(doc, 0, 12, "Stack", "Right tool for the job",
                          "I pick by the constraint in front of me, not by habit.") + 32
    groups = p["stack"]
    gap = 16
    cw = (INNER - gap * (len(groups) - 1)) / len(groups)
    inner = cw - 36

    def card_h(g):
        tools = len(wrap([(g["tools"], "sans5", 16, "fg")], inner))
        use = len(wrap([(g["use"], "sans", 13.5, "muted")], inner))
        return 60 + 22 * tools + 20 * use + 18

    h = max(card_h(g) for g in groups)
    for i, g in enumerate(groups):
        x = i * (cw + gap)
        c = t[g["runtime"]]
        doc.defs.append(f'<clipPath id="s{i}"><rect x="{x}" y="{top}" width="{cw - 2}" height="{h}" rx="12"/></clipPath>')
        doc.add(
            f'<rect x="{x}" y="{top}" width="{cw - 2}" height="{h}" rx="12" fill="{t["surface"]}" stroke="{t["border"]}"/>',
            f'<rect x="{x}" y="{top}" width="{cw - 2}" height="3" fill="{c}" clip-path="url(#s{i})"/>',
            f'<rect x="{x + 18}" y="{top + 27}" width="9" height="9" rx="2" fill="{c}"/>',
            doc.text(x + 33, top + 36, g["area"], "mono5", 13, "fg"),
        )
        y = doc.paragraph(x + 18, top + 66, [(g["tools"], "sans5", 16, "fg")], inner, 22)
        doc.paragraph(x + 18, y + 22, [(g["use"], "sans", 13.5, "muted")], inner, 20)

    # Principles under the cards
    py = top + h + 34
    doc.add(f'<path d="M0 {py}H{INNER}" stroke="{t["border"]}"/>')
    pw = INNER / len(p["principles"])
    bottom = py
    for i, pr in enumerate(p["principles"]):
        x = i * pw
        doc.add(doc.text(x, py + 34, pr["title"], "sans6", 15, "fg"))
        bottom = max(bottom, doc.paragraph(x, py + 56, [(pr["detail"], "sans", 14, "muted")], pw - 30, 20))
    title = "Stack: " + "; ".join(f'{g["area"]}: {g["tools"]} ({g["use"]})' for g in groups)
    return doc.render(bottom + 4, title)


# ---------------------------------------------------------------- contact


def contact(theme: str, p: dict) -> str:
    doc = Doc(theme, W)
    t = doc.t
    common_defs(doc)
    email = p["contact"]["email"]
    head = wrap([("Need a backend your team can trust?", "display", 44, "fg")], 600)
    H = 64 + len(head) * 48 + 96
    doc.defs.append(f'<clipPath id="cc"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18"/></clipPath>')
    doc.styles.append(
        ".drift{animation:drift 12s ease-in-out infinite}"
        "@keyframes drift{0%,100%{transform:translate(0,0)}50%{transform:translate(-60px,-10px)}}"
    )
    doc.add(
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="18" fill="{t["surface"]}" stroke="{t["border"]}"/>',
        f'<g clip-path="url(#cc)"><g class="drift"><ellipse cx="{W * 0.72}" cy="{H * 0.95}" rx="420" ry="260" fill="url(#glow)"/></g></g>',
        doc.text(48, 54, "CONTACT", "mono5", 12, "muted", spacing_px=1.4),
    )
    y = 54 + 52
    for i, line in enumerate(head):
        doc.add(doc.line(46, y + i * 48, line))
    y += (len(head) - 1) * 48 + 58
    ew = measure(email, "mono5", 24)
    doc.add(
        doc.text(48, y, email, "mono5", 24, "fg"),
        f'<path d="M48 {y + 8}h{ew:.1f}" stroke="{t["accent"]}" stroke-opacity=".5" stroke-width="2"/>',
        doc.text(48 + ew + 14, y - 1, "↗", "mono5", 22, "accent"),
    )
    return doc.render(H, f"Contact: {email}")


# ---------------------------------------------------------------- main

SECTIONS = {
    "hero": hero,
    "metrics": metrics,
    "work": work,
    "experience": experience,
    "stack": stack,
    "contact": contact,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out")
    parser.add_argument("--profile", help="read me.json from a file instead of the site")
    parser.add_argument("--skip-activity", action="store_true", help="don't call the GitHub API")
    args = parser.parse_args()

    profile = load_profile(args.profile)
    os.makedirs(args.out, exist_ok=True)
    activity = None if args.skip_activity else fetch_activity()
    for theme in THEMES:
        for name, draw in SECTIONS.items():
            with open(os.path.join(args.out, f"{name}-{theme}.svg"), "w", encoding="utf-8") as f:
                f.write(draw(theme, profile))
        if activity is not None:
            with open(os.path.join(args.out, f"activity-{theme}.svg"), "w", encoding="utf-8") as f:
                f.write(render_activity(theme, activity))
    print(f"wrote {len(os.listdir(args.out))} files to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
