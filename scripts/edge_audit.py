#!/usr/bin/env python3
"""Second-reading audit for missing edges in the concept graph.

Extraction (Step 5) is done by a reader, and readers miss edges far more often
than they invent them. This script turns the recall check into a repeatable
procedure that does not depend on the subject: one packet per module for a
reviewer, then mechanical verification of whatever the reviewer reports.

  edge_audit.py prepare [--dir W] [--only 0352,0351]
      writes graph/audit/packets/NNNN.md, one per module that defines concepts.
      Each packet holds the instructions, the concepts the module defines with
      their current prerequisites, every other concept as a candidate
      prerequisite (with definitions, in teaching order), and the module text
      with line numbers. A reviewer reads one packet and writes
      graph/audit/findings/NNNN.tsv.

  edge_audit.py verify [--dir W]
      reads every findings file and writes graph/audit/candidates.tsv with a
      status per row:
        ok         quote found, edge new, no cycle, teaching order respected
        implied    as ok, but `from` already reaches `to` indirectly
        order      `from` is taught after `to`'s module, and the text does not
                   point to that module (a finding in itself)
        forward    a use or mention of a concept taught later, with a pointer to
                   the module that teaches it (an acknowledged forward reference)
        unmarked   a reviewer-reported forward mention with no such pointer
        cycle      adding it would create a cycle (needs a concept split)
        bad-quote  quote not found in the module text: reject or re-read
        duplicate  edge already exists
        unknown    an id that is not in concepts.tsv, or `to` not defined here
      module-only and missing-concept rows are carried through for a human.

  edge_audit.py forward [--dir W]
      mechanical scan for forward references: every place a module names a
      concept that a later module teaches. Terms come from the concept's label
      (the part outside parentheses, matched case-insensitively, plus an
      acronym in parentheses, matched exactly) or from an optional `terms`
      column in concepts.tsv (`|`-separated, overrides the label). Fenced code
      and the Prerequisites line are skipped. Writes graph/audit/forward.tsv,
      one row per concept, module and section, with `pointer` yes or no. See
      POINTERS below for what counts as a pointer.

  edge_audit.py grade-prepare [--dir W] [--only ...]
      writes graph/audit/grade-packets/NNNN.md: the strength rubric, every
      existing edge into the module's concepts (E refs), every verified `ok`
      candidate (C refs), and the module text. A grader writes
      graph/audit/grades/NNNN.tsv with a strength in [0,1] for each ref, plus
      any missing edges between two concepts of the same module (ref W).

  edge_audit.py grade-apply [--dir W] [--write]
      sets `strength` on existing edges, then adds C and W edges strongest
      first, skipping any edge whose source already reaches its target (implied:
      a path exists) at the moment it would be added. Edges that would close a
      cycle, or that run against teaching order, are never added: they go to
      graph/audit/alerts.md for the content developer, with module, line and
      quote, together with the cycle/order rows from verify, existing edges
      graded 0, and missing concepts. Writes graph/audit/edges.proposed.tsv;
      with --write it also replaces graph/edges.tsv. Run check.py afterwards.

  edge_audit.py prune [--dir W] [--write]
      removes edges graded 0, then edges implied by another path at least as
      strong (a path is as strong as its weakest edge), weakest first. Logs
      removals to graph/audit/removed.tsv. Dry run without --write.

POINTERS. A forward reference is acceptable when the reader is told where the
concept is taught: the later module's id appears (as a link or in plain text)
in the same section as the mention, or in the introduction of an enclosing
section (the text before its first subheading). A forward reference is not an
edge: it never enters edges.tsv. Unpointed ones are alerted; pointed ones are
listed for review and passed to notebooklm.py, so a tutor sends the student
ahead instead of stepping back through earlier concepts.

edges.tsv columns: from, to, strength, note. strength is a number in [0,1]
(see prompts/rubric.md); consumers choose their own threshold rather than the graph
deciding what counts.
"""
import collections, csv, pathlib, re, sys
import courselib

