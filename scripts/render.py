#!/usr/bin/env python3
"""Render the concept and module graphs to theme-adaptive SVG (needs graphviz).

Run check.py first — it regenerates module-edges.tsv.
Usage: render.py [--dir WORKDIR]
"""
import collections, csv, re, subprocess
import courselib

work, cfg = courselib.load()
g = work / "graph"
C = list(csv.DictReader(open(g / "concepts.tsv"), delimiter="\t"))
E = list(csv.DictReader(open(g / "edges.tsv"), delimiter="\t"))
ME = list(csv.DictReader(open(g / "module-edges.tsv"), delimiter="\t"))
mods = courselib.modules(work)
order = [m["id"] for m in mods]
meta = {m["id"]: m for m in mods}
PALETTE = ["#2f6f4f", "#3a5f8f", "#6f3a6f", "#7a5a2f", "#3f6f6f", "#7a8079"]
colour = {name: PALETTE[i % len(PALETTE)] for i, name in
          enumerate(dict.fromkeys(m["canvas_module"] for m in mods))}
PENDING = "#a8791f"
q = lambda s: s.replace('"', r'\"')

groups = collections.defaultdict(list)
for c in C:
    groups[c["module"]].append(c)
with open(g / "concepts.dot", "w") as f:
    f.write('digraph c {\n  rankdir=LR; nodesep=0.18; ranksep=0.7;\n'
            '  graph [fontname="Helvetica" fontsize=13];\n'
            '  node [shape=box style=rounded fontname="Helvetica" fontsize=10'
            ' height=0.3 margin="0.12,0.05"];\n  edge [arrowsize=0.6];\n')
    for m in order + sorted(set(groups) - set(order)):
        if m not in groups:
            continue
        f.write(f'  subgraph "cluster_{m}" {{\n'
                f'    label="{m}  {q(meta[m]["title"]) if m in meta else "external"}";\n'
                f'    style=rounded;\n')
        for c in groups[m]:
            lab = q(c["label"])
            f.write(f'    "{c["id"]}" [label="{lab if len(lab) <= 30 else lab[:28] + "..."}"];\n')
        f.write("  }\n")
    for e in E:
        try:  # line weight follows edge strength; weak edges are dashed
            st = float(e.get("strength") or "")
            attr = f' [penwidth={0.4 + 2.2 * st:.2f}{" style=dashed" if st < 0.3 else ""}]'
        except ValueError:
            attr = ""
        f.write(f'  "{e["from"]}" -> "{e["to"]}"{attr};\n')
    f.write("}\n")

with open(g / "modules.dot", "w") as f:
    f.write('digraph m {\n  rankdir=LR; splines=spline; nodesep=0.35; ranksep=0.9;\n'
            '  node [shape=box style="rounded,filled" fontname="Helvetica"'
            ' fontsize=11 penwidth=0];\n  edge [arrowsize=0.7];\n')
    for m in mods:
        lab = q(m["title"] if len(m["title"]) < 34 else m["title"][:31] + "...")
        if m["status"] == "published":
            f.write(f'  "{m["id"]}" [label="{m["id"]}\\n{lab}"'
                    f' fillcolor="{colour[m["canvas_module"]]}" fontcolor=white];\n')
        else:
            f.write(f'  "{m["id"]}" [label="{m["id"]}\\n{lab}\\n({q(m["status"])})"'
                    f' fillcolor="#f0efe6" fontcolor="{PENDING}" style="rounded,filled"'
                    f' penwidth=1.6 color="{PENDING}"];\n')
    for e in ME:
        if e["from_module"] in meta and e["to_module"] in meta:
            f.write(f'  "{e["from_module"]}" -> "{e["to_module"]}";\n')
    f.write("}\n")


def themeable(t):
    for pat in (r'<\?xml[^>]*\?>\s*', r'<!DOCTYPE[^>]*>\s*'):
        t = re.sub(pat, "", t)
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    t = re.sub(r'<polygon fill="white"[^/]*/>', "", t)
    t = t.replace('fill="black"', 'fill="currentColor"')
    t = t.replace('stroke="black"', 'stroke="currentColor"')
    t = re.sub(r'(<svg[^>]*?)\swidth="[^"]*"', r"\1", t, count=1)
    return re.sub(r'(<svg[^>]*?)\sheight="[^"]*"', r"\1", t, count=1).strip()


for stem in ("concepts", "modules"):
    subprocess.run(["dot", "-Tsvg", str(g / f"{stem}.dot"), "-o", str(g / f"{stem}.svg")],
                   check=True)
    (g / f"{stem}.themed.svg").write_text(themeable((g / f"{stem}.svg").read_text()))
    print(f"graph/{stem}.themed.svg")
