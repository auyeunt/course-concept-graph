#!/usr/bin/env python3
"""Concept extraction (Step 5) as packets, one module at a time in teaching order.

  extract.py prepare [--dir W] [--only NNNN]
      writes graph/extract/packets/NNNN.md for the next module in teaching order
      that has text but no concepts yet (or for --only NNNN). The packet holds
      the instructions (prompts/extract.md), the strength rubric, every concept
      already in the graph grouped by module in teaching order, and the module
      text with line numbers. A module counts as done once it has concepts or
      a reply has been applied with --write. Give it to a reader (a model, or a person) and
      save the reply, as-is or as a bare table, to graph/extract/NNNN.tsv (or
      .txt).

  extract.py apply [--dir W] NNNN [--write] [--replace]
      checks the reply and, with --write, adds it to the graph:
        concept rows   -> concepts.tsv (module NNNN)
        prior rows     -> concepts.tsv (module PRIOR), unless the id exists
        edge rows      -> edges.tsv, with strength and an "extract" note
        restated rows  -> the module is added to that concept's restated_in
        undefined rows -> listed in graph/extract/undefined.tsv for the author
      A row is rejected (and reported) when its quote is not in the module
      text, an id is malformed, reused or unknown, an edge's target is not a
      concept of this module, its source is defined in a later module, its
      strength is not in (0, 1], or it would close a cycle. Without --write
      nothing changes. --replace first removes the module's existing concepts
      and the edges into them (for redoing a module).

Because each packet lists the concepts already in the graph, modules must be
applied in teaching order: prepare, read, apply --write, then the next one.
After the last module, run check.py, then the Step 5b audit (whose first job is
to recover the edges this pass missed) and edge_audit.py forward.
"""
import collections, csv, pathlib, re, sys
import courselib
from edge_audit import norm, module_text, teaching_order, load_graph

EXT_COLS = ["kind", "id", "label", "from", "strength", "line", "quote", "note"]
ID = re.compile(r"[a-z][a-z0-9]*(\.[a-z0-9]+(-[a-z0-9]+)*)+")


def realign(fields):
    """A row as a dict of EXT_COLS. Models sometimes leave out `-` fields (an
    edge row without its empty label, say), which shifts everything after it.
    The line number is the anchor: quote and note follow it, and an edge's
    strength and source come just before it."""
    f = fields + [""] * (len(EXT_COLS) - len(fields))
    if len(fields) == len(EXT_COLS) and f[5].isdigit():
        return dict(zip(EXT_COLS, f))
    j = next((i for i in range(2, len(fields) - 1) if fields[i].isdigit()), None)
    if j is None:
        return dict(zip(EXT_COLS, f))
    r = {k: "-" for k in EXT_COLS}
    r.update(kind=fields[0], id=fields[1], line=fields[j], quote=fields[j + 1],
             note=fields[j + 2] if j + 2 < len(fields) else "")
    before = fields[2:j]
    if r["kind"] == "edge":
        if before:
            r["strength"] = before[-1]
        if len(before) >= 2:
            r["from"] = before[-2]
        if len(before) >= 3:
            r["label"] = before[0]
    elif before:
        r["label"] = before[0]
    return r


def done_modules(concepts):
    return {c["module"] for c in concepts}