FIND_COLS = ["kind", "from", "to", "line", "quote", "why"]
CAND_COLS = ["status", "accept", "module", "kind", "from", "to", "line",
             "quote", "why", "detail"]



def load_graph(work):
    g = work / "graph"
    concepts = list(csv.DictReader(open(g / "concepts.tsv"), delimiter="\t"))
    edges = list(csv.DictReader(open(g / "edges.tsv"), delimiter="\t"))
    return concepts, edges


def module_text(work, cfg, mid):
    f = work / "clean" / f"{mid}.md"
    if not f.exists():
        f = courselib.source_file(cfg, mid)
    return open(f).read() if f else None


def teaching_order(work, concepts):
    """Module ids in Canvas order; PRIOR first, off-manifest modules by number."""
    order = ["PRIOR"] + [m["id"] for m in courselib.modules(work)]
    extra = sorted({c["module"] for c in concepts} - set(order))
    return order + extra


def ancestors(edges):
    preds = collections.defaultdict(set)
    for e in edges:
        preds[e["to"]].add(e["from"])
    memo = {}

    def anc(n):
        if n not in memo:
            memo[n] = set()
            for p in preds[n]:
                memo[n] |= {p} | anc(p)
        return memo[n]
    return anc


def prepare(work, cfg, only):
    concepts, edges = load_graph(work)
    by = {c["id"]: c for c in concepts}
    order = teaching_order(work, concepts)
    pos = {m: i for i, m in enumerate(order)}
    preds = collections.defaultdict(list)
    for e in edges:
        preds[e["to"]].append(e["from"])
    titles = {m["id"]: m["title"] for m in courselib.modules(work)}
    out = work / "graph" / "audit" / "packets"
    out.mkdir(parents=True, exist_ok=True)
    (work / "graph" / "audit" / "findings").mkdir(exist_ok=True)
    made = []
    for mid in order:
        if mid == "PRIOR" or (only and mid not in only):
            continue
        defined = [c for c in concepts if c["module"] == mid]
        text = module_text(work, cfg, mid)
        if not defined or text is None:
            continue
        findings = work / "graph" / "audit" / "findings" / f"{mid}.tsv"
        L = [f"# Edge audit packet: module {mid}, {titles.get(mid, '')}\n",
             courselib.prompt("review", out=findings),
             f"\n## Concepts defined in module {mid} (the `to` side)\n"]
        for c in defined:
            cur = "; ".join(f"{p} ({by[p]['label']})" for p in preds[c["id"]]) or "none"
            L.append(f"- `{c['id']}`: {c['label']}. {c['definition']}\n"
                     f"  Current prerequisites: {cur}")
        L.append("\n## Candidate prerequisites from other modules (the `from` side can also be\n"
                 "any concept above, defined in this module), in teaching order\n")
        for m in order:
            group = [c for c in concepts if c["module"] == m and c["module"] != mid]
            if not group:
                continue
            tag = " (taught LATER than this module)" if pos[m] > pos[mid] else ""
            name = "prior knowledge" if m == "PRIOR" else f"module {m} {titles.get(m, '')}"
            L.append(f"\n### {name}{tag}\n")
            L += [f"- `{c['id']}`: {c['label']}. {c['definition']}" for c in group]
        L.append(f"\n## Module {mid} text, with line numbers\n")
        L += [f"{i:4} | {line}" for i, line in enumerate(text.split("\n"), 1)]
        (out / f"{mid}.md").write_text("\n".join(L) + "\n")
        made.append(mid)
    print(f"wrote {len(made)} packets to {out}: {' '.join(made)}")


def norm(s):
    """Compare quotes loosely: reviewers often add or drop math/emphasis delimiters."""
    return re.sub(r"\s+", " ", re.sub(r"[$*`_]", "", s)).strip()


