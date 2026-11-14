#!/usr/bin/env python3
"""Export the concept graph as NotebookLM sources for Socratic tutoring.

Reads graph/concepts.tsv, graph/edges.tsv, modules.tsv and clean/, and writes
these into <workdir>/notebooklm/, replacing them but leaving any other file
there untouched:

  <course> concept map.md     one self-contained card per concept: definition,
                              direct prerequisites (with why), what it unlocks,
                              restatements, and its full foundation by module
  modules/NNNN <title>.md     each clean/ module, front matter stripped, ../NNNN
                              links spelled out, prefixed with where it sits
  chat-instructions.txt       text for NotebookLM's "Configure chat" box

If graph/audit/forward.tsv exists (edge_audit.py forward), each forward
reference that the author marked with a pointer is named on the concept's card
and in the mentioning module's header, so the tutor tells a student that the
concept is taught later instead of stepping back through earlier concepts.

Every card repeats names and module titles rather than relying on headings,
because a retriever hands the model one chunk at a time, out of context.
"""
import collections, csv, re, shutil, sys
import courselib

work, cfg = courselib.load()
g = work / "graph"
out = work / "notebooklm"
course = cfg.get("course_name") or cfg.get("canvas_course") or work.name
# --structure-only: a variant map with no definitions, so it cannot be cited
# for what a concept *is* -- only for how concepts relate. Written alone to
# notebooklm/experiments/; the normal outputs are left as they are.
lean = "--structure-only" in sys.argv
map_title = f"{course} concept map" + (" (structure only)" if lean else "")

C = list(csv.DictReader(open(g / "concepts.tsv"), delimiter="\t"))
E = list(csv.DictReader(open(g / "edges.tsv"), delimiter="\t"))
by_id = {c["id"]: c for c in C}
row = {c["id"]: i for i, c in enumerate(C)}
pre, post = collections.defaultdict(list), collections.defaultdict(list)
note, strength = {}, {}
for e in E:
    if e["from"] not in by_id or e["to"] not in by_id:
        sys.exit(f"unknown id in edge {e['from']} -> {e['to']}; run check.py")
    pre[e["to"]].append(e["from"])
    post[e["from"]].append(e["to"])
    note[(e["from"], e["to"])] = (e.get("note") or "").strip()
    try:
        strength[(e["from"], e["to"])] = float(e.get("strength") or "")
    except ValueError:
        pass

# forward references the author marked with a pointer: concept -> [(module, section)]
fwd, fwd_in = collections.defaultdict(list), collections.defaultdict(list)
for r in courselib.tsv(g / "audit" / "forward.tsv", []):
    if r.get("pointer") == "yes" and r.get("concept") in by_id:
        if (r["module"], r["section"]) not in fwd[r["concept"]]:
            fwd[r["concept"]].append((r["module"], r["section"]))
        if r["concept"] not in fwd_in[r["module"]]:
            fwd_in[r["module"]].append(r["concept"])

# ---- modules: Canvas order, titles (manifest first, then repo front matter)
def front_title(text):
    m = re.search(r'^title:\s*"?(?:Module \d+:\s*)?(.*?)"?\s*$', text, re.M)
    return m.group(1).replace('\\"', '"') if m else None


manifest = courselib.modules(work)
pos = {m["id"]: i + 1 for i, m in enumerate(manifest)}
unit = {m["id"]: m["canvas_module"] for m in manifest}
# wording for where a module sits; a course without Canvas sets these in course.json
UNIT = cfg.get("unit_label", "Canvas unit")
ORDER_SOURCE = cfg.get("order_source", "Canvas")
title = {m["id"]: m["title"] for m in manifest}
for mid in title:  # prefer the module's own title: it names the NotebookLM source
    f = work / "clean" / f"{mid}.md"
    if f.exists():
        title[mid] = front_title(f.read_text()) or title[mid]


for mid in sorted({c["module"] for c in C} - set(title) - {"PRIOR"}):
    f = courselib.source_file(cfg, mid.removeprefix("EXT-"))
    title[mid] = (f and front_title(f.read_text())) or "(title unknown)"
title["PRIOR"] = "assumed from prerequisite coursework"


def mod_name(mid):
    if mid == "PRIOR":
        return "prior knowledge (not taught in this course)"
    return f"module {mid}, “{title[mid]}”"


def mod_key(mid):
    return (0, 0) if mid == "PRIOR" else (1, pos[mid]) if mid in pos else (2, mid)


# ---- levels (longest path from a root) and topological order
level = {}


