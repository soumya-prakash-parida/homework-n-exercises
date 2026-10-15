#!/usr/bin/env python3
"""Regenerate index.html (the GitHub Pages home page) from the PDFs in this repo.

Run from anywhere:

    python3 scripts/build_index.py

It looks for every folder named PDF that sits in this layout:

    <Grade>/<Subject>/<Format>/PDF/<name>.pdf

When a matching JSON/<name>.json exists next to it, the JSON's "subject" and
passage titles are used to label the worksheet set. Nothing is copied or moved:
the page links straight to the PDFs where they already live, so run this again
whenever PDFs are added, renamed or removed, then commit index.html.
"""
import html
import json
import os
import re
from datetime import date
from urllib.parse import quote

try:
    from pypdf import PdfReader
except ImportError:  # page counts are a nice-to-have, not required
    PdfReader = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_URL = "https://github.com/soumya-prakash-parida/homework-n-exercises"

SMALL_WORDS = {"a", "an", "and", "of", "the", "in", "through", "to", "for", "on"}
SPECIAL_WORDS = {"ai": "AI", "earths": "Earth's"}


def natural_key(text):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", text)]


def prettify(stem):
    """'earths-natural-phenomena' -> "Earth's Natural Phenomena"."""
    parts = []
    for chunk in stem.split("_"):
        words = []
        for i, w in enumerate(chunk.split("-")):
            if w in SPECIAL_WORDS:
                words.append(SPECIAL_WORDS[w])
            elif w in SMALL_WORDS and i > 0:
                words.append(w)
            else:
                words.append(w[:1].upper() + w[1:])
        parts.append(" ".join(words))
    return ": ".join(parts)


def collect():
    """Return {grade: {subject: {format: {"sheets": [...], "keys": [...]}}}}."""
    tree = {}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        if os.path.basename(dirpath) != "PDF":
            continue
        rel = os.path.relpath(dirpath, ROOT).split(os.sep)
        if len(rel) != 4:
            continue
        grade, subject, fmt, _ = rel
        for fn in sorted(filenames):
            if not fn.lower().endswith(".pdf"):
                continue
            stem = os.path.splitext(fn)[0]
            pdf_path = os.path.join(dirpath, fn)
            is_key = "answer-key" in stem

            number, title, passages = None, prettify(stem), []
            json_path = os.path.join(ROOT, grade, subject, fmt, "JSON", stem + ".json")
            if os.path.exists(json_path) and not is_key:
                with open(json_path, encoding="utf-8") as f:
                    data = json.load(f)
                passages = [t["title"] for t in data.get("topics", []) if t.get("title")]
                m = re.match(r"^Topic\s+(\d+):\s*(.+)$", data.get("subject") or "")
                if m:
                    number, title = int(m.group(1)), m.group(2).strip()

            pages = None
            if PdfReader is not None:
                try:
                    pages = len(PdfReader(pdf_path).pages)
                except Exception:
                    pages = None

            entry = {
                "title": title,
                "number": number,
                "passages": passages,
                "pages": pages,
                "kb": max(1, round(os.path.getsize(pdf_path) / 1024)),
                "href": quote("/".join(rel + [fn]), safe="/"),
                "is_key": is_key,
            }
            bucket = tree.setdefault(grade, {}).setdefault(subject, {}).setdefault(
                fmt, {"sheets": [], "keys": []}
            )
            bucket["keys" if is_key else "sheets"].append(entry)

    for subjects in tree.values():
        for formats in subjects.values():
            for bucket in formats.values():
                bucket["sheets"].sort(
                    key=lambda e: (e["number"] is None, e["number"] or 0, natural_key(e["title"]))
                )
                bucket["keys"].sort(key=lambda e: natural_key(e["title"]))
    return tree


def esc(text):
    return html.escape(text, quote=True)


def render_row(e):
    num = ""
    if e["number"] is not None:
        num = f'<span class="num"><span class="sr">Topic </span>{e["number"]}</span>'
    inside = ""
    if e["passages"]:
        spans = "".join(f"<span>{esc(p)}</span>" for p in e["passages"])
        inside = f'<p class="inside">Passages: {spans}</p>'
    bits = []
    if e["pages"]:
        bits.append(f'{e["pages"]} pages')
    bits.append(f'{e["kb"]} KB')
    meta = ", ".join(bits)
    t = esc(e["title"])
    return (
        '<li class="row">'
        f"{num}"
        f'<div class="main"><a class="title" href="{e["href"]}">{t}</a>{inside}</div>'
        f'<div class="actions"><span class="meta">{meta}</span>'
        f'<a class="get" href="{e["href"]}" download>Download'
        f'<span class="sr"> {t} (PDF)</span></a></div>'
        "</li>"
    )


def plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def render_body(tree):
    out = []
    for grade in sorted(tree, key=natural_key):
        out.append(f'<h2 class="grade">{esc(grade)}</h2>')
        for subject in sorted(tree[grade], key=natural_key):
            out.append(f'<h3 class="subject">{esc(subject)}</h3>')
            for fmt in sorted(tree[grade][subject], key=natural_key):
                bucket = tree[grade][subject][fmt]
                label = esc(fmt.replace(" - ", ": "))
                out.append(
                    '<section class="format">'
                    f'<div class="format-head"><h4>{label}</h4>'
                    f'<span class="count">{plural(len(bucket["sheets"]), "worksheet")}</span></div>'
                )
                if bucket["sheets"]:
                    out.append('<ul class="rows">' + "".join(render_row(e) for e in bucket["sheets"]) + "</ul>")
                if bucket["keys"]:
                    out.append('<h5 class="keys">Answer keys</h5>')
                    out.append('<ul class="rows">' + "".join(render_row(e) for e in bucket["keys"]) + "</ul>")
                out.append("</section>")
    return "\n".join(out)