def realign_finding(fields):
    """A findings row as a dict of FIND_COLS. Models sometimes drop a `-`
    field (a forward row without its `to`), shifting the rest; the line
    number anchors the row: quote and why follow it, from and to precede it."""
    f = fields + [""] * (len(FIND_COLS) - len(fields))
    if len(fields) == len(FIND_COLS) and (f[3].isdigit() or f[3] in ("", "-")):
        return dict(zip(FIND_COLS, f))
    j = next((i for i in range(1, len(fields) - 1) if fields[i].isdigit()), None)
    if j is None:
        return dict(zip(FIND_COLS, f))
    before = fields[1:j]
    return {"kind": fields[0], "from": before[0] if before else "-",
            "to": before[1] if len(before) > 1 else "-", "line": fields[j],
            "quote": fields[j + 1], "why": fields[j + 2] if j + 2 < len(fields) else ""}


def replies(d):
    """NNNN.tsv or NNNN.txt files in d (a .tsv wins); either may be a model's
    whole reply with the table in a code fence."""
    by = {}
    for f in sorted(d.glob("*.txt")) + sorted(d.glob("*.tsv")):
        by[f.stem] = f
    return [by[k] for k in sorted(by)]


def section_zones(lines):
    """For each 1-based line, the text in which a pointer covers it: its own
    section (heading to the next heading of the same or higher level) plus the
    introduction of every enclosing section. Fenced code is not a heading."""
    heads, fence = [], False
    for i, l in enumerate(lines):
        if re.match(r"\s*(```|~~~)", l):
            fence = not fence
        elif not fence and (m := re.match(r"(#{1,6})\s+(.*)", l)):
            heads.append((i, len(m.group(1)), m.group(2).strip()))
    n = len(lines)
    span = []
    for k, (i, lev, t) in enumerate(heads):
        end = next((j for j, lv, _ in heads[k + 1:] if lv <= lev), n)
        intro = heads[k + 1][0] if k + 1 < len(heads) else n
        span.append((i, end, intro, lev, t))

    def zone(ln):
        """(section title, text that may hold a pointer) for 1-based line ln."""
        x = ln - 1
        inside = [s for s in span if s[0] <= x < s[1]]
        if not inside:
            first = heads[0][0] if heads else n
            return "(before the first heading)", "\n".join(lines[:first])
        own = inside[-1]
        parts = ["\n".join(lines[own[0]:own[1]])]
        parts += ["\n".join(lines[s[0]:s[2]]) for s in inside[:-1]]
        return own[4], "\n".join(parts)
    return zone


def points_to(text, mid):
    return re.search(r"(?<![\w.])" + re.escape(mid) + r"(?!\w)", text) is not None


def fenced(lines):
    """Set of 0-based line indexes inside fenced code blocks (fences included)."""
    out, fence = set(), False
    for i, l in enumerate(lines):
        if re.match(r"\s*(```|~~~)", l):
            out.add(i)
            fence = not fence
        elif fence:
            out.add(i)
    return out


