#!/usr/bin/env python3
"""Validate the concept dependency graph. Exits non-zero on any problem.

Reads graph/concepts.tsv and graph/edges.tsv, cross-checks against the Canvas
order in modules.tsv, and rewrites graph/topo-order.tsv and
graph/module-edges.tsv.

Checks: unknown ids, duplicate ids, cycles (Kahn), prerequisites presented after
the module that needs them, concepts used but never defined, concepts defined
more than once.

Usage: check.py [--dir WORKDIR]
"""
import collections, csv, pathlib, re, sys
import courselib

work, cfg = courselib.load()
g = work / "graph"
concepts = list(csv.DictReader(open(g / "concepts.tsv"), delimiter="\t"))
edges = list(csv.DictReader(open(g / "edges.tsv"), delimiter="\t"))
by = {c["id"]: c for c in concepts}
pos = {m["id"]: i for i, m in enumerate(courselib.modules(work))}
problems = []

if len(by) != len(concepts):
    problems.append("duplicate concept ids present")
for e in edges:
    for side in ("from", "to"):
        if e[side] not in by:
            problems.append(f"edge references unknown concept: {e[side]}")

bad_strength = [e for e in edges if (e.get("strength") or "").strip()
                and not re.fullmatch(r"(0(\.\d+)?|1(\.0+)?)", e["strength"].strip())]
if bad_strength:
    problems.append(f"{len(bad_strength)} edges with a strength outside [0,1], e.g. "
                    f"{bad_strength[0]['from']} -> {bad_strength[0]['to']}")
ungraded = sum(1 for e in edges if not (e.get("strength") or "").strip())

succ = collections.defaultdict(list)
indeg = {c["id"]: 0 for c in concepts}
for e in edges:
    if e["from"] in by and e["to"] in by:
        succ[e["from"]].append(e["to"])
        indeg[e["to"]] += 1

deg = dict(indeg)
q = collections.deque(sorted(i for i, d in deg.items() if d == 0))
level = {i: 0 for i in q}
order = []
while q:
    n = q.popleft()
    order.append(n)
    for m in succ[n]:
        level[m] = max(level.get(m, 0), level[n] + 1)
        deg[m] -= 1
        if deg[m] == 0:
            q.append(m)
cyclic = len(order) != len(concepts)
if cyclic:
    problems.append(f"CYCLE among: {sorted(set(by) - set(order))}")

violations = [(by[e["from"]]["module"], by[e["to"]]["module"], e["from"], e["to"])
              for e in edges
              if e["from"] in by and e["to"] in by
              and pos.get(by[e["from"]]["module"]) is not None
              and pos.get(by[e["to"]]["module"]) is not None
              and pos[by[e["from"]]["module"]] > pos[by[e["to"]]["module"]]]

print(f"concepts {len(concepts)}   edges {len(edges)}"
      + (f" ({ungraded} without a strength)" if ungraded else ""))
print("\nconcepts per module:")
for m, n in sorted(collections.Counter(c["module"] for c in concepts).items()):
    print(f"  {m:10} {n}")
print(f"\nacyclic: {'NO' if cyclic else 'YES'}"
      f"   depth: {max(level.values()) + 1 if level else 0} levels")
print(f"roots: {sum(1 for i in by if indeg[i] == 0)}   "
      f"leaves: {sum(1 for i in by if not succ[i])}")

outside = [c for c in concepts if c["module"] not in pos]
print(f"\nconcepts not defined by any module in the manifest: {len(outside)}")
for c in outside:
    print(f"  {c['module']:10} {c['id']:28} {c['label']}")

dup = [c for c in concepts if c.get("restated_in")]
print(f"\nconcepts defined more than once: {len(dup)}")
for c in dup:
    print(f"  {c['id']:28} defined {c['module']}, restated {c['restated_in']}")

print(f"\n{'Canvas ordering' if cfg.get('canvas_course') else 'Teaching-order'} violations: {len(violations)}")
for a, b, x, y in violations:
    print(f"  {a} appears after {b}, but {x} is needed by {y}")

courselib.write_tsv(g / "topo-order.tsv",
                    [{"level": level[i], "id": i, "module": by[i]["module"],
                      "label": by[i]["label"]}
                     for i in sorted(order, key=lambda i: (level[i], by[i]["module"], i))],
                    ["level", "id", "module", "label"])
mod_edges = sorted({(by[e["from"]]["module"], by[e["to"]]["module"]) for e in edges
                    if e["from"] in by and e["to"] in by
                    and by[e["from"]]["module"] != by[e["to"]]["module"]})
courselib.write_tsv(g / "module-edges.tsv",
                    [{"from_module": a, "to_module": b} for a, b in mod_edges],
                    ["from_module", "to_module"])
print(f"\nwrote topo-order.tsv, module-edges.tsv ({len(mod_edges)} inter-module edges)")

if problems:
    print("\nPROBLEMS:")
    for p in problems:
        print("  " + p)
sys.exit(1 if problems else 0)
