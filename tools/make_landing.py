"""Build the static landing page (index.html) of a paper from a content file and the paper's generated number macros.

Usage: python3 tools/make_landing.py [content.json] [numbers.tex or -] [index.html]
Standard library only. Strings in the content file may contain {{macroName}}, which is replaced by the value of
\\newcommand{\\macroName}{value} in the numbers file, so the page and the paper always show the same figures.
Pass - as the numbers file for papers whose figures are written into the content file.
Every block except the abstract, the cite box and the footer is optional.
The layout is the editorial paper layout shared by the author's papers: serif text on warm paper, one accent colour,
labelled rows, a headline-number strip, figures with ruled captions and a BibTeX box.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

CSS = """
:root{--accent:#a64a24;--paper:#f4f1ea;--ink:oklch(0.21 0.012 70);--ink2:oklch(0.45 0.012 70);--ink3:oklch(0.4 0.012 70);--ink4:oklch(0.33 0.012 70);--rule:oklch(0.8 0.01 80);--rule2:oklch(0.88 0.01 80);--box:oklch(0.95 0.01 85);--sans:'IBM Plex Sans',system-ui,sans-serif;--mono:'IBM Plex Mono',monospace}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);font-family:'Newsreader',Georgia,'Times New Roman',serif;font-optical-sizing:auto;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
::selection{background:oklch(0.88 0.06 45)}
a{color:var(--ink);text-decoration-thickness:1px;text-underline-offset:3px;text-decoration-color:oklch(0.62 0.1 45 / .6)}
a:hover{color:var(--accent)}
.page{max-width:1040px;margin:0 auto;padding:0 40px 56px}
.mast{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 28px;padding:16px 0 14px;border-top:3px solid var(--ink);border-bottom:1px solid var(--rule);font-family:var(--sans);font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink2)}
.mast b{font-weight:600;color:var(--ink)}
.mast .date{margin-left:auto}
h1{margin:64px 0 0;max-width:900px;font-size:clamp(32px,5vw,50px);line-height:1.1;font-weight:500;letter-spacing:-.018em;text-wrap:balance}
h1 small{display:block;margin-top:20px;font-size:.58em;line-height:1.3;font-weight:400;letter-spacing:-.005em;color:var(--ink2)}
.authors{display:flex;flex-wrap:wrap;gap:16px 48px;margin-top:40px}
.author-name{font-size:20px;font-weight:600;line-height:1.3}
.author-meta{margin-top:4px;font-family:var(--sans);font-size:13.5px;line-height:1.5;color:var(--ink2)}
.author-meta i{margin:0 8px;color:oklch(0.7 0.01 80);font-style:normal}
.actions{display:flex;flex-wrap:wrap;align-items:center;gap:14px 28px;margin-top:32px;font-family:var(--sans);font-size:14px;font-weight:500}
.btn{display:inline-block;padding:11px 20px;background:var(--ink);color:var(--paper);text-decoration:none;border-radius:2px}
.btn:hover{background:var(--accent);color:var(--paper)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,190px),1fr));gap:28px 0;margin-top:64px;padding:28px 0;border-top:1px solid var(--ink);border-bottom:1px solid var(--rule)}
.stat{padding:2px 24px 2px 20px;border-left:1px solid var(--ink)}
.stat-v{font-size:46px;line-height:1;font-weight:400;letter-spacing:-.025em;font-variant-numeric:lining-nums tabular-nums}
.stat-l{margin-top:12px;max-width:210px;font-family:var(--sans);font-size:13px;line-height:1.4;color:var(--ink3)}
.row{display:flex;flex-wrap:wrap;gap:14px 56px;padding:40px 0 44px;border-top:1px solid var(--rule)}
.row.first{border-top:none;padding:48px 0 52px}
.row.tight{padding:36px 0 40px}
.label{flex:1 1 150px;max-width:190px;padding-top:4px;font-family:var(--sans);font-size:13.5px;font-weight:600;line-height:1.35}
.label.accent{color:var(--accent)}
.body{flex:999 1 480px;min-width:0;max-width:740px}
.lead{margin:0;font-size:23px;line-height:1.48;letter-spacing:-.005em;text-align:justify;text-justify:inter-word;hyphens:auto;text-wrap:pretty}
.abstract{margin:0;font-size:18px;line-height:1.7;color:oklch(0.27 0.012 70);text-align:justify;text-justify:inter-word;hyphens:auto;text-wrap:pretty}
.note{margin:0;font-size:16px;line-height:1.65;color:oklch(0.38 0.012 70);text-align:justify;text-justify:inter-word;hyphens:auto;text-wrap:pretty}
.note code{font-family:var(--mono);font-size:13px}
.scroll{overflow-x:auto}
table{width:100%;min-width:560px;border-collapse:collapse;font-size:16px;font-variant-numeric:lining-nums tabular-nums}
thead tr{border-top:2px solid var(--ink);border-bottom:1px solid var(--ink)}
th{padding:11px 12px;text-align:right;font-family:var(--sans);font-size:12px;font-weight:500;line-height:1.35;color:var(--ink3);vertical-align:bottom}
th:first-child,td:first-child{text-align:left;padding-left:0}
td{padding:9px 12px;text-align:right;border-bottom:1px solid var(--rule2)}
tr.group td{padding:16px 0 6px;text-align:left;font-family:var(--sans);font-size:12.5px;font-weight:600;letter-spacing:.04em;color:var(--ink2);border-bottom:none}
tbody tr:last-child td{border-bottom:2px solid var(--ink)}
td.hl{font-weight:600;color:var(--accent)}
td.b{font-weight:600}
table.left th,table.left td{text-align:left;padding-left:0;padding-right:16px}
table.left th:not(:first-child),table.left td:not(:first-child){padding-left:12px}
.table-note{margin:16px 0 0;font-family:var(--sans);font-size:13px;line-height:1.6;color:var(--ink3);text-wrap:pretty}
.finding{display:flex;gap:20px;padding:24px 0;border-top:1px solid var(--rule2)}
.finding:first-child{padding-top:0;border-top:none}
.finding:last-child{padding-bottom:0}
.finding .n{flex:0 0 22px;padding-top:5px;font-family:var(--sans);font-size:13px;font-weight:600;font-variant-numeric:tabular-nums;color:var(--accent)}
.finding h3{margin:0;font-size:20px;font-weight:600;line-height:1.3;letter-spacing:-.005em}
.finding p{margin:8px 0 0;font-size:17px;line-height:1.62;color:var(--ink4);text-wrap:pretty}
.figs{padding:40px 0 20px;border-top:1px solid var(--rule)}
.figs .label{padding-bottom:28px;max-width:none}
figure{margin:0 0 52px}
figure img{display:block;width:100%;height:auto;mix-blend-mode:multiply}
.pair{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:44px 48px;align-items:start;margin:0 0 52px}
.pair figure{margin:0}
figcaption{display:flex;gap:18px;margin-top:14px;padding-top:12px;border-top:1px solid var(--rule2);font-family:var(--sans);font-size:13.5px;line-height:1.55;color:oklch(0.38 0.012 70)}
figcaption b{flex:0 0 58px;font-weight:600;color:var(--ink)}
figcaption span{max-width:640px;text-wrap:pretty}
.kw{margin:0;font-size:17px;font-style:italic;line-height:1.6;color:var(--ink4)}
.bib{border:1px solid var(--rule);border-radius:2px;background:var(--box)}
.bib-bar{display:flex;align-items:center;justify-content:space-between;padding:8px 8px 8px 18px;border-bottom:1px solid oklch(0.86 0.01 80);font-family:var(--sans);font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink3)}
.bib button{font-family:var(--sans);font-size:12.5px;font-weight:500;letter-spacing:0;text-transform:none;padding:5px 14px;border:1px solid var(--ink);border-radius:2px;background:transparent;color:var(--ink);cursor:pointer}
.bib button:hover{background:var(--ink);color:var(--paper)}
.bib pre{margin:0;padding:18px 18px 22px;overflow-x:auto;font-family:var(--mono);font-size:12.5px;line-height:1.75;color:oklch(0.25 0.012 70)}
.links{border-top:1px solid var(--ink)}
.links a{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:2px 20px;padding:14px 0;border-bottom:1px solid var(--rule2);text-decoration:none}
.links a:last-child{border-bottom-color:var(--ink)}
.links span:first-child{font-size:19px}
.links span:first-child i{font-style:normal;font-size:15px;color:oklch(0.5 0.012 70)}
.links span:last-child{font-family:var(--sans);font-size:12.5px;color:var(--ink2)}
footer{display:flex;flex-direction:column;gap:10px;margin-top:24px;padding-top:24px;border-top:3px solid var(--ink);max-width:760px;font-family:var(--sans);font-size:12.5px;line-height:1.65;color:oklch(0.42 0.012 70)}
footer p{margin:0;text-wrap:pretty}
footer p:first-child{font-weight:500;color:var(--ink)}
@media(max-width:560px){.page{padding:0 20px 40px}.stat-v{font-size:40px}}
"""

FONTS = ("https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400&family=IBM+Plex+Sans:wght@400;500;600"
         "&family=Newsreader:ital,opsz,wght@0,6..72,300..700;1,6..72,300..700&display=swap")

SCRIPT = """
function copyBib(btn){
  var t=document.getElementById('bibtex').textContent;
  var done=function(){btn.textContent='Copied';setTimeout(function(){btn.textContent='Copy'},2000)};
  if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(done,done)}else{done()}
}
"""


def load_macros(path: Path) -> dict[str, str]:
    macros = {}
    for name, value in re.findall(r"\\newcommand\{\\(\w+)\}\{(.*)\}\s*$", path.read_text(), re.M):
        macros[name] = value.replace("\\,", ",").replace("\\%", "%").replace("$<0.001$", "<0.001").replace("$", "")
    return macros


def fill(text: str, macros: dict[str, str]) -> str:
    def sub(m: re.Match) -> str:
        if m.group(1) not in macros:
            raise KeyError(f"macro {m.group(1)} is not defined in the numbers file")
        return macros[m.group(1)]

    return re.sub(r"\{\{(\w+)\}\}", sub, text)


def walk(node, macros):
    if isinstance(node, str):
        return fill(node, macros)
    if isinstance(node, list):
        return [walk(x, macros) for x in node]
    if isinstance(node, dict):
        return {k: walk(v, macros) for k, v in node.items()}
    return node


def attr(text: str) -> str:
    return html.escape(text, quote=True)


def block(label: str, body: str, cls: str = "", label_cls: str = "") -> str:
    return f'<div class="row {cls}"><div class="label {label_cls}">{label}</div><div class="body">{body}</div></div>'


def cell(text: str) -> str:
    if text.startswith("!"):
        return f'<td class="hl">{text[1:]}</td>'
    if text.startswith("*"):
        return f'<td class="b">{text[1:]}</td>'
    return f"<td>{text}</td>"


def table(spec: dict) -> str:
    head = "".join(f"<th>{h}</th>" for h in spec["header"])
    rows = []
    for group in spec["groups"]:
        if group["name"]:
            rows.append(f'<tr class="group"><td colspan="{len(spec["header"])}">{group["name"]}</td></tr>')
        for r in group["rows"]:
            rows.append("<tr>" + "".join(cell(c) for c in r) + "</tr>")
    note = f'<p class="table-note">{spec["note"]}</p>' if spec.get("note") else ""
    cls = ' class="left"' if spec.get("align") == "left" else ""
    return f'<div class="scroll"><table{cls}><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>{note}'


def figure(f: dict, number: int) -> str:
    return (f'<figure><img src="{f["src"]}" alt="{attr(f["alt"])}" loading="lazy"><figcaption><b>Figure {number}</b>'
            f'<span>{f["caption"]}</span></figcaption></figure>')


def figures(items: list) -> str:
    out, n = [], 0
    for item in items:
        group = item if isinstance(item, list) else [item]
        figs = []
        for f in group:
            n += 1
            figs.append(figure(f, n))
        out.append(f'<div class="pair">{"".join(figs)}</div>' if len(group) > 1 else figs[0])
    return "".join(out)


def render(c: dict) -> str:
    m = c["meta"]
    url = m["site_url"]
    pdf = url + m["pdf"]
    scholar_title = m.get("scholar_title") or (m["title"] + (": " + m["subtitle"] if m.get("subtitle") else ""))
    html_title = m.get("html_title") or scholar_title
    heads = [
        f'<meta name="citation_title" content="{attr(scholar_title)}">',
        *[f'<meta name="citation_author" content="{attr(a["scholar"])}">' for a in m["authors"]],
        f'<meta name="citation_publication_date" content="{m["year"]}">',
        f'<meta name="citation_online_date" content="{m["online_date"]}">',
        '<meta name="citation_language" content="en">',
        f'<meta name="citation_abstract_html_url" content="{url}">',
        f'<meta name="citation_pdf_url" content="{pdf}">',
        f'<meta name="citation_keywords" content="{attr("; ".join(m["keywords"]))}">',
        f'<meta property="og:title" content="{attr(m.get("og_title") or m["title"])}">',
        f'<meta property="og:description" content="{attr(m["og_description"])}">',
        '<meta property="og:type" content="article">',
        f'<meta property="og:url" content="{url}">',
        *([f'<meta property="og:image" content="{url}{m["og_image"]}">'] if m.get("og_image") else []),
        f'<meta name="description" content="{attr(m["og_description"])}">',
    ]
    mast = "".join(f"<b>{t}</b>" if i == 0 else f"<span>{t}</span>" for i, t in enumerate(m["tags"]))
    authors = "".join(
        f'<div><div class="author-name">{a["name"]}</div><div class="author-meta">{a["affiliation"]}'
        + (f'<i>/</i><a href="mailto:{a["email"]}">{a["email"]}</a>' if a.get("email") else "") + "</div></div>"
        for a in m["authors"])
    actions = "".join(
        (f'<a class="btn" href="{a["url"]}" target="_blank" rel="noopener">{a["label"]}&nbsp;&darr;</a>' if i == 0 else
         f'<a href="{a["url"]}" target="_blank" rel="noopener">{a["label"]}&nbsp;&nearr;</a>') for i, a in enumerate(c["actions"]))
    parts = [
        f'<div class="mast">{mast}<span class="date">{m["date_label"]}</span></div>',
        f'<h1>{m["title"]}' + (f'<small>{m["subtitle"]}</small>' if m.get("subtitle") else "") + "</h1>",
        f'<div class="authors">{authors}</div>',
        f'<div class="actions">{actions}</div>',
    ]
    if c.get("stats"):
        stats = "".join(f'<div class="stat"><div class="stat-v">{s["value"]}</div><div class="stat-l">{s["label"]}</div></div>' for s in c["stats"])
        parts.append(f'<div class="stats">{stats}</div>')
    first = True
    if c.get("key_finding"):
        parts.append(f'<div class="row first"><div class="label accent" style="padding-top:7px">Key finding</div><div class="body"><p class="lead">{c["key_finding"]}</p></div></div>')
        first = False
    parts.append(block("Abstract", f'<p class="abstract">{c["abstract"]}</p>', "" if not first else "first"))
    if c.get("scope"):
        parts.append(block("Scope note", f'<p class="note">{c["scope"]}</p>', "tight"))
    if c.get("table"):
        parts.append(block(c["table"]["title"], table(c["table"])))
    if c.get("findings"):
        items = "".join(f'<div class="finding"><div class="n">{i + 1}</div><div><h3>{f["title"]}</h3><p>{f["text"]}</p></div></div>'
                        for i, f in enumerate(c["findings"]))
        parts.append(block(c["findings_title"], items))
    if c.get("figures"):
        parts.append(f'<div class="figs"><div class="label">{c.get("figures_title", "Key figures")}</div>{figures(c["figures"])}</div>')
    if c.get("data"):
        d = c["data"]
        parts.append(block(d["title"], table({"header": d["header"], "groups": [{"name": "", "rows": d["rows"]}], "note": d.get("note", ""), "align": "left"})))
    parts.append(block("Keywords", f'<p class="kw">{"; ".join(m["keywords_display"])}</p>', "tight"))
    parts.append(block("Cite this work", f'<div class="bib"><div class="bib-bar"><span>BibTeX</span><button onclick="copyBib(this)">Copy</button></div><pre id="bibtex">{html.escape(c["bibtex"])}</pre></div>'))
    links = "".join(f'<a href="{l["url"]}" target="_blank" rel="noopener"><span>{l["label"]}&nbsp;<i>&nearr;</i></span>'
                    f'<span>{re.sub(r"^https?://", "", l["url"]).rstrip("/")}</span></a>' for l in c["links"])
    parts.append(block("Links", f'<div class="links">{links}</div>'))
    parts.append(f'<footer>{"".join(f"<p>{p}</p>" for p in c["footer"])}</footer>')
    body = "".join(parts)
    return (f'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{html_title}</title>\n{chr(10).join(heads)}\n'
            f'<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            f'<link rel="stylesheet" href="{FONTS}">\n<style>{CSS}</style>\n</head>\n<body>\n<div class="page">\n{body}\n</div>\n<script>{SCRIPT}</script>\n</body>\n</html>\n')


def main() -> None:
    content = Path(sys.argv[1] if len(sys.argv) > 1 else "site/landing.json")
    numbers = sys.argv[2] if len(sys.argv) > 2 else "paper/generated/numbers.tex"
    out = Path(sys.argv[3] if len(sys.argv) > 3 else "index.html")
    macros = {} if numbers == "-" else load_macros(Path(numbers))
    data = json.loads(content.read_text())
    out.write_text(render(data if numbers == "-" else walk(data, macros)))
    print("wrote", out)


if __name__ == "__main__":
    main()