def verify(work, cfg):
    concepts, edges = load_graph(work)
    by = {c["id"]: c for c in concepts}
    order = teaching_order(work, concepts)
    pos = {m: i for i, m in enumerate(order)}
    have = {(e["from"], e["to"]) for e in edges}
    anc = ancestors(edges)
    rows = []
    for f in replies(work / "graph" / "audit" / "findings"):
        mid = f.stem
        lines = (module_text(work, cfg, mid) or "").split("\n")
        zone = section_zones(lines)
        for fields in courselib.read_table(f, "kind", raw=True):
            r = realign_finding(fields)
            row = dict(r, module=mid, accept="", status="", detail="")
            if r["kind"] == "forward":
                a = r["from"]
                n = int(r["line"]) if r["line"].isdigit() else 0
                if a not in by or pos.get(by[a]["module"], 0) <= pos.get(mid, 0):
                    row["status"] = "unknown"
                    row["detail"] = "not a concept taught after this module"
                else:
                    t = by[a]["module"]
                    hit = n and points_to(zone(n)[1], t)
                    row["status"] = "forward" if hit else "unmarked"
                    row["detail"] = f"{a} is taught in {t}; " + (
                        f"the section points to {t}" if hit else f"no pointer to {t}")
                rows.append(row)
                continue
            if r["kind"] != "edge":
                row["status"] = r["kind"]
                rows.append(row)
                continue
            a, b = r["from"], r["to"]
            q = norm(r["quote"]).strip('"')
            try:
                n = int(r["line"])
            except ValueError:
                n = 0
            near = norm(" ".join(lines[max(0, n - 4):n + 3])) if n else ""
            if a not in by or b not in by or by[b]["module"] != mid:
                row["status"] = "unknown"
            elif (a, b) in have:
                row["status"] = "duplicate"
            elif not q or (q not in near and q not in norm("\n".join(lines))):
                row["status"] = "bad-quote"
            elif a == b or b in anc(a):
                row["status"] = "cycle"
                row["detail"] = f"{b} already reaches {a}"
            elif pos.get(by[a]["module"], 0) > pos.get(mid, 0):
                t = by[a]["module"]
                if n and points_to(zone(n)[1], t):
                    row["status"] = "forward"
                    row["detail"] = (f"{a} is taught in {t}, after {mid}; the section points "
                                     f"to {t}, but the reviewer read it as a dependency")
                else:
                    row["status"] = "order"
                    row["detail"] = f"{a} is taught in {t}, after {mid}"
            elif a in anc(b):
                row["status"] = "implied"
                row["detail"] = f"{a} already reaches {b} indirectly"
            else:
                row["status"] = "ok"
            if row["status"] in ("ok", "implied", "order", "forward") and q not in near:
                row["detail"] = (row["detail"] + "; " if row["detail"] else "") + "quote found, but not at the given line"
            rows.append(row)
    rank = {s: i for i, s in enumerate(
        ["ok", "implied", "order", "unmarked", "forward", "cycle", "note",
         "missing-concept", "module-only",
         "bad-quote", "duplicate", "unknown"])}
    rows.sort(key=lambda r: (rank.get(r["status"], 99), r["module"], r["to"]))
    out = work / "graph" / "audit" / "candidates.tsv"
    courselib.write_tsv(out, rows, CAND_COLS)
    tally = collections.Counter(r["status"] for r in rows)
    print(f"wrote {out}: " + ", ".join(f"{k} {v}" for k, v in
                                       sorted(tally.items(), key=lambda kv: rank.get(kv[0], 99))))


FWD_COLS = ["concept", "label", "taught_in", "module", "section", "lines",
            "pointer", "restated", "quote"]


def concept_terms(c):
    """(regex, flags) pairs for finding mentions of a concept in prose."""
    if (c.get("terms") or "").strip():
        ts = [t.strip() for t in c["terms"].split("|") if t.strip()]
        return [(r"(?<!\w)" + re.escape(t) + r"(?:s|es)?(?!\w)", re.I) for t in ts]
    out = []
    base = re.sub(r"\s*\([^)]*\)", "", c["label"]).strip()
    if re.fullmatch(r"[A-Za-z][A-Za-z '\-]{2,}", base):
        out.append((r"(?<!\w)" + re.escape(base) + r"(?:s|es)?(?!\w)", re.I))
    for p in re.findall(r"\(([^)]*)\)", c["label"]):
        p = p.strip()
        if re.fullmatch(r"[A-Z][A-Z0-9]{1,7}", p):
            out.append((r"(?<![\w.])" + re.escape(p) + r"(?!\w)", 0))
        elif re.fullmatch(r"[A-Za-z][A-Za-z '\-]{2,}", p):
            out.append((r"(?<!\w)" + re.escape(p) + r"(?:s|es)?(?!\w)", re.I))
    return out