def lvl(i):
    if i not in level:
        level[i] = 1 + max((lvl(p) for p in pre[i]), default=-1)
    return level[i]


for c in C:
    lvl(c["id"])
depth = max(level.values())


def ckey(i):
    return (mod_key(by_id[i]["module"]), level[i], row[i])


anc_memo = {}


def ancestors(i):
    if i not in anc_memo:
        s = set()
        for p in pre[i]:
            s |= {p} | ancestors(p)
        anc_memo[i] = s
    return anc_memo[i]


# longest chain: walk back from the deepest concept along max-level parents
tail = max(C, key=lambda c: (level[c["id"]], -row[c["id"]]))["id"]
chain = [tail]
while pre[chain[-1]]:
    chain.append(max(pre[chain[-1]], key=lambda p: (level[p], -row[p])))
chain.reverse()

lab = lambda i: by_id[i]["label"]
mods_in_order = sorted({c["module"] for c in C}, key=mod_key)
concepts_of = collections.defaultdict(list)
for c in sorted(C, key=lambda c: ckey(c["id"])):
    concepts_of[c["module"]].append(c["id"])

mod_pre, mod_post = collections.defaultdict(set), collections.defaultdict(set)
for e in E:
    a, b = by_id[e["from"]]["module"], by_id[e["to"]]["module"]
    if a != b:
        mod_pre[b].add(a)
        mod_post[a].add(b)


def where(mid):
    if mid == "PRIOR":
        return "Assumed from prerequisite coursework."
    if mid in pos:
        return (f"{UNIT} “{unit[mid]}”, item {pos[mid]} of "
                f"{len(manifest)} in teaching order.")
    return (f"Not linked from {ORDER_SOURCE}, and its text is not among this notebook's "
            "sources.")


def mlist(ms, none="nothing"):
    return "; ".join(mod_name(m) for m in sorted(ms, key=mod_key)) or none


def short(mid):
    return "prior knowledge" if mid == "PRIOR" else f"module {mid}"


def semi(ids):
    return "; ".join(lab(i) for i in ids)


# ---- concept map
L = []
w = L.append
w(f"# {map_title}\n")
w(f"This source maps every concept in the {course} modules and how each one "
  "depends on the others. It is meant to be used alongside the module "
  "sources, which hold the actual explanations.\n")
if lean:
    w("This map deliberately contains no definitions. For what any concept "
      "means, read the module that defines it; this map only says which "
      "concepts depend on which.\n")
w("How to read a concept card:\n")
w("- **Builds directly on** lists the concepts a student must already "
  "understand to make sense of this one. If a student is stuck, these are "
  "the first things to check, one step back.")
w("- **Leads directly to** lists the concepts that use this one. Once a "
  "student has this concept, these are the natural next steps forward.")
w("- **Full foundation** lists every concept this one rests on, directly or "
  "indirectly, grouped by module in teaching order.")
w(f"- **Depth** counts the longest chain of prerequisites below the concept, "
  f"from 0 (needs nothing from this course) to {depth}.")
w("- **Also restated in** names other modules that repeat or extend the "
  "definition.")
w("- **Mentioned before it is taught** names earlier modules that use the "
  "concept as a forward reference and say where it is taught. A student who "
  "meets it there is not missing a prerequisite: it has not been taught yet.\n")
w(f"The map has {len(C)} concepts and {len(E)} prerequisite links across "
  f"{len([m for m in mods_in_order if m != 'PRIOR'])} modules. It has no "
  "cycles, so stepping back through prerequisites always ends at "
  "foundations.\n")

w("## The course spine: its longest prerequisite chain\n")
w("The longest chain of concepts, each one building directly on the one "
  "before it:\n")
for n, i in enumerate(chain, 1):
    w(f"{n}. {lab(i)} ({mod_name(by_id[i]['module'])})")
w("")

w("## Modules in teaching order and how they depend on each other\n")
for mid in mods_in_order:
    w(f"- **{mod_name(mid)[0].upper() + mod_name(mid)[1:]}.** {where(mid)} "
      f"Builds on: {mlist(mod_pre[mid])}. Leads to: "
      f"{mlist(mod_post[mid], 'no later module')}.")
w("")


def grade(s):
    """Words for an edge strength, so a retriever matches more than a number."""
    for cut, word in ((0.9, "definitional"), (0.7, "core"), (0.5, "substantial"),
                      (0.3, "secondary"), (0.0, "supporting")):
        if s >= cut:
            return f"{word} dependency, strength {s:g}"
    return ""


