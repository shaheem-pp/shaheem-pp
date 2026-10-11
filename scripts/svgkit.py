"""Theme tokens, fonts and text layout for the README's SVG cards.

GitHub shows README images through <img>, which cannot load web fonts, so each
SVG embeds a subset of the fonts it uses. Text is measured with the same fonts
to wrap lines, since SVG has no automatic wrapping.
"""

from __future__ import annotations

import base64
import io
import os
from typing import Dict, List, Optional, Sequence, Tuple

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

# Same tokens as shaheem.dev (src/index.css).
THEMES: Dict[str, Dict[str, str]] = {
    "light": {
        "bg": "#f4f5f7", "surface": "#ffffff", "fg": "#12151c", "muted": "#5b6272",
        "border": "#dde0e6", "accent": "#2a44d4", "success": "#17803d", "dot": "#c9cdd6",
        "python": "#2f7d55", "dotnet": "#7044b8", "mobile": "#c4471b", "web": "#a86a12",
    },
    "dark": {
        "bg": "#0d0f14", "surface": "#151922", "fg": "#e7e9ef", "muted": "#959cab",
        "border": "#252a35", "accent": "#8f9dff", "success": "#4ade80", "dot": "#2b313d",
        "python": "#4fb886", "dotnet": "#a787e8", "mobile": "#f0784a", "web": "#e3a948",
    },
}

# key -> (file, letter-spacing in em)
FONTS = {
    "display": ("archivo-800-125.ttf", -0.035),
    "title": ("archivo-700-112.ttf", -0.02),
    "lead": ("archivo-600-100.ttf", -0.01),
    "sans": ("plex-sans-400.ttf", 0.0),
    "sans5": ("plex-sans-500.ttf", 0.0),
    "sans6": ("plex-sans-600.ttf", 0.0),
    "mono": ("plex-mono-400.ttf", 0.0),
    "mono5": ("plex-mono-500.ttf", 0.0),
}

_loaded: Dict[str, TTFont] = {}


def _font(key: str) -> TTFont:
    if key not in _loaded:
        _loaded[key] = TTFont(os.path.join(FONT_DIR, FONTS[key][0]))
    return _loaded[key]


def measure(text: str, font: str, size: float) -> float:
    f = _font(font)
    cmap = f.getBestCmap()
    hmtx = f["hmtx"]
    upm = f["head"].unitsPerEm
    space = hmtx[cmap[32]][0]
    advance = sum(hmtx[cmap[ord(c)]][0] if ord(c) in cmap else space for c in text)
    return advance * size / upm + FONTS[font][1] * size * len(text)


