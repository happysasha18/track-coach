#!/usr/bin/env python3
"""Render SPEC.md to a styled, self-contained, offline HTML (no CDN) for a calm read.
Handles the constructs this spec actually uses: ATX headings, blockquotes, tables,
ordered/unordered (nested) lists, hr, **bold**, `code`, and ⟨DECIDE⟩ highlight.
Usage: python3 scripts/render_spec.py docs/SPEC.md /tmp/spec.html [#anchor-substr]
"""
import html
import re
import sys


def inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r'<span class="wiki">\1</span>', s)
    s = re.sub(r"(⟨DECIDE[^⟩]*⟩)", r'<span class="decide">\1</span>', s)
    s = re.sub(r"\b(D-INV-\d+|CR-\d+\w*|G\d+|F\d+|INV-\d+)\b", r'<span class="id">\1</span>', s)
    return s


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def render(md: str) -> str:
    lines = md.split("\n")
    out, i, n = [], 0, len(lines)

    def close_para(buf):
        if buf:
            out.append("<p>" + " ".join(buf) + "</p>")
            buf.clear()

    para: list[str] = []
    while i < n:
        line = lines[i]
        # table block
        if line.lstrip().startswith("|") and "|" in line:
            close_para(para)
            tbl = []
            while i < n and lines[i].lstrip().startswith("|"):
                tbl.append(lines[i]); i += 1
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in tbl]
            out.append("<table>")
            for ri, row in enumerate(rows):
                if ri == 1 and all(set(c) <= set("-: ") for c in row):
                    continue
                tag = "th" if ri == 0 else "td"
                out.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in row) + "</tr>")
            out.append("</table>")
            continue
        # heading
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            close_para(para)
            lvl = len(m.group(1)); txt = m.group(2)
            out.append(f'<h{lvl} id="{slug(txt)}">{inline(txt)}</h{lvl}>')
            i += 1; continue
        # hr
        if re.match(r"^---+\s*$", line):
            close_para(para); out.append("<hr>"); i += 1; continue
        # blockquote (collect run)
        if line.lstrip().startswith(">"):
            close_para(para)
            q = []
            while i < n and lines[i].lstrip().startswith(">"):
                q.append(re.sub(r"^\s*>\s?", "", lines[i])); i += 1
            out.append('<blockquote>' + render("\n".join(q)) + "</blockquote>")
            continue
        # list (collect run of -, *, or N.) with 2-space nesting
        if re.match(r"^(\s*)([-*]|\d+\.)\s+", line):
            close_para(para)
            out.append(render_list(lines, i_box := [i]))
            i = i_box[0]; continue
        # blank
        if not line.strip():
            close_para(para); i += 1; continue
        para.append(inline(line.strip())); i += 1
    close_para(para)
    return "\n".join(out)


def render_list(lines, i_box):
    i = i_box[0]; n = len(lines)
    base = len(re.match(r"^(\s*)", lines[i]).group(1))
    ordered = bool(re.match(r"^\s*\d+\.", lines[i]))
    items = []
    while i < n:
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
        if not m:
            if lines[i].strip() == "":
                # peek: continue list only if next non-blank is a same-or-deeper item
                j = i + 1
                while j < n and lines[j].strip() == "":
                    j += 1
                if j < n and re.match(r"^\s{%d,}([-*]|\d+\.)\s+" % base, lines[j]):
                    i = j; continue
            break
        indent = len(m.group(1))
        if indent < base:
            break
        if indent > base:
            sub = render_list(lines, sb := [i]); i = sb[0]
            if items:
                items[-1] = items[-1][:-5] + sub + "</li>"
            continue
        items.append("<li>" + inline(m.group(3)) + "</li>")
        i += 1
    i_box[0] = i
    tag = "ol" if ordered else "ul"
    return f"<{tag}>" + "".join(items) + f"</{tag}>"


def main():
    src, dst = sys.argv[1], sys.argv[2]
    anchor = sys.argv[3] if len(sys.argv) > 3 else ""
    md = open(src, encoding="utf-8").read()
    body = render(md)
    scroll = ""
    if anchor:
        scroll = (
            "<script>window.addEventListener('load',function(){"
            "var hs=document.querySelectorAll('h1,h2,h3,h4');"
            "for(var k=0;k<hs.length;k++){if(hs[k].textContent.indexOf(%r)>=0){"
            "hs[k].scrollIntoView();hs[k].classList.add('hit');break;}}});</script>" % anchor
        )
    page = f"""<!doctype html><html><head><meta charset="utf-8">
<title>track-coach SPEC</title><style>
:root{{--bg:#0e1116;--panel:#161b22;--fg:#c9d1d9;--mut:#8b949e;--acc:#58a6ff;--warn:#e3b341;--id:#7ee787;}}
*{{box-sizing:border-box}}
body{{background:var(--bg);color:var(--fg);font:15px/1.62 -apple-system,Segoe UI,Roboto,sans-serif;
max-width:920px;margin:0 auto;padding:40px 28px 120px}}
h1{{font-size:25px;border-bottom:1px solid #30363d;padding-bottom:.3em;line-height:1.3}}
h2{{font-size:21px;margin-top:1.8em;border-bottom:1px solid #21262d;padding-bottom:.25em;color:#e6edf3}}
h3{{font-size:17px;margin-top:1.5em;color:#e6edf3}}
h4{{font-size:15px;margin-top:1.2em;color:var(--mut);text-transform:none}}
.hit{{background:#1f6feb33;outline:2px solid var(--acc);border-radius:6px;padding:4px 8px}}
code{{background:#1f2630;color:#c9d1d9;padding:.12em .35em;border-radius:5px;font-size:.88em}}
strong{{color:#f0f6fc}}
blockquote{{border-left:3px solid #3b434b;background:var(--panel);margin:.8em 0;padding:.4em 16px;border-radius:0 8px 8px 0;color:#adbac7}}
table{{border-collapse:collapse;margin:1em 0;width:100%;font-size:.9em}}
th,td{{border:1px solid #30363d;padding:6px 10px;text-align:left;vertical-align:top}}
th{{background:#1c2330}}
hr{{border:0;border-top:1px solid #30363d;margin:1.6em 0}}
ul,ol{{padding-left:1.4em}} li{{margin:.18em 0}}
.decide{{color:#161b22;background:var(--warn);padding:.05em .4em;border-radius:5px;font-weight:600}}
.id{{color:var(--id);font-family:ui-monospace,monospace;font-size:.86em}}
.wiki{{color:var(--acc);font-style:italic}}
a{{color:var(--acc)}}
</style></head><body>{body}{scroll}</body></html>"""
    open(dst, "w", encoding="utf-8").write(page)
    print(dst)


if __name__ == "__main__":
    main()