def prepare(work, cfg, only):
    concepts, _ = load_graph(work) if (work / "graph" / "concepts.tsv").exists() else ([], [])
    order = teaching_order(work, concepts)
    titles = {m["id"]: m["title"] for m in courselib.modules(work)}
    have = done_modules(concepts)
    if only:
        mid = only
    else:
        marks = work / "graph" / "extract"
        mid = next((m for m in order[1:] if m not in have
                    and not (marks / f"{m}.done").exists()
                    and module_text(work, cfg, m) is not None), None)
        if mid is None:
            print("every module with text already has concepts; nothing to prepare")
            return
    text = module_text(work, cfg, mid)
    if text is None:
        sys.exit(f"no text for module {mid}")
    pos = {m: i for i, m in enumerate(order)}
    out = work / "graph" / "extract"
    (out / "packets").mkdir(parents=True, exist_ok=True)
    dest = out / f"{mid}.tsv"
    L = [f"# Concept extraction packet: module {mid}, {titles.get(mid, '')}\n",
         courselib.prompt("extract", rubric=courselib.prompt("rubric"), out=dest),
         "\n## Concepts already in the graph, by module in teaching order\n"]
    shown = 0
    for m in order:
        if m != "PRIOR" and pos.get(m, 0) >= pos.get(mid, 0):
            continue
        group = [c for c in concepts if c["module"] == m]
        if not group:
            continue
        name = ("prior knowledge (from outside the course)" if m == "PRIOR"
                else f"module {m} {titles.get(m, '')}")
        L.append(f"\n### {name}\n")
        L += [f"- `{c['id']}`: {c['label']}. {c['definition']}" for c in group]
        shown += len(group)
    if not shown:
        L.append("None yet: this is the first module. Every concept you need from "
                 "outside this module is a `prior` row.")
    L.append(f"\n## Module {mid} text, with line numbers\n")
    L += [f"{i:4} | {line}" for i, line in enumerate(text.split("\n"), 1)]
    (out / "packets" / f"{mid}.md").write_text("\n".join(L) + "\n")
    print(f"wrote {out / 'packets' / f'{mid}.md'} ({shown} concepts listed); "
          f"save the reply to {dest}")


