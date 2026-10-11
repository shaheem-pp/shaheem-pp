"""Recent public GitHub activity, drawn as a server access log, plus a strip of
active days over the last 90 days."""

from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Optional

from svgkit import Doc, clip, section_heading

USER = os.environ.get("GH_USER", "shaheem-pp")
LINES = 8
DAYS = 90

# Repo language -> runtime colour token, matching the site's families
RUNTIME = {
    "Python": "python", "Jupyter Notebook": "python",
    "C#": "dotnet", "F#": "dotnet", "Visual Basic .NET": "dotnet",
    "Swift": "mobile", "Kotlin": "mobile", "Java": "mobile", "Objective-C": "mobile", "Dart": "mobile",
    "TypeScript": "web", "JavaScript": "web", "HTML": "web", "CSS": "web", "SCSS": "web", "Vue": "web", "Svelte": "web",
}


def _get(url: str, accept: str = "application/vnd.github+json"):
    headers = {"Accept": accept, "User-Agent": f"{USER}-profile-readme"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com"):
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as res:
        body = res.read().decode("utf-8")
    return json.loads(body) if accept.endswith("json") else body


def _safe(url: str):
    """Lookups like a deleted commit can fail; the log line still renders without them."""
    try:
        return _get(url)
    except Exception:
        return None


def _first_line(text: Optional[str]) -> str:
    return (text or "").split("\n")[0].strip()


def _entry(event: dict) -> Optional[dict]:
    kind, p, repo = event["type"], event["payload"], event["repo"]["name"]
    name = repo[len(USER) + 1:] if repo.startswith(USER + "/") else repo
    line = {"at": event["created_at"][:16].replace("T", " ") + "Z", "repo": repo, "name": name}

    def out(method, rest, status, note=""):
        return {**line, "method": method, "rest": rest, "status": status, "note": note}

    if kind == "PushEvent":
        commit = _safe(f"https://api.github.com/repos/{repo}/commits/{p.get('head')}")
        msg = _first_line(((commit or {}).get("commit") or {}).get("message"))
        return out("POST", "/commits", 201, f'"{msg}"' if msg else "")
    if kind == "PullRequestEvent":
        action = p.get("action")
        if action not in ("opened", "merged", "closed"):
            return None
        pr = _safe(f"https://api.github.com/repos/{repo}/pulls/{p.get('number')}") or {}
        title = f'"{_first_line(pr.get("title"))}"' if pr.get("title") else ""
        if action == "opened":
            return out("POST", f"/pulls/{p.get('number')}", 201, title)
        merged = action == "merged" or pr.get("merged")
        return out("PATCH", f"/pulls/{p.get('number')}", 200, ("merged " if merged else "closed ") + title)
    if kind == "CreateEvent":
        if p.get("ref_type") == "repository":
            return out("PUT", "", 201, "new repository")
        return out("PUT", f"/{p.get('ref_type')}es", 201, p.get("ref") or "")
    if kind == "DeleteEvent":
        return out("DELETE", f"/{p.get('ref_type')}es", 204, p.get("ref") or "")
    if kind == "ReleaseEvent":
        return out("POST", "/releases", 201, (p.get("release") or {}).get("tag_name", ""))
    if kind == "ForkEvent":
        return out("POST", "/forks", 202)
    if kind == "WatchEvent":
        return out("PUT", "/stargazers", 204, "★")
    if kind == "PublicEvent":
        return out("PATCH", "", 200, "now public")
    if kind == "IssuesEvent" and p.get("action") == "opened":
        return out("POST", f"/issues/{(p.get('issue') or {}).get('number', '')}", 201)
    return None


def access_log() -> List[dict]:
    events = _get(f"https://api.github.com/users/{USER}/events/public?per_page=100")
    # The feed is ordered by event id, which can drift from event time.
    events.sort(key=lambda e: e["created_at"], reverse=True)
    lines: List[dict] = []
    languages: Dict[str, Optional[str]] = {}
    for event in events:
        if len(lines) >= LINES:
            break
        line = _entry(event)
        if not line:
            continue
        prev = lines[-1] if lines else None
        # Fold a burst of identical requests (say, five pushes) into the newest line.
        if prev and (prev["method"], prev["repo"], prev["rest"]) == (line["method"], line["repo"], line["rest"]):
            prev["repeat"] = prev.get("repeat", 1) + 1
            continue
        if line["repo"] not in languages:
            languages[line["repo"]] = (_safe(f"https://api.github.com/repos/{line['repo']}") or {}).get("language")
        line["runtime"] = RUNTIME.get(languages[line["repo"]] or "", "muted")
        lines.append(line)
    return lines


def active_days() -> Optional[List[dict]]:
    """The public contributions page needs no token and counts private work when
    the profile shows it, which the events API never does."""
    try:
        html = _get(f"https://github.com/users/{USER}/contributions", accept="text/html")
    except Exception as err:
        print(f"skipping the active-days strip: {err}")
        return None
    counts = {}
    for cell_id, text in re.findall(r'for="(contribution-day-component-[\d-]+)"[^>]*>([^<]*)</tool-tip>', html):
        m = re.match(r"(\d+) contribution", text)
        counts[cell_id] = int(m.group(1)) if m else 0
    days = []
    for tag in re.findall(r"<td[^>]*data-date=\"[^\"]+\"[^>]*>", html):
        date = re.search(r'data-date="([^"]+)"', tag).group(1)
        cell = re.search(r'id="([^"]+)"', tag)
        level = re.search(r'data-level="(\d)"', tag)
        days.append({
            "date": date,
            "level": int(level.group(1)) if level else 0,
            "count": counts.get(cell.group(1), 0) if cell else 0,
        })
    days.sort(key=lambda d: d["date"])
    return days[-DAYS:] or None


def fetch_activity() -> dict:
    return {
        "lines": access_log(),
        "days": active_days(),
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


def render_activity(theme: str, data: dict) -> str:
    W = 928  # drawing width inside the 36px panel frame
    doc = Doc(theme, W, 36)
    t = doc.t
    lines, days = data["lines"], data["days"]
    doc.defs.append(
        f'<pattern id="dots" width="16" height="16" patternUnits="userSpaceOnUse">'
        f'<circle cx="1.5" cy="1.5" r="1" fill="{t["dot"]}"/></pattern>'
    )
    doc.styles.append(
        ".caret{animation:blink 1.1s steps(1) infinite}@keyframes blink{50%{opacity:0}}"
        ".today{animation:today 2s ease-in-out infinite}@keyframes today{50%{opacity:.35}}"
    )
    top = section_heading(doc, 0, 12, "Activity", "Recent requests", "Public GitHub activity, every 6 hours.") + 32

    size, ch, pad = 13, 13 * 0.6, 26
    cols = int((W - pad * 2) / ch)
    line_h = 25
    bar = 46
    log_h = 18 + max(len(lines), 1) * line_h + 12
    strip_y = top + bar + log_h + 14
    H = strip_y + 92 if days else top + bar + log_h

    doc.defs.append(f'<clipPath id="card"><rect x="1" y="{top}" width="{W - 2}" height="{H - top - 1}" rx="12"/></clipPath>')
    doc.add(
        f'<rect x="1" y="{top}" width="{W - 2}" height="{H - top - 1}" rx="12" fill="{t["surface"]}"/>',
        f'<g clip-path="url(#card)"><rect x="0" y="{top}" width="{W}" height="{bar}" fill="{t["bg"]}"/>'
        f'<rect x="0" y="{top}" width="{W}" height="{bar}" fill="url(#dots)" opacity=".7"/></g>',
        f'<path d="M1 {top + bar}H{W - 1}" stroke="{t["border"]}"/>',
        f'<rect x="1.5" y="{top + .5}" width="{W - 3}" height="{H - top - 2}" rx="12" fill="none" stroke="{t["border"]}"/>',
    )
    cmd = f"tail -n {LINES} /var/log/github/{USER}.access.log"
    doc.add(
        doc.line(pad, top + 28, [("$ ", "mono5", size, "accent"), (cmd, "mono", size, "fg")]),
        f'<rect class="caret" x="{pad + (len(cmd) + 2.4) * ch:.1f}" y="{top + 17}" width="{ch * 0.9:.1f}" height="15" fill="{t["accent"]}" opacity=".7"/>',
        doc.text(W - pad, top + 28, f"updated {data['updated']}", "mono", 11.5, "muted", anchor="end"),
    )

    # Columns in characters: time, method, path, note, status
    c_method, c_path = 19, 27
    paths = [f"/{ln['name']}{ln['rest']}" for ln in lines]
    path_len = min(max([18] + [len(x) for x in paths]), 44)
    c_note = c_path + path_len + 2
    c_status = cols - 3
    note_max = (c_status - 2 - c_note) * ch

    def col(c):
        return pad + c * ch

    y0 = top + bar + 18 + 16
    for i, ln in enumerate(lines):
        y = y0 + i * line_h
        path = f"/{ln['name']}"
        rest = ln["rest"]
        if len(path) + len(rest) > path_len:
            path = path[: max(path_len - len(rest) - 1, 4)] + "…"
        note = ln["note"] + (f"  +{ln['repeat'] - 1} more" if ln.get("repeat") else "")
        doc.add(
            doc.text(col(0), y, ln["at"], "mono", size, "muted"),
            doc.text(col(c_method), y, ln["method"], "mono5", size, "accent"),
            doc.line(col(c_path), y, [(path, "mono5", size, ln["runtime"] if ln["runtime"] != "muted" else "fg"),
                                     (rest, "mono", size, "fg")] if rest else
                     [(path, "mono5", size, ln["runtime"] if ln["runtime"] != "muted" else "fg")]),
            doc.text(col(c_note), y, clip(note, "mono", size, note_max), "mono", size, "muted"),
            doc.text(col(c_status), y, str(ln["status"]), "mono5", size, "success" if ln["status"] < 300 else "muted"),
        )
    if not lines:
        doc.add(doc.text(pad, y0, "-- no public activity in the last 90 days --", "mono", size, "muted"))

    if days:
        active = sum(1 for d in days if d["count"] > 0 or d["level"] > 0)
        total = sum(d["count"] for d in days)
        doc.add(
            f'<path d="M1 {strip_y - 14}H{W - 1}" stroke="{t["border"]}" stroke-dasharray="3 3"/>',
            doc.text(pad, strip_y + 12, f"ACTIVE DAYS · LAST {len(days)}", "mono5", 11.5, "muted", spacing_px=1.2),
            doc.line(W - pad, strip_y + 12, [(f"{active}/{len(days)}", "mono5", 12, "success"),
                                             (f" days · {total:,} contributions", "mono", 12, "muted")], anchor="end"),
        )
        step = (W - pad * 2) / len(days)
        bw = max(step - 3, 2)
        opacity = [1, 0.4, 0.6, 0.8, 1]
        for i, d in enumerate(days):
            fill = t["success"] if d["level"] else t["border"]
            cls = ' class="today"' if i == len(days) - 1 and d["level"] else ""
            doc.add(
                f'<rect{cls} x="{pad + i * step:.2f}" y="{strip_y + 28}" width="{bw:.2f}" height="30" rx="2" '
                f'fill="{fill}" fill-opacity="{opacity[d["level"]]}"><title>{d["date"]}: {d["count"]} contributions</title></rect>'
            )
        doc.add(
            doc.text(pad, strip_y + 78, days[0]["date"], "mono", 11, "muted"),
            doc.text(W - pad, strip_y + 78, "today", "mono", 11, "muted", anchor="end"),
        )

    return doc.render(H, f"Recent public GitHub activity of {USER}, written as a server access log")