def item(i, other_end, edge):
    c = by_id[i]
    why = note.get(edge, "")
    # audit notes read "audit 0283:34: Core: reason." -- keep the reason only
    why = re.sub(r"^audit \S+:\d*:\s*", "", why)
    why = re.sub(r"^(Definitional|Core|Substantial|Secondary|Supporting)\s*:\s*", "", why, flags=re.I)
    why = why.rstrip(". ")
    why = f" Why: {why[:1].upper() + why[1:]}." if why else ""
    body = why.strip() if lean else f"{c['definition']}{why}"
    s = strength.get(edge)
    tag = f", {grade(s)}" if s is not None else ""
    return (f"- **{c['label']}** ({short(c['module'])}{tag})"
            + (f": {body}" if body else ""))


def by_strength(edges_of, key):
    """Strongest first; ungraded edges after graded ones; then curriculum order."""
    return sorted(edges_of, key=lambda x: (-strength.get(key(x), -1), ckey(x)))


STRONG = 0.5   # prerequisites at or above this go into the tutoring path


for mid in mods_in_order:
    name = mod_name(mid)
    w(f"# Concepts from {name}\n")
    w(f"{where(mid)} Builds on {mlist(mod_pre[mid])}. Leads to "
      f"{mlist(mod_post[mid], 'no later module')}.\n")
    w(f"Concepts in {name}, in dependency order: "
      + semi(concepts_of[mid]) + ".\n")
    for i in concepts_of[mid]:
        c = by_id[i]
        ps = by_strength(pre[i], lambda p: (p, i))
        ds = by_strength(post[i], lambda d: (i, d))
        w(f"## {c['label']} — concept from {name}\n")
        w(f"**{c['label']}** (id `{i}`) is defined in {name}. "
          + ("Its definition is in that module, not in this map.\n" if lean
             else f"{c['definition']}\n"))
        w(f"Depth {level[i]} of {depth}. {where(mid)}\n")
        if ps:
            w(f"**{c['label']}** builds directly on:\n")
            for p in ps:
                w(item(p, i, (p, i)))
            w("")
        else:
            w(f"**{c['label']}** builds on nothing else in this course; it "
              "is a starting point.\n")
        if ds:
            w(f"**{c['label']}** leads directly to:\n")
            for d in ds:
                w(item(d, i, (i, d)))
            w("")
        else:
            w(f"Nothing later in the course builds directly on "
              f"**{c['label']}**.\n")
        if c.get("restated_in", "").strip():
            again = [m.strip() for m in c["restated_in"].split(",") if m.strip()]
            w(f"Also restated in: {mlist(again)}.\n")
        if fwd[i]:
            w(f"**{c['label']}** is mentioned before it is taught, as a forward "
              "reference, in " + "; ".join(f"{short(m)} (section “{sec}”)"
                                          for m, sec in fwd[i])
              + f". A student who meets it there does not need it yet: say that "
              f"it is taught in {mod_name(mid)}, and whether the passage can be "
              "followed without it, rather than stepping back through earlier "
              "concepts.\n")
        anc = ancestors(i)
        if len(anc) > len(ps):
            groups = collections.defaultdict(list)
            for a in sorted(anc, key=ckey):
                groups[by_id[a]["module"]].append(lab(a))
            w(f"Full foundation of **{c['label']}** ({len(anc)} concepts): "
              + " | ".join(f"{short(m)}: " + "; ".join(v) for m, v in
                           sorted(groups.items(), key=lambda kv: mod_key(kv[0])))
              + ".\n")
        tutor = []
        key_ps = [p for p in ps if strength.get((p, i), 1) >= STRONG] or ps[:1]
        key_ds = [d for d in ds if strength.get((i, d), 1) >= STRONG] or ds[:1]
        if key_ps:
            tutor.append(f"Before working on {c['label']}, check that the "
                         "student can explain " + semi(key_ps) +
                         f" in their own words, and say how each is used in "
                         f"{c['label']}.")
        if len(key_ps) < len(ps):
            tutor.append("It also draws on " + semi([p for p in ps if p not in key_ps])
                         + ", in a supporting role.")
        if key_ds:
            tutor.append(f"Once {c['label']} is solid, ask how it is used in " +
                         semi(key_ds) + ".")
        if tutor:
            w("Tutoring path: " + " ".join(tutor) + "\n")

if lean:
    (out / "experiments").mkdir(parents=True, exist_ok=True)
    f = out / "experiments" / f"{map_title}.md"
    f.write_text("\n".join(L))
    print(f"{f.relative_to(work)}: {len(f.read_text().split())} words")
    sys.exit()