def forward(work, cfg):
    concepts, _ = load_graph(work)
    order = teaching_order(work, concepts)
    pos = {m: i for i, m in enumerate(order)}
    texts = {}
    for m in order[1:]:
        t = module_text(work, cfg, m)
        if t is not None:
            lines = t.split("\n")
            texts[m] = (lines, section_zones(lines), fenced(lines))
    rows = []
    for c in concepts:
        home = c["module"]
        if home == "PRIOR" or home not in pos:
            continue
        rx = [re.compile(p, fl) for p, fl in concept_terms(c)]
        again = {x.strip() for x in (c.get("restated_in") or "").split(",") if x.strip()}
        for m in order[1:pos[home]]:
            if m not in texts:
                continue
            lines, zone, code = texts[m]
            found = collections.OrderedDict()
            for i, l in enumerate(lines):
                if i in code or re.match(cfg["prereq_line"], l):
                    continue
                if any(r.search(l) for r in rx):
                    sec, ztext = zone(i + 1)
                    found.setdefault(sec, []).append((i + 1, l, points_to(ztext, home)))
            for sec, hits in found.items():
                ptr = all(h[2] for h in hits)
                rows.append({"concept": c["id"], "label": c["label"], "taught_in": home,
                             "module": m, "section": sec,
                             "lines": ",".join(str(h[0]) for h in hits),
                             "pointer": "yes" if ptr else "no",
                             "restated": "yes" if m in again else "",
                             "quote": norm(hits[0][1])[:160]})
    rows.sort(key=lambda r: (pos[r["module"]], r["pointer"], r["concept"]))
    out = work / "graph" / "audit" / "forward.tsv"
    out.parent.mkdir(parents=True, exist_ok=True)
    courselib.write_tsv(out, rows, FWD_COLS)
    n = collections.Counter(r["pointer"] for r in rows)
    print(f"wrote {out}: {len(rows)} forward mentions, {n['yes']} with a pointer, "
          f"{n['no']} without")
    for r in rows:
        if r["pointer"] == "no":
            print(f"  {r['module']} \u00a7 {r['section']}: {r['concept']} "
                  f"(taught in {r['taught_in']}) lines {r['lines']}")





def grade_prepare(work, cfg, only):
    concepts, edges = load_graph(work)
    by = {c["id"]: c for c in concepts}
    titles = {m["id"]: m["title"] for m in courselib.modules(work)}
    cpath = work / "graph" / "audit" / "candidates.tsv"
    cands = [r for r in csv.DictReader(open(cpath), delimiter="\t")
             if r["status"] == "ok"] if cpath.exists() else []
    out = work / "graph" / "audit" / "grade-packets"
    out.mkdir(parents=True, exist_ok=True)
    (work / "graph" / "audit" / "grades").mkdir(exist_ok=True)

    def desc(i):
        c = by[i]
        return f"`{i}` ({c['label']}, module {c['module']}): {c['definition']}"
    made = []
    for mid in teaching_order(work, concepts):
        if mid == "PRIOR" or (only and mid not in only):
            continue
        defined = [c for c in concepts if c["module"] == mid]
        text = module_text(work, cfg, mid)
        if not defined or text is None:
            continue
        ids = {c["id"] for c in defined}
        dest = work / "graph" / "audit" / "grades" / f"{mid}.tsv"
        L = [courselib.prompt("grade", mid=mid, title=titles.get(mid, ""),
                                 rubric=courselib.prompt("rubric"), out=dest),
             f"## Concepts defined in module {mid}\n"]
        L += [f"- {desc(c['id'])}" for c in defined]
        L.append("\n## Existing edges (E): grade each\n")
        n = 0
        for e in edges:
            if e["to"] in ids:
                n += 1
                note = f" Note: {e['note']}" if e.get("note") else ""
                L.append(f"- E{n}: {e['from']} -> {e['to']}.{note}\n  from = {desc(e['from'])}")
        L.append("\n## New candidates (C), found by an earlier reviewer: grade each\n")
        k = 0
        for r in cands:
            if r["module"] == mid:
                k += 1
                L.append(f"- C{k}: {r['from']} -> {r['to']}. Evidence, line {r['line']}: "
                         f"\"{r['quote']}\". Reviewer: {r['why']}\n  from = {desc(r['from'])}")
        if not k:
            L.append("(none)")
        L.append(f"\n## Module {mid} text, with line numbers\n")
        L += [f"{i:4} | {line}" for i, line in enumerate(text.split("\n"), 1)]
        (out / f"{mid}.md").write_text("\n".join(L) + "\n")
        made.append(f"{mid}(E{n},C{k})")
    print(f"wrote {len(made)} grading packets to {out}: {' '.join(made)}")