def esc(text: str) -> str:
    return (
        str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


Run = Tuple[str, str, float, str]  # text, font, size, css class for colour


def wrap(runs: Sequence[Run], width: float) -> List[List[Run]]:
    """Greedy word wrap over styled runs. Returns lines, each a list of runs."""
    words: List[Tuple[str, str, float, str, bool]] = []  # text, font, size, cls, space_before
    for text, font, size, cls in runs:
        for i, word in enumerate(text.split(" ")):
            if word:
                # A run continues the previous one unless its text starts with a space.
                words.append((word, font, size, cls, i > 0 or text.startswith(" ")))
    lines: List[List[Run]] = [[]]
    x = 0.0
    for word, font, size, cls, spaced in words:
        piece = (" " if spaced and lines[-1] else "") + word
        w = measure(piece, font, size)
        if lines[-1] and x + w > width:
            lines.append([])
            piece, w, x = word, measure(word, font, size), 0.0
        line = lines[-1]
        if line and line[-1][1:] == (font, size, cls):
            line[-1] = (line[-1][0] + piece, font, size, cls)
        else:
            line.append((piece, font, size, cls))
        x += w
    return lines


def clip(text: str, font: str, size: float, width: float) -> str:
    if measure(text, font, size) <= width:
        return text
    while text and measure(text + "…", font, size) > width:
        text = text[:-1]
    return text.rstrip() + "…"


class Doc:
    """One SVG document: collects the text it draws so it can embed font subsets."""

    def __init__(self, theme: str, width: int, panel: float = 0):
        """width is the drawing area; panel > 0 frames it with that much padding on
        the site's background, so the image reads on any page colour."""
        self.t = THEMES[theme]
        self.width = width
        self.panel = panel
        self.used: Dict[str, set] = {}
        self.parts: List[str] = []
        self.styles: List[str] = []
        self.defs: List[str] = []

    def add(self, *parts: str) -> None:
        self.parts.extend(parts)

    def _use(self, font: str, text: str) -> None:
        self.used.setdefault(font, set()).update(text)

    def text(
        self, x: float, y: float, text: str, font: str, size: float, cls: str = "fg",
        anchor: str = "start", extra: str = "", spacing_px: Optional[float] = None,
    ) -> str:
        self._use(font, text)
        px = FONTS[font][1] * size if spacing_px is None else spacing_px
        spacing = f";letter-spacing:{px:.2f}px" if px else ""
        a = f' text-anchor="{anchor}"' if anchor != "start" else ""
        return (
            f'<text x="{x:.1f}" y="{y:.1f}"{a} class="{cls}" '
            f'style="font-family:{font};font-size:{size}px{spacing}"{extra}>{esc(text)}</text>'
        )

    def line(self, x: float, y: float, runs: Sequence[Run], anchor: str = "start") -> str:
        """A single line of mixed styles."""
        spans = []
        for text, font, size, cls in runs:
            self._use(font, text)
            tracking = FONTS[font][1]
            spacing = f";letter-spacing:{tracking * size:.2f}px" if tracking else ""
            spans.append(
                f'<tspan class="{cls}" style="font-family:{font};font-size:{size}px{spacing}">{esc(text)}</tspan>'
            )
        a = f' text-anchor="{anchor}"' if anchor != "start" else ""
        return f'<text x="{x:.1f}" y="{y:.1f}"{a}>{"".join(spans)}</text>'

    def paragraph(self, x: float, y: float, runs: Sequence[Run], width: float, leading: float) -> float:
        """Wrapped text starting at baseline y. Returns the baseline after the last line."""
        lines = wrap(runs, width)
        for i, line in enumerate(lines):
            self.add(self.line(x, y + i * leading, line))
        return y + (len(lines) - 1) * leading

    def _faces(self) -> str:
        faces = []
        for key, chars in sorted(self.used.items()):
            font = TTFont(os.path.join(FONT_DIR, FONTS[key][0]))
            opts = Options()
            opts.flavor = "woff2"
            opts.layout_features = ["kern"]
            opts.hinting = False
            sub = Subsetter(opts)
            sub.populate(text="".join(chars) + " ")
            sub.subset(font)
            font.flavor = "woff2"
            buf = io.BytesIO()
            font.save(buf)
            data = base64.b64encode(buf.getvalue()).decode()
            faces.append(f"@font-face{{font-family:{key};src:url(data:font/woff2;base64,{data}) format('woff2')}}")
        return "\n".join(faces)

    def render(self, height: float, title: str) -> str:
        t = self.t
        colours = "".join(f".{k}{{fill:{v}}}" for k, v in t.items())
        p = self.panel
        w, h = self.width + 2 * p, height + 2 * p
        body = "\n".join(self.parts)
        if p:
            self.defs.append(
                f'<pattern id="pdots" width="16" height="16" patternUnits="userSpaceOnUse">'
                f'<circle cx="1.5" cy="1.5" r="1" fill="{t["dot"]}"/></pattern>'
                '<radialGradient id="pfade" cx="1" cy="0" r=".9"><stop offset="0" stop-color="#fff"/>'
                '<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
                '<mask id="pmask"><rect width="100%" height="100%" fill="url(#pfade)"/></mask>'
            )
            body = (
                f'<rect x=".5" y=".5" width="{w - 1:.0f}" height="{h - 1:.0f}" rx="16" fill="{t["bg"]}" stroke="{t["border"]}"/>\n'
                f'<rect x="1" y="1" width="{w - 2:.0f}" height="{h - 2:.0f}" rx="16" fill="url(#pdots)" mask="url(#pmask)"/>\n'
                f'<g transform="translate({p} {p})">\n{body}\n</g>'
            )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
            f'viewBox="0 0 {w:.0f} {h:.0f}" role="img" aria-label="{esc(title)}">\n'
            f"<title>{esc(title)}</title>\n"
            f"<style>\n{self._faces()}\ntext{{white-space:pre}}\n{colours}\n"
            + "\n".join(self.styles)
            + "\n@media (prefers-reduced-motion:reduce){*{animation:none!important}}\n</style>\n"
            + (f"<defs>{''.join(self.defs)}</defs>\n" if self.defs else "")
            + body
            + "\n</svg>\n"
        )


def section_heading(doc: Doc, x: float, y: float, eyebrow: str, title: str, intro: Optional[str] = None) -> float:
    """Eyebrow + big title, intro right-aligned on the title's baseline. Returns that baseline."""
    doc.add(doc.text(x, y, eyebrow.upper(), "mono5", 12, "muted", spacing_px=1.4))
    base = y + 44
    doc.add(doc.text(x, base, title, "display", 40))
    if intro:
        doc.add(doc.text(doc.width - x, base, intro, "sans", 15, "muted", anchor="end"))
    return base