out_tmp = out.with_name(out.name + ".tmp")
shutil.rmtree(out_tmp, ignore_errors=True)
(out_tmp / "modules").mkdir(parents=True)
(out_tmp / f"{course} concept map.md").write_text("\n".join(L))

# ---- module sources


def safe(s):
    return re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|]', "", s)).strip()


def rewrite(text):
    def link(m):
        txt, mid = m.group(1), m.group(2)
        t = title.get(mid) or "another module"
        return (f"module {mid} (“{t}”)" if txt.strip() == mid
                else f"{txt} (module {mid}, “{t}”)")
    text = re.sub(r"\[([^\]]*)\]\(\.\./(" + cfg["id_pattern"] + r")/?[^)]*\)", link, text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)",
                  lambda m: f"[Figure: {m.group(1)}; see the online module]"
                  if m.group(1).strip() not in ("", "image")
                  else "[Figure; see the online module]", text)
    return text


written = []
for m in manifest:
    mid = m["id"]
    f = work / "clean" / f"{mid}.md"
    if not f.exists():
        print(f"warning: no clean/{mid}.md", file=sys.stderr)
        continue
    text = f.read_text()
    t = front_title(text) or m["title"]
    body = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    head = [f"# Module {mid}: {t}\n",
            f"*Where this module sits (from the {course} concept map):* "
            f"{where(mid)} It builds on {mlist(mod_pre[mid])}, and leads to "
            f"{mlist(mod_post[mid], 'no later module')}. Concepts it defines: "
            + semi(concepts_of[mid]) + ".\n"]
    if fwd_in[mid]:
        head.append("Mentioned here before they are taught (forward references): "
                    + "; ".join(f"{lab(i)}, taught in {mod_name(by_id[i]['module'])}"
                                for i in fwd_in[mid]) + ".\n")
    if cfg.get("pages_base"):
        head.append(f"Online version: {cfg['pages_base']}/{mid}/\n")
    name = f"{mid} {safe(t)}.md"
    (out_tmp / "modules" / name).write_text("\n".join(head) + "\n" +
                                             rewrite(body).lstrip())
    written.append(name)

# ---- chat instructions
(out_tmp / "chat-instructions.txt").write_text(f"""\
You are a Socratic tutor for {course}. Help the student reach understanding by asking, not telling.

The sources are the course modules (one per module) and the "{course} concept map". The map has one card per concept: its definition, what it "builds directly on", what it "leads directly to", and its full foundation.

When the student asks about a concept:
1. Find its card in the concept map. Ask one question at a time, starting with the most direct prerequisite listed under "builds directly on". Wait for the answer.
2. If an answer shows a gap, step back to that prerequisite's card and repeat. Keep stepping back until you reach something the student does know, then work forward again one link at a time.
3. Explain only when questions have stalled, and then briefly, in the module's own words and notation, citing the module.
4. When the student gets something right, ask how it connects to the next concept on the path, so they build the links themselves.
5. If the student meets a concept in a module before the module that teaches it (the card says "mentioned before it is taught"), it is a forward reference, not a gap: tell them where it is taught and whether they need it now, and do not step back through its prerequisites.
6. Concepts marked as prior knowledge are assumed from earlier courses: point the student to review them rather than teaching them in full. Modules described as not among the notebook's sources cannot be quoted.

Refer to modules by number and title so the student can find the reading. Do not hand over complete answers to exercises; guide the student to them.
""")

# Replace only what this script generates; anything else in notebooklm/
# (hand-written instructions, recorded chats) is the user's and stays.
out.mkdir(exist_ok=True)
for item in out_tmp.iterdir():
    dest = out / item.name
    if dest.is_dir():
        shutil.rmtree(dest)
    elif dest.exists():
        dest.unlink()
    item.rename(dest)
out_tmp.rmdir()
words = sum(len(p.read_text().split()) for p in
            [out / f"{course} concept map.md", *(out / "modules").glob("*.md")])
cm = out / f"{course} concept map.md"
print(f"{cm.relative_to(work)}: {len(C)} cards, depth {depth}, "
      f"{len(cm.read_text().split())} words")
print(f"notebooklm/modules/: {len(written)} module sources")
print(f"notebooklm/chat-instructions.txt: "
      f"{len((out / 'chat-instructions.txt').read_text())} characters")
print(f"{1 + len(written)} sources, {words} words in all")
