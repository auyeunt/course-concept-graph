---
name: course-concept-graph
description: Build a concept/definition dependency DAG for a Canvas course whose content modules live in a GitHub repo — inventory the shell, audit the links, index the prose, extract concepts, prove the graph is acyclic, check Canvas teaching order against it, and rewrite each module's Prerequisites line. Use when the user asks for a concept map, dependency graph, prerequisite graph or DAG over course content, wants to know whether a course is taught in a valid order, whether anything is defined after it is used, what a module really depends on, which modules are missing or duplicated, or mentions a Canvas shell plus a GitHub OER module repo.
---

# Concept dependency graph for a Canvas + GitHub course

Two systems, and the whole point is the gap between them:

* **Canvas** holds the *teaching order* — which module a student meets first.
* **A GitHub repo** holds the *content*, published to GitHub Pages, with each
  module in `NNNN/index.md` or `NNNN/mdModule.md`.

The deliverable is a directed acyclic graph of concepts, plus everything that
falls out of comparing it against Canvas: modules referenced but unreachable,
concepts used before they are defined, concepts defined twice, and prerequisite
declarations that do not match what the prose actually uses.

**Canvas is read-only unless the user asks otherwise.** Report what needs
changing and let them change it; they usually prefer to. The content repo is
read-only too until they say to edit it.

## Layout

One working directory per course, separate from the content repo:

```
<workdir>/
  course.json        repo path, Pages base, Canvas course URL, id pattern
  modules.tsv        the module list, in Canvas presentation order
  ai-sections.tsv    AI-generated sections to drop before analysis
  links/NNNN.md      symlinks to the verbatim source
  clean/NNNN.md      the same, AI sections removed — this is what is analysed
  graph/concepts.tsv graph/edges.tsv       the graph; hand-edited, source of truth
  graph/extract/     extraction packets and replies (Step 5)
  graph/audit/       audit packets, replies, alerts (Step 5b)
  graph/report.html  the published artifact
```

`course.json`:

```json
{
  "repo": "~/modules",
  "module_files": ["index.md", "mdModule.md"],
  "pages_base": "https://USER.github.io/modules",
  "canvas_course": "https://lrccd.instructure.com/courses/NNNNNN",
  "id_pattern": "\\d{4}"
}
```

Scripts live in `scripts/` beside this file and all take `--dir WORKDIR`:
`build_corpus.py`, `check.py`, `render.py`, `prereqs.py`, `extract.py`,
`edge_audit.py`, `notebooklm.py`. They need only Python 3 (standard library)
and Graphviz for `render.py`. Every prompt a model reads is a plain file in
`prompts/` beside them; nothing in the procedure depends on which model reads
the packets.

The same folder is a kit for colleagues without Claude (see `README.md`):
`colab/course_concept_graph.ipynb` (built by `colab/build_notebook.py`) runs the
whole pipeline in Google Colab through `scripts/kit.py`, using Colab's built-in
Gemini or packets carried to the Gemini app by hand, and
`guide/faculty-guide.md` explains it for faculty. A course without Canvas or a
module repo uses readings files instead: `kit.import_readings` writes
`clean/mNN.md` and `modules.tsv` from `readings/` in file-name order, and
`course.json` carries `unit_label` and `order_source` for the wording. Change
behaviour in the scripts and prompts, never only in the notebook.

## Step 1: inventory the Canvas shell

Use Claude in Chrome; the user is normally signed in.

**Navigate to the API URL and read the page text.** Do not scrape the modules
page, and do not call `fetch()` from `javascript_tool` — the extension guard
refuses it. Navigating works:

```
https://<canvas>/api/v1/courses/<id>/modules?include[]=items&per_page=100
```

then `get_page_text`. One call returns every module, every item, its `position`,
`type`, `published`, and — for `ExternalUrl` items — the `external_url`. That is
everything this skill needs, and it is authoritative in a way the rendered page
is not: the DOM shows a Canvas redirect, not the destination.