CSS = """
:root {
  --desk: #E4EAF4;
  --paper: #F8FAFE;
  --rule: #D3E1F3;
  --ink: #16213E;
  --graphite: #566075;
  --margin: #D94661;
  --highlight: #FFE066;
  --gutter: 76px;
  --gap: 28px;
  --numgap: 14px;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--desk);
  color: var(--ink);
  font: 17px/1.55 "Atkinson Hyperlegible", system-ui, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
.sheet {
  position: relative;
  max-width: 900px;
  margin: 32px auto;
  padding: 56px 40px 40px calc(var(--gutter) + var(--gap));
  background: var(--paper);
  box-shadow: 0 14px 40px -22px rgba(22, 33, 62, 0.35);
}
.sheet::before {
  content: "";
  position: absolute;
  top: 0;
  bottom: 0;
  left: var(--gutter);
  width: 2px;
  background: var(--margin);
  opacity: 0.75;
}
h1 {
  margin: 0 0 12px;
  font-size: clamp(2.1rem, 5.5vw, 3.1rem);
  line-height: 1.08;
  letter-spacing: -0.01em;
}
.lede { margin: 0 0 8px; max-width: 54ch; color: var(--graphite); }
h2.grade { margin: 44px 0 0; font-size: 1.9rem; line-height: 1.2; }
h3.subject { margin: 2px 0 0; font-size: 1.1rem; color: var(--graphite); }
.format { margin-top: 30px; }
.format-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 16px;
  padding-bottom: 6px;
  border-bottom: 2px solid var(--ink);
}
.format-head h4 { margin: 0; font-size: 1.15rem; }
.count { color: var(--graphite); font-size: 0.9rem; white-space: nowrap; }
h5.keys { margin: 26px 0 0; padding-bottom: 6px; font-size: 1rem; color: var(--graphite); border-bottom: 2px solid var(--ink); }
.rows { margin: 0; padding: 0; list-style: none; }
.row {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px 20px;
  padding: 14px 0;
  border-bottom: 1px solid var(--rule);
}
.num {
  position: absolute;
  top: 14px;
  right: calc(100% + var(--gap) + var(--numgap));
  font-weight: 700;
  color: var(--graphite);
  font-variant-numeric: tabular-nums;
}
.title {
  font-weight: 700;
  font-size: 1.1rem;
  color: var(--ink);
  text-decoration: underline;
  text-decoration-color: var(--rule);
  text-decoration-thickness: 2px;
  text-underline-offset: 4px;
}
.title:hover { text-decoration-color: var(--margin); }
.inside { margin: 4px 0 0; color: var(--graphite); font-size: 0.9rem; line-height: 1.5; }
.inside span + span::before { content: "/"; margin: 0 0.55em; color: var(--margin); }
.actions { display: flex; align-items: center; gap: 16px; white-space: nowrap; }
.meta { color: var(--graphite); font-size: 0.9rem; }
.get {
  padding: 6px 16px;
  border: 2px solid var(--ink);
  border-radius: 6px;
  color: var(--ink);
  font-weight: 700;
  text-decoration: none;
}
.get:hover { background: var(--highlight); }
a:focus-visible { outline: 3px solid var(--ink); outline-offset: 3px; border-radius: 4px; }
.get:focus-visible { background: var(--highlight); }
.foot { margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--rule); color: var(--graphite); font-size: 0.9rem; }
.foot a { color: var(--ink); }
.sr {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
@media (max-width: 640px) {
  :root { --gutter: 40px; --gap: 14px; --numgap: 8px; }
  body { font-size: 16px; }
  .sheet { margin: 0; padding: 36px 16px 32px calc(var(--gutter) + var(--gap)); box-shadow: none; }
  .row { grid-template-columns: minmax(0, 1fr); }
  .actions { justify-content: space-between; }
}
"""


def build():
    tree = collect()
    total = sum(
        len(b["sheets"]) + len(b["keys"])
        for subjects in tree.values()
        for formats in subjects.values()
        for b in formats.values()
    )
    updated = date.today().strftime("%B %-d, %Y")
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Homework and Exercises</title>
<meta name="description" content="Printable practice worksheets with answer keys. Open a PDF to read it on screen, or download it to print.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<main class="sheet">
<h1>Homework and Exercises</h1>
<p class="lede">Printable practice sheets for home study. Open a worksheet to read it on screen, or choose Download to save the PDF and print it.</p>
{render_body(tree)}
<p class="foot">Last updated {updated}. {plural(total, "PDF")} on this page. <a href="{REPO_URL}">Source files on GitHub</a>.</p>
</main>
</body>
</html>
"""
    out_path = os.path.join(ROOT, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Wrote {out_path} listing {total} PDF(s).")


if __name__ == "__main__":
    build()