def reaches(succ, a, b):
    """True if a path a -> ... -> b exists."""
    seen, stack = set(), [a]
    while stack:
        n = stack.pop()
        if n == b:
            return True
        if n not in seen:
            seen.add(n)
            stack.extend(succ[n])
    return False


def path_strength(succ, st, a, b, skip=None):
    """Strength of the strongest path a -> ... -> b, ignoring the edge `skip`.

    A path is as strong as its weakest edge (ungraded edges count as 1). None
    if there is no path. Used for redundancy: an edge is implied only when some
    other path is at least as strong as it is, so a definitional edge is never
    dropped in favour of a chain through a supporting one.
    """
    import heapq
    best, heap = {a: 2.0}, [(-2.0, a)]
    while heap:
        v, n = heapq.heappop(heap)
        v = -v
        if n == b:
            return v
        if v < best.get(n, -1):
            continue
        for m in succ[n]:
            if (n, m) == skip:
                continue
            w = min(v, st.get((n, m), 1.0))
            if w > best.get(m, -1):
                best[m] = w
                heapq.heappush(heap, (-w, m))
    return None


def strength_of(e):
    try:
        return float(e.get("strength") or "")
    except ValueError:
        return 1.0


def grade_apply(work, cfg, write):
    g = work / "graph"
    concepts, edges = load_graph(work)
    by = {c["id"]: c for c in concepts}
    order = teaching_order(work, concepts)
    pos = {m: i for i, m in enumerate(order)}
    grades = {}
    for f in replies(g / "audit" / "grades"):
        for r in courselib.read_table(f, "ref"):
            r = {k: (v or "").strip() for k, v in r.items() if k}
            try:
                r["s"] = max(0.0, min(1.0, float(r["strength"])))
            except (KeyError, ValueError):
                continue
            r["module"] = f.stem
            grades.setdefault((r["from"], r["to"]), r)
    alerts = collections.defaultdict(list)

    # existing edges keep their place; they only gain a strength
    out, ungraded = [], 0
    for e in edges:
        r = grades.get((e["from"], e["to"]))
        # an edge nobody graded keeps whatever strength it already had
        s = (e.get("strength") or "") if r is None else f"{r['s']:.2f}".rstrip("0").rstrip(".") or "0"
        if r is None:
            ungraded += 1
        elif r["s"] == 0:
            alerts["zero"].append(f"- `{e['from']}` -> `{e['to']}` (module {r['module']}): {r['why']}")
        out.append({"from": e["from"], "to": e["to"], "strength": s, "note": e.get("note", "")})

    succ = collections.defaultdict(set)
    for e in out:
        succ[e["from"]].add(e["to"])
    have = {(e["from"], e["to"]) for e in out}
    st = {(e["from"], e["to"]): strength_of(e) for e in out}
    for e in out:
        k = (e["from"], e["to"])
        p = path_strength(succ, st, *k, skip=k)
        if p is not None and p >= st[k]:
            alerts["redundant"].append(f"- `{k[0]}` -> `{k[1]}` (strength {st[k]:g}; "
                                       f"another path has strength {p:g})")
    new = sorted((r for r in grades.values()
                  if r.get("ref", "")[:1] in ("C", "W") and (r["from"], r["to"]) not in have
                  and r["from"] in by and r["to"] in by and r["s"] > 0),
                 key=lambda r: -r["s"])
    added, implied = 0, 0
    for r in new:
        a, b, s = r["from"], r["to"], r["s"]
        where = f"module {r['module']}, line {r.get('line', '?')}"
        if a == b or reaches(succ, b, a):
            alerts["cycle"].append(f"- `{a}` -> `{b}` ({where}, strength {s}): {r['why']}")
        elif pos.get(by[a]["module"], 0) > pos.get(by[b]["module"], 0):
            alerts["order"].append(f"- `{a}` (module {by[a]['module']}) -> `{b}` ({where}, strength {s}): {r['why']}")
        elif (path_strength(succ, st, a, b) or -1) >= s:
            implied += 1
        else:
            succ[a].add(b)
            st[(a, b)] = s
            added += 1
            out.append({"from": a, "to": b, "strength": f"{s:g}",
                        "note": f"audit {r['module']}:{r.get('line', '')}: {r['why']}".replace("\t", " ")})

    cpath = g / "audit" / "candidates.tsv"
    for r in (csv.DictReader(open(cpath), delimiter="\t") if cpath.exists() else []):
        line = f"- `{r['from']}` -> `{r['to']}` (module {r['module']}, line {r['line']}): \"{r['quote']}\" {r['why']} [{r['detail']}]"
        if r["status"] in ("cycle", "order", "unmarked", "forward"):
            alerts[r["status"]].append(line)
        elif r["status"] == "missing-concept":
            alerts["missing"].append(f"- module {r['module']}: {r['to']}. {r['why']}")
        elif r["status"] == "note":
            alerts["note"].append(line)
    for r in courselib.tsv(g / "audit" / "forward.tsv", FWD_COLS):
        line = (f"- `{r['concept']}` ({r['label']}, taught in {r['taught_in']}) in module "
                f"{r['module']}, \u00a7 {r['section']}, line {r['lines']}: \"{r['quote']}\""
                + (f" (module {r['module']} also restates its definition)" if r.get("restated") else ""))
        alerts["forward" if r["pointer"] == "yes" else "unmarked"].append(line)

    raw = open(g / "edges.tsv", newline="").read()
    eol = "\r\n" if "\r\n" in raw else "\n"
    cols = ["from", "to", "strength", "note"]
    text = eol.join(["\t".join(cols)] + ["\t".join(e[c] for c in cols) for e in out]) + eol
    (g / "audit" / "edges.proposed.tsv").write_text(text, newline="")
    heads = {
        "note": "Problems in the text itself: circular or repeated definitions.",
        "cycle": "Cycles: the text makes each concept depend on the other. Usually a concept "
                 "that needs splitting, or material explained before it is taught.",
        "order": "Teaching order: a module depends on a concept that a later module "
                 "teaches, and does not say where it is taught.",
        "unmarked": "Forward mentions without a pointer: a module names a concept a "
                    "later module teaches. Add a forward reference (where it is taught, "
                    "whether the reader needs it now), or move the material.",
        "forward": "Forward references with a pointer (acknowledged; check each still "
                   "reads correctly without the later concept).",
        "zero": "Existing edges with no support in the defining module's text (not removed).",
        "missing": "Ideas a module develops that the graph has no concept for.",
        "redundant": "Edges implied by another path at least as strong (run prune to "
                     "remove them; new edges like these are not added).",
    }
    md = ["# Edge audit alerts\n",
          f"Existing edges graded: {len(out) - added - ungraded}, ungraded: {ungraded}. "
          f"New edges added: {added}. Skipped as implied (a path already exists): {implied}.\n"]
    for k, h in heads.items():
        md += [f"\n## {h} ({len(alerts[k])})\n"] + alerts[k]
    (g / "audit" / "alerts.md").write_text("\n".join(md) + "\n")
    print(f"existing {len(out) - added} (ungraded {ungraded}), added {added}, implied {implied}, "
          + ", ".join(f"{k} {len(v)}" for k, v in alerts.items()))
    if write:
        (g / "edges.tsv").write_text(text, newline="")
        print(f"wrote {g / 'edges.tsv'}; now run check.py")
    else:
        print(f"wrote {g / 'audit' / 'edges.proposed.tsv'} and alerts.md; --write to replace edges.tsv")