For one module's items after an edit:
`/api/v1/courses/<id>/modules/<module_id>/items?per_page=100`.

**Watch the response size.** `get_page_text` persists anything large to a file
and truncates it at 50 KB, which lands mid-JSON and parses as a syntax error —
or worse, parses cleanly having silently dropped the tail. A course with more
than about 100 module items will exceed it. When that happens, or pre-emptively
for a big course, fetch the module list alone
(`/modules?per_page=100`, no `include[]`) and then walk
`/modules/<module_id>/items` one module at a time; each response stays small
enough to come back whole. `browser_batch` runs several navigate/read pairs in a
single round trip, so this costs little.

## Step 2: triage the links

Content modules are the `ExternalUrl` items matching `<pages_base>/<id_pattern>`.
Everything else — YouTube, Google Docs, quizzes, files — is out of scope.

Sort the rest into:

* **Wrong host.** The same numbered module served from an older location. If it
  is published, that is a live defect; if unpublished, note it and move on.
* **Referenced but unlinked.** A module named in another module's Prerequisites
  or an inline `../NNNN` link with no Canvas item pointing at it. Check the repo
  before calling it missing — the file usually exists and only the link is absent.
* **Trailing-slash variants.** `modules/0432/` resolves but will not match a
  strict pattern in a later sweep. Worth one line, not a finding.

`curl -o /dev/null -w '%{http_code}'` against the Pages URL settles whether a
module is actually unreachable or merely unlinked. Those are very different
problems and the fix differs.

Record the result in `modules.tsv` — id, Canvas module name, item title, status —
**in Canvas presentation order**, because `check.py` derives teaching order from
the row order. Use a status other than `published` for anything still needing a
Canvas-side fix; `render.py` draws those in amber.

## Step 3: build the corpus

Some modules embed their own AI-generated question banks. They are not the
author's exposition and they distort both the index and the concept extraction.
List them in `ai-sections.tsv` as `id <TAB> exact top-level heading`; each named
section is dropped from its heading to the next `# ` or EOF.

Match headings **exactly, never by regex.** A case-insensitive search for "AI"
matches "But w*ai*t, is `1101(2)` 13 or -3?" and silently eats a real section.

Then `build_corpus.py --dir .`. It rebuilds `links/` and `clean/` from scratch,
so it is safe to re-run after pulling the content repo.

## Step 4: index the prose

Follow the `rag-index` skill against `clean/`. Declare two sources: the modules
as tier `primary`, and an `analysis/` + `notes/` source as tier `derived` even
though it starts empty — declaring it now keeps your own later findings separable
from the source material, which is the split that goes wrong once analysis output
starts outnumbering the corpus.

The index is for *lookup while extracting concepts*. It does not build the graph.

## Step 5: extract the concepts

This is the judgment-heavy step. `extract.py` turns it into packets, one module
at a time in teaching order, that any capable model (or a person) can work:

    python3 $S/extract.py prepare --dir .        # packet for the next module
    # reader writes graph/extract/NNNN.tsv (a bare table or the whole reply)
    python3 $S/extract.py apply NNNN --dir .     # dry run: what passes the checks
    python3 $S/extract.py apply NNNN --dir . --write

Each packet holds `prompts/extract.md`, the strength rubric, every concept
already in the graph and the numbered module text. The reply has `concept`,
`prior`, `edge` (with a strength), `restated` and `undefined` rows, each with a
verbatim quote. `apply` rejects rows whose quote is not in the text, malformed
or reused ids, edges from later modules, and cycles; it adds the rest, appends
`restated_in`, and collects undefined terms in `graph/extract/undefined.tsv`
(raw material for the forward-reference and missing-concept checks). Because
each packet lists what the graph already holds, apply a module before preparing
the next. `--only NNNN` skips a module that defines nothing (a tooling page).

