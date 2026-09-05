"""Render the CassiFI Markdown paper to print-ready local HTML."""
from __future__ import annotations

import argparse
import base64
import hashlib
from html import escape
from pathlib import Path
import re
from typing import Sequence

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "cassi-technical-paper.md"
FIGURE = ROOT / "figures" / "field-intelligence-loop.svg"


def _stash_math(source: str) -> tuple[str, list[tuple[str, str]]]:
    values: list[tuple[str, str]] = []

    def display(match: re.Match[str]) -> str:
        token = f"CASSIDISPLAYMATH{len(values):04d}"
        values.append((token, match.group(0)))
        return f"\n\n{token}\n\n"

    def inline(match: re.Match[str]) -> str:
        token = f"CASSIINLINEMATH{len(values):04d}"
        values.append((token, match.group(0)))
        return token

    protected = re.sub(r"\\\[[\s\S]*?\\\]", display, source)
    protected = re.sub(r"\\\([^\n]*?\\\)", inline, protected)
    return protected, values


def render() -> str:
    source = PAPER.read_text(encoding="utf-8")
    protected, math_values = _stash_math(source)
    renderer = MarkdownIt("commonmark", {"html": False, "typographer": True}).enable("table")
    body = renderer.render(protected)
    for token, math in math_values:
        rendered = escape(math)
        if token.startswith("CASSIDISPLAY"):
            body = body.replace(f"<p>{token}</p>", f'<div class="math-block">{rendered}</div>')
        else:
            body = body.replace(token, f'<span class="math-inline">{rendered}</span>')

    figure_data = base64.b64encode(FIGURE.read_bytes()).decode("ascii")
    body = body.replace(
        'src="figures/field-intelligence-loop.svg"',
        f'src="data:image/svg+xml;base64,{figure_data}"',
    )
    paper_sha256 = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="source-sha256" content="{paper_sha256}">
<meta name="author" content="Carina Gardner">
<meta name="description" content="A mechanism-first account of persistent field learning, exact evidence, uncertainty, transparent nonverbal planning, and computational efficiency.">
<meta name="keywords" content="field intelligence, continual learning, associative memory, exact evidence, uncertainty, nonverbal reasoning, planning, interpretability, computational efficiency">
<meta name="license" content="CC BY 4.0">
<meta name="version" content="0.1.0">
<title>Cassi Field Intelligence: Persistent Learning, Exact Evidence, and Transparent Nonverbal Deliberation</title>
<script>
window.MathJax = {{
  tex: {{inlineMath: [['\\\\(', '\\\\)']], displayMath: [['\\\\[', '\\\\]']]}},
  svg: {{fontCache: 'local'}},
  options: {{enableMenu: false}}
}};
</script>
<script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
<style>
@page {{ size: A4; margin: 18mm 17mm 20mm; }}
:root {{ color: #172033; background: white; font-family: Georgia, 'Times New Roman', serif; font-size: 11.2pt; line-height: 1.48; }}
* {{ box-sizing: border-box; }}
body {{ max-width: 920px; margin: 0 auto; padding: 42px 54px 80px; }}
h1, h2, h3 {{ color: #101827; font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.16; page-break-after: avoid; break-after: avoid; }}
h1 {{ font-size: 30pt; letter-spacing: -0.035em; margin: 0 0 24px; border-bottom: 4px solid #2563eb; padding-bottom: 18px; }}
h2 {{ font-size: 20pt; margin: 44px 0 16px; border-bottom: 1px solid #cbd5e1; padding-bottom: 7px; }}
h3 {{ font-size: 14.5pt; margin: 28px 0 10px; }}
p {{ margin: 0 0 12px; orphans: 3; widows: 3; }}
a {{ color: #1d4ed8; text-decoration: none; overflow-wrap: anywhere; }}
blockquote {{ margin: 20px 28px; padding: 14px 20px; border-left: 4px solid #2563eb; background: #eff6ff; font-size: 12.5pt; }}
table {{ width: 100%; border-collapse: collapse; margin: 18px 0 24px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 8.8pt; page-break-inside: auto; }}
thead {{ display: table-header-group; }}
tr {{ page-break-inside: avoid; break-inside: avoid; }}
th, td {{ border: 1px solid #94a3b8; padding: 7px 8px; vertical-align: top; }}
th {{ background: #eaf1fb; color: #172033; text-align: left; }}
pre {{ border: 1px solid #cbd5e1; border-radius: 6px; background: #f8fafc; padding: 12px 14px; overflow-wrap: anywhere; white-space: pre-wrap; font-size: 8.5pt; page-break-inside: avoid; }}
code {{ font-family: 'Cascadia Mono', Consolas, monospace; font-size: 0.86em; background: #f1f5f9; padding: 0.08em 0.25em; border-radius: 3px; }}
pre code {{ background: transparent; padding: 0; }}
img {{ display: block; width: 100%; height: auto; margin: 22px auto 12px; page-break-inside: avoid; break-inside: avoid; }}
.math-block {{ margin: 15px 0; overflow: visible; text-align: center; page-break-inside: avoid; break-inside: avoid; }}
.math-inline {{ white-space: nowrap; }}
body > p:nth-of-type(-n+4) {{ font-family: 'Segoe UI', Arial, sans-serif; color: #334155; }}
hr {{ border: 0; border-top: 1px solid #cbd5e1; }}
@media print {{
  body {{ max-width: none; margin: 0; padding: 0; }}
  h2 {{ page-break-before: auto; }}
  a {{ color: inherit; }}
}}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(), encoding="utf-8", newline="\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