def prune(work, write):
    """Remove edges graded 0, then edges implied by a path at least as strong.

    Weakest first, recomputing after every removal, so each removed edge still
    has an equally strong path when it goes: the strongest-path strength
    between every pair of concepts is unchanged. Removed rows are appended to
    graph/audit/removed.tsv with the reason.
    """
    g = work / "graph"
    raw = open(g / "edges.tsv", newline="").read()
    eol = "\r\n" if "\r\n" in raw else "\n"
    edges = list(csv.DictReader(open(g / "edges.tsv"), delimiter="\t"))
    cols = list(edges[0].keys()) if edges else ["from", "to", "strength", "note"]
    st = {(e["from"], e["to"]): strength_of(e) for e in edges}
    succ = collections.defaultdict(set)
    for a, b in st:
        succ[a].add(b)
    gone = {}
    for e in edges:
        k = (e["from"], e["to"])
        if (e.get("strength") or "").strip() and st[k] == 0:
            gone[k] = "strength 0: no support in the text"
            succ[k[0]].discard(k[1])
    for k in sorted((k for k in st if k not in gone), key=lambda k: st[k]):
        p = path_strength(succ, st, *k, skip=k)
        if p is not None and p >= st[k]:
            gone[k] = f"implied: another path has strength {p:g} >= {st[k]:g}"
            succ[k[0]].discard(k[1])
    keep = [e for e in edges if (e["from"], e["to"]) not in gone]
    print(f"{len(edges)} edges, {len(gone)} to remove "
          f"({sum(1 for v in gone.values() if v.startswith('strength 0'))} with strength 0), {len(keep)} kept")
    if not write:
        for k, why in gone.items():
            print(f"  {k[0]} -> {k[1]}: {why}")
        print("dry run; --write to apply")
        return
    log = g / "audit" / "removed.tsv"
    new_log = not log.exists()
    with open(log, "a", newline="") as fh:
        if new_log:
            fh.write("\t".join(cols + ["removed_because"]) + "\n")
        for e in edges:
            k = (e["from"], e["to"])
            if k in gone:
                fh.write("\t".join([e.get(c) or "" for c in cols] + [gone[k]]) + "\n")
    text = eol.join(["\t".join(cols)] + ["\t".join(e.get(c) or "" for c in cols) for e in keep]) + eol
    (g / "edges.tsv").write_text(text, newline="")
    print(f"wrote {g / 'edges.tsv'} and appended to {log}; now run check.py")


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args and not args[0].startswith("-") else ""
    work, cfg = courselib.load([a for a in args if a != cmd])
    only = set(args[args.index("--only") + 1].split(",")) if "--only" in args else None
    if cmd == "prepare":
        prepare(work, cfg, only)
    elif cmd == "verify":
        verify(work, cfg)
    elif cmd == "forward":
        forward(work, cfg)
    elif cmd == "grade-prepare":
        grade_prepare(work, cfg, only)
    elif cmd == "grade-apply":
        grade_apply(work, cfg, "--write" in args)
    elif cmd == "prune":
        prune(work, "--write" in args)
    else:
        sys.exit(__doc__)