Claude can work the packets as subagents; a colleague can attach each packet to
a Gemini chat ("The attached file is a task packet. Read all of it and follow
its instructions exactly.") and save the reply. All prompts live in `prompts/`
as plain text (extract, review, grade, rubric, and the shared output note), so
they can be read, edited or pasted into a Gem without touching the scripts.
Every reader of a reply (`extract.py`, `edge_audit.py`) accepts either a bare
TSV or a whole model reply with the table in a ```tsv fence.

Tested 2026-11-14 with the free Gemini (CCC Edu, default Thinking model) on
CISP 310's 0281, 0282, 0283 from an empty graph: 36 concepts against the
reference graph's 27, covering 25 of them, with 0 rows rejected. It also
produced three concepts the later audit had flagged as missing (internal binary
representation, multi-digit numbers, stacked addition), used `restated`
correctly, and reported fixed-width storage as `undefined` (0283 uses it without
defining it). Expect finer granularity than a careful human pass; the audit and
prune steps settle edges, not concept boundaries, so review the concept list.

The schema the packets fill:

`graph/concepts.tsv` — `id, module, label, definition, restated_in`:

* `id` — namespaced slug (`int.twos-complement`, `sub.call-frame`).
* `module` — the module that *defines* it. Exactly one, even when several
  discuss it: pick the one that develops it, and list the others in
  `restated_in`. That column is a finding, not bookkeeping.
* Use pseudo-modules for concepts the corpus never defines: `PRIOR` for things
  assumed from the prerequisite course, `EXT-NNNN` for a module referenced but
  not yet in the corpus. Both show up in `check.py` as "not defined by any
  module in the manifest", which is exactly the list the user wants to see.

`graph/edges.tsv` — `from, to, strength, note`, where `from` is a prerequisite of `to`
and `strength` is in [0,1] (see Step 5b; leave it empty on a first pass).
Every edge must be defensible from the text; put the reason in `note` when it is
not obvious. Prefer many small concepts to few large ones — the graph's value is
in its resolution.

Two habits that pay off:

* An author's declared prerequisites are a hypothesis. Check them against the
  prose. In practice they are usually a correct subset — real, but incomplete.
* Inline `../NNNN` cross-references are free evidence. Extract them first; they
  show which modules the author already knew were related.

Give symbol concepts a spoken-language label ("Signed interpreted value
v_s(x,w)"): a student never types the symbol, and the label is what retrieval
matches. A filled `restated_in` with no matching outgoing edge is a red flag
that the next step will catch.

## Step 5b: audit and weigh the edges

A single reading misses edges. In CISP 310 it missed v_s into the overflow
and L flags, which 0352 defines with v_s, so a tutor walking prerequisites back
from L could never reach it. `edge_audit.py` makes the second reading a
procedure that does not depend on the subject:

1. `edge_audit.py prepare --dir .` writes one packet per module to
   `graph/audit/packets/`: instructions, the module's concepts with their
   current prerequisites, every concept as a candidate, and the numbered text.
   Give each packet to a reviewer subagent (four or five modules per agent is
   fine) who writes `graph/audit/findings/NNNN.tsv`: missing edges with a
   verbatim quote, plus `module-only`, `missing-concept`, `forward` and `note`
   rows.
2. `edge_audit.py verify --dir .` checks every quote against the text and
   classifies each row: ok, implied (a path already exists), cycle, order,
   forward (pointed forward reference), unmarked (forward mention, no pointer).
   `edge_audit.py forward --dir .` is the mechanical backstop: it scans every
   module for the terms of concepts taught later and writes
   `graph/audit/forward.tsv` (see "Forward references" below).
3. `edge_audit.py grade-prepare --dir .` writes grading packets with the
   strength rubric, every existing edge (E) and every ok candidate (C). Graders
   give each a strength in [0,1] and add missing within-module edges (W).
4. `edge_audit.py grade-apply --dir .` stages `edges.proposed.tsv` and
   `alerts.md`; `--write` replaces `edges.tsv` (back it up first).
5. `edge_audit.py prune --dir .` (dry run, then `--write`) removes edges graded
   0 and edges implied by an equally strong path, logging each to
   `graph/audit/removed.tsv`. Then run `check.py`, `prereqs.py`, `render.py`
   and `notebooklm.py`.

Policy the script enforces: **edges carry a strength, not a yes/no**, in a
`strength` column (from, to, strength, note), and consumers choose their own
threshold (notebooklm.py puts edges of 0.5 and up into the tutoring path and
lists weaker ones as supporting). **Implied edges are never kept**, where
"implied" is strength-aware: a path is as strong as its weakest edge, and an
edge is implied only when another path is at least as strong as it. New edges
go in strongest first under that test, and `prune` removes existing ones
weakest first, so the strongest path between any two concepts never weakens.
Plain reachability is the wrong test: in CISP 310 it would have deleted
XOR -> L flag (1.0, L = S xor O) because a 0.4 chain also connects them. **Cycles and
teaching-order conflicts are never added**: they go to `alerts.md` with module,
line and quote, for the content developer to resolve, together with text
problems (circular or repeated definitions), existing edges graded 0, existing
redundant edges, and missing concepts. Nothing is removed automatically.

What the CISP 310 run showed, worth expecting elsewhere:

* Reviewers asked for recall over-report: they count every concept a passage
  touches (notation, checks, illustrations). Without strengths the graph would
  have more than doubled. The rubric's anchors (1.0 definitional, 0.8 core,
  0.6 substantial, 0.4 secondary, 0.2 supporting, 0 none) are what separate
  "why carry exists" from "carry written as a C function".
* Grade the existing edges too. The first reader's threshold was never
  written down; 8 of 238 had no support in the text at all.
* Calibrate: have every grader also grade one shared module to a separate file
  (`graph/audit/calib/`). Four graders agreed within 0.2 on every edge of
  CISP 310's 0352, mean spread 0.06.
* Packets must let `from` be a concept of the same module; the first version
  did not, and within-module edges went unreported.
* Cycles and order conflicts cluster around modules that explain something
  before the course teaches it (CISP 310's 0432). They are content findings,
  not graph errors.

### Forward references

Course material is not a story: foreshadowing a later idea does not help a
reader, but an explicit forward reference does. It tells the reader where the
concept is taught, whether they need it now (usually not), and when to come
back. Without one, a reader who stops at every unclear term and works back
through prerequisites (the reading habit a tutor teaches) goes into the later
module, which itself depends on the one being read, and comes back confused.

* **Detection.** Two sources. Reviewers report `forward` rows, and `edge` rows
  that run against teaching order. `edge_audit.py forward` scans the text for
  every concept's terms in modules before the one that teaches it: the label
  outside parentheses (case-insensitive, plural allowed) and a parenthesized
  acronym (exact case), or an optional `terms` column in `concepts.tsv`
  (`|`-separated) when the label is a poor search term. Fenced code and the
  Prerequisites line are skipped. Expect some everyday-word noise (CISP 310:
  "component" in early modules); a `terms` override is the fix.
* **What counts as a pointer** (checked mechanically): the later module's id,
  as a link or plain text, in the same section as the mention or in the
  introduction of an enclosing section. Section boundaries are headings, so a
  pointer at the top of "The stack" covers that section but not its sibling
  "Caller's responsibility".
* **Handling.** A forward reference is never an edge and never enters
  `edges.tsv`. Without a pointer it is alerted (`unmarked`, or `order` if the
  reviewer judged it a dependency), and the content developer either adds a
  pointer or moves the material. With a pointer it is listed for review and
  `notebooklm.py` names it on the concept's card and in the module's header, so
  the tutor says "taught later in module N" instead of stepping back.
* Suggested wording for the author: one sentence naming the module that teaches
  it and saying whether this passage needs it, e.g. CISP 310's 0432: "This
  section only states TTP's stack conventions, for reference. What a stack is
  (last in, first out) and why push and pop are written this way is explained
  in [0304](../0304). You do not need that yet to read the rest of this module;
  return to this section after 0304."

## Step 6: validate

`check.py --dir .` exits non-zero on unknown ids, duplicate ids, or a cycle, and
reports:

* **Cycles.** A cycle means a genuine modelling error or genuinely circular
  material. Resolve it by splitting the concept, not by deleting an edge.
* **Canvas ordering violations.** An edge whose source module is presented
  *after* its target. This is the finding users act on. Cluster them before
  reporting — ten violations were two root causes in the case this came from.
* **Concepts defined more than once.** Where a reference module and a teaching
  module state the same rules. Usually a content decision, not a defect: either
  trim one to a cross-reference, or make one normative and have the other cite it.

`render.py --dir .` writes both diagrams as SVG with `currentColor`, so they
work on light and dark grounds when inlined into an artifact.

## Step 7: amend the Prerequisites lines

`prereqs.py --dir .` prints, per module, the declared list against the module's
**direct predecessors** — every module supplying at least one concept it uses
directly — with the concept edges that justify each addition. `--apply` rewrites
the line in the content repo.

Three rules the script already follows, worth understanding before you trust it:

* **Direct predecessors, not a transitive reduction.** "Immediate dependencies"
  means every module that directly supplies something, even when another
  prerequisite would transitively imply it. A reduction hides real relationships.
* If you do compute a reduction for comparison, note the direction is easy to
  invert: `p` is redundant when **`p` reaches some other predecessor `q`**, which
  keeps the nearest prerequisites and drops distant ancestors. Getting it
  backwards silently keeps the roots and discards the useful ones.
* **Union with what is declared; never drop the author's own entries.**

Afterwards, verify independently rather than trusting the write: re-read the
documents and confirm they match the plan, that no `../NNNN` dangles, that the
declared prerequisite graph is itself acyclic, and that no prerequisite points at
a module appearing later in Canvas.

## Step 8: report

Publish an artifact. What earns its place:

* headline counts — concepts, edges, depth, cycles, ordering violations;
* the module-level diagram, which is legible where the full concept graph is not;
* findings ranked by what the user must act on, each naming the specific module
  and the specific fix;
* the longest chain, which shows the spine of the course better than any prose;
* a searchable table of every concept by topological level;
* the full concept graph in a scrollable panel.

Re-publish to the same URL as the course changes; the diff between versions is
itself the progress report.

## Step 9 (optional): export for NotebookLM

`notebooklm.py --dir .` writes into `notebooklm/` from the graph and `clean/`,
replacing only its own outputs (the user keeps hand-written instructions and
recorded chats in the same folder):
a `<course_name> concept map.md` with one card per concept, one source per
module (front matter stripped, `../NNNN` links spelled out as module number and
title, figures replaced by placeholders, each prefixed with where it sits in the
graph), and `chat-instructions.txt` for NotebookLM's *Configure chat* box. Set
`course_name` in `course.json`.

Cards are written for a retriever, not a reader: each one restates its module,
definition, direct prerequisites (with the edge note as "Why"), direct
dependents, restatements and full foundation, because a chunk arrives alone.
Lists use semicolons, since labels contain commas.

`--structure-only` writes a variant map with every definition removed to
`notebooklm/experiments/`. In testing it kept the tutoring path intact while
reducing how often NotebookLM credited the map with definitions; citations
follow whatever passages were retrieved, and instructions alone did not stop
the full map being cited for definitions. What made the tutor consistently
Socratic was a specific instruction naming the situation and the first move,
not a general "don't give answers" rule. Re-run after any edit to the
graph, then replace the sources in the notebook; NotebookLM does not re-read a
Markdown upload.

## Notes

* Compute Canvas position from row order in `modules.tsv`, and re-verify against
  the API after the user edits Canvas. They may fix more than you flagged, or
  half of what you flagged — both happened in the case this came from, and only
  re-reading caught it.
* A URL fix and a position fix are separate actions. Say which you mean.
* Re-check the whole Canvas module containing an edited item, not just the item.
* When a module renders something odd on the live page — leftover test scripts,
  stray markup — flag it with file and line numbers rather than fixing it; the
  content repo is the user's.