def apply(work, cfg, mid, write, replace):
    g = work / "graph"
    cpath, epath = g / "concepts.tsv", g / "edges.tsv"
    concepts = courselib.tsv(cpath, [])
    edges = courselib.tsv(epath, [])
    order = teaching_order(work, concepts + [{"module": mid}])
    pos = {m: i for i, m in enumerate(order)}
    f = next((p for p in (g / "extract" / f"{mid}.tsv", g / "extract" / f"{mid}.txt")
              if p.exists()), None)
    if f is None:
        sys.exit(f"no reply at graph/extract/{mid}.tsv or .txt")
    rows = [realign(x) for x in courselib.read_table(f, "kind", raw=True)]
    text = module_text(work, cfg, mid) or ""
    lines = text.split("\n")
    whole = norm(" ".join(lines))

    if any(c["module"] == mid for c in concepts):
        if not replace:
            sys.exit(f"module {mid} already has concepts; use --replace to redo it")
        gone = {c["id"] for c in concepts if c["module"] == mid}
        concepts = [c for c in concepts if c["module"] != mid]
        edges = [e for e in edges if e["to"] not in gone and e["from"] not in gone]
    by = {c["id"]: c for c in concepts}

    def quote_ok(r):
        q = norm(r.get("quote", "")).strip('"')
        return bool(q) and q in whole

    rejected, undefined = [], []
    new, prior, restated, new_edges = [], [], [], []
    for r in rows:
        r = {k: (r.get(k) or "").strip() for k in EXT_COLS}
        k, i = r["kind"], r["id"]
        why = None
        if k in ("concept", "prior", "edge", "restated") and not quote_ok(r):
            why = "quote not found in the module text"
        elif k == "concept":
            if not ID.fullmatch(i) or i.startswith("prior."):
                why = "malformed id"
            elif i in by or i in {c["id"] for c in new}:
                why = "id already in use"
            else:
                new.append({"id": i, "module": mid, "label": r["label"],
                            "definition": r["note"], "restated_in": ""})
        elif k == "prior":
            if not ID.fullmatch(i) or not i.startswith("prior."):
                why = "prior ids start with prior."
            elif i in by and by[i]["module"] != "PRIOR":
                why = f"{i} is a course concept, not prior knowledge"
            elif i not in by and i not in {c["id"] for c in prior}:
                prior.append({"id": i, "module": "PRIOR", "label": r["label"],
                              "definition": r["note"], "restated_in": ""})
        elif k == "restated":
            if i not in by:
                why = "unknown id"
            else:
                restated.append(i)
        elif k == "undefined":
            undefined.append({"module": mid, "term": r["label"], "line": r["line"],
                              "quote": r["quote"], "note": r["note"]})
        elif k == "edge":
            new_edges.append(r)
        else:
            why = f"unknown kind {k!r}"
        if why:
            rejected.append((r, why))

    ids_here = [c["id"] for c in new]
    known = set(by) | set(ids_here) | {c["id"] for c in prior}
    succ = collections.defaultdict(set)
    for e in edges:
        succ[e["from"]].add(e["to"])

    def reaches(a, b):
        seen, stack = set(), [a]
        while stack:
            n = stack.pop()
            if n == b:
                return True
            if n not in seen:
                seen.add(n)
                stack.extend(succ[n])
        return False

    added = []
    for r in new_edges:
        a, b = r["from"], r["id"]
        why = None
        try:
            s = float(r["strength"])
        except ValueError:
            s = -1
        if b not in ids_here:
            why = f"target {b} is not a concept defined in module {mid}"
        elif a not in known:
            why = f"unknown source {a}"
        elif a in by and pos.get(by[a]["module"], 0) > pos.get(mid, 0):
            why = f"{a} is taught later, in {by[a]['module']}"
        elif not 0 < s <= 1:
            why = "strength must be in (0, 1]"
        elif a == b or reaches(b, a):
            why = "would close a cycle"
        elif any(e["from"] == a and e["to"] == b for e in added):
            why = "duplicate"
        if why:
            rejected.append((r, why))
            continue
        succ[a].add(b)
        n = r["note"].replace("\t", " ")
        added.append({"from": a, "to": b, "strength": f"{s:g}",
                      "note": f"extract {mid}:{r['line']}: {n}"})

    kinds = collections.Counter(r.get("kind", "?") for r in rows)
    print(f"{f.name}: " + ", ".join(f"{k} {v}" for k, v in kinds.items()))
    print(f"accepted: {len(new)} concepts, {len(prior)} new prior, {len(added)} edges, "
          f"{len(restated)} restated, {len(undefined)} undefined; rejected {len(rejected)}")
    for r, why in rejected:
        print(f"  rejected {r.get('kind')} {r.get('from') or ''} {r.get('id')}: {why}")
    roots = [i for i in ids_here if not any(e["to"] == i for e in added)]
    if roots:
        print(f"  no prerequisites (check these): {', '.join(roots)}")
    if not write:
        print("dry run; --write to add to the graph")
        return

    for c in concepts:
        if c["id"] in restated:
            have = [x for x in (c.get("restated_in") or "").split(",") if x.strip()]
            if mid not in have:
                c["restated_in"] = ",".join(have + [mid])
    ccols = ["id", "module", "label", "definition", "restated_in"]
    # leave existing rows where they are: new prior rows go after the last PRIOR
    # row, the module's concepts at the end
    cut = max((n + 1 for n, c in enumerate(concepts) if c["module"] == "PRIOR"), default=0)
    write_rows(cpath, concepts[:cut] + prior + concepts[cut:] + new, ccols)
    write_rows(epath, edges + added, ["from", "to", "strength", "note"])
    if undefined:
        upath = g / "extract" / "undefined.tsv"
        old = [u for u in courselib.tsv(upath, []) if u["module"] != mid]
        courselib.write_tsv(upath, old + undefined, ["module", "term", "line", "quote", "note"])
    (g / "extract" / f"{mid}.done").write_text("")  # applied, even if it defined nothing
    print(f"wrote {cpath.name} and {epath.name}; next: extract.py prepare")


def write_rows(path, rows, cols):
    """Write a TSV keeping the file's existing line endings (CRLF or LF) and
    without csv quoting, so hand edits and diffs stay clean."""
    eol = "\n"
    if path.exists() and "\r\n" in open(path, newline="").read(4096):
        eol = "\r\n"
    def cell(v):
        v = (v or "").replace("\t", " ")
        return "\u201c" + v[1:] if v.startswith('"') else v  # csv readers strip a leading "
    out = ["\t".join(cols)] + ["\t".join(cell(r.get(c)) for c in cols) for r in rows]
    path.write_text(eol.join(out) + eol, newline="")


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args and not args[0].startswith("-") else ""
    rest = [a for a in args[1:]]
    work, cfg = courselib.load([a for a in args if a != cmd])
    if cmd == "prepare":
        prepare(work, cfg, args[args.index("--only") + 1] if "--only" in args else None)
    elif cmd == "apply":
        mids = [a for a in rest if re.fullmatch(cfg["id_pattern"], a)]
        if len(mids) != 1:
            sys.exit("usage: extract.py apply NNNN [--write] [--replace]")
        apply(work, cfg, mids[0], "--write" in args, "--replace" in args)
    else:
        sys.exit(__doc__)
