#!/usr/bin/env python3
"""Compare each module's declared Prerequisites line with the graph.

The proposed list is the module's *direct* predecessors: every module supplying
at least one concept this module uses directly. Existing declarations are unioned
in, never dropped — the author's intent wins. Entries are ordered by Canvas
position. Prints a plan; --apply rewrites the Prerequisites line in the content
repo (not in clean/, which is generated).

Usage: prereqs.py [--dir WORKDIR] [--apply]
"""
import collections, csv, re, sys
import courselib

work, cfg = courselib.load()
apply_ = "--apply" in sys.argv
g = work / "graph"
C = {c["id"]: c for c in csv.DictReader(open(g / "concepts.tsv"), delimiter="\t")}
E = list(csv.DictReader(open(g / "edges.tsv"), delimiter="\t"))
mods = courselib.modules(work)
pos = {m["id"]: i for i, m in enumerate(mods)}

direct = collections.defaultdict(set)
why = collections.defaultdict(list)
for e in E:
    a, b = C[e["from"]]["module"], C[e["to"]]["module"]
    if a == b or a not in pos or b not in pos:
        continue
    direct[b].add(a)
    why[(a, b)].append((C[e["from"]]["label"], C[e["to"]]["label"]))

declared, plan, changes = {}, {}, []
for m in mods:
    src = courselib.source_file(cfg, m["id"])
    if not src:
        continue
    declared[m["id"]] = courselib.prereq_ids(cfg, src.read_text())
    plan[m["id"]] = sorted(set(direct.get(m["id"], set())) | set(declared[m["id"]]),
                           key=lambda x: pos.get(x, 1 << 30))

print(f"{'mod':6} {'declared':22} {'proposed':34} added")
print("-" * 84)
for m in mods:
    i = m["id"]
    if i not in plan:
        continue
    added = [x for x in plan[i] if x not in declared[i]]
    if added:
        changes.append(i)
    print(f"{i:6} {','.join(declared[i]) or '—':22} {','.join(plan[i]) or '—':34} "
          f"{'+' + ','.join(added) if added else ''}")

print("\njustification for each addition:")
for m in mods:
    i = m["id"]
    for p in plan.get(i, []):
        if p not in declared[i]:
            ex = why[(p, i)][:2]
            more = f" (+{len(why[(p, i)]) - 2} more)" if len(why[(p, i)]) > 2 else ""
            print(f"  {i} <- {p}: " +
                  "; ".join(f'"{a}" needed by "{b}"' for a, b in ex) + more)

if not apply_:
    print(f"\n{len(changes)} module(s) would change. Re-run with --apply to write them.")
    sys.exit(0)

written = 0
for m in mods:
    i = m["id"]
    src = courselib.source_file(cfg, i)
    if not src:
        continue
    lines = src.read_text().split("\n")
    idx = [n for n, l in enumerate(lines) if re.match(cfg["prereq_line"], l)]
    if len(idx) != 1:
        print(f"  {i}: expected exactly one Prerequisites line, found {len(idx)} — skipped",
              file=sys.stderr)
        continue
    new = "-   Prerequisites:" + ("" if not plan[i] else
                                  " " + ", ".join(f"[{x}](../{x})" for x in plan[i]))
    if lines[idx[0]] != new:
        lines[idx[0]] = new
        src.write_text("\n".join(lines))
        written += 1
print(f"\nrewrote {written} file(s) under {cfg['repo']}")
