You are auditing a concept dependency graph built from course modules. The graph
was extracted by an earlier reader, who is known to have missed edges. Your job
is recall: find prerequisite edges INTO this module's concepts that the text
supports but the graph lacks. Earlier reviewers missed about a third of the real
edges; expect to find several.

## What an edge means

An edge X -> Y means: to follow how this module introduces, explains or
justifies Y, a student must already understand X. The evidence must be in this
module's own text. Count X when the passage that develops Y
- names X or uses X's term, symbol or notation;
- applies X's rule, formula, procedure or result;
- reasons from X, or defines Y in terms of X.
Count it even if X comes from a much earlier module, and even if X is already
reachable indirectly through other edges: direct use is what matters.

Do not count X when it appears only in an exercise or quiz question; when the
shared word is everyday vocabulary rather than the concept; or when the text
uses Y to explain X (that is the reverse edge).

## Concepts taught LATER: the most often missed findings

Some candidate lists below are marked "taught LATER than this module". A module
that uses one of those concepts is explaining something before the course
teaches it. That is exactly what the author needs to hear about, and it is the
finding reviewers most often leave out because it looks like a mistake in the
graph. Report it; do not skip it:
- if the passage cannot be followed without the later concept, write an `edge`
  row (it will be flagged as a teaching-order problem, not added blindly);
- if the passage only mentions or names it, write a `forward` row.

## How to read

Read the whole module before writing anything. Then:
1. For each concept the module defines, find the passage that develops it and
   ask of every term, symbol and step in that passage: which concept in the
   lists below does a student need here?
2. Then go through every concept in the "taught LATER" lists, one by one, and
   search the module for its term, symbol, abbreviation or notation (for
   example an abbreviation such as PC, or a symbol written in the text). Report
   each one you find, as `edge` or `forward`.

## What to write

One tab-separated table with this header line and one row per finding. No tabs
or newlines inside a field.

kind	from	to	line	quote	why

- kind `edge`: a missing edge. `from` is any id in the lists below (a concept
  defined earlier in this same module counts), `to` is an id defined in this
  module, `line` is the line number of the quote, `quote` is the shortest exact
  span (at most 200 characters) copied verbatim from that line, markup and all,
  without adding delimiters of your own, that shows the development of `to`
  using `from`. `why` is one sentence.
- kind `forward`: the module uses or mentions a concept from a list marked
  "taught LATER", and no concept here needs it to be followed. `from` is that
  concept's id, `to` is the concept here whose passage mentions it (or `-`),
  `line` and `quote` locate it, `why` says whether the text tells the reader
  where it is taught.
- kind `module-only`: the module clearly relies on an earlier concept, but no
  concept defined here depends on it (for example a worked example). `to` is `-`.
- kind `missing-concept`: the module develops an idea that is not in the
  "defined here" list at all. `from` is `-`, `to` is a short proposed label,
  `why` says what it is and what it depends on.
- kind `note`: a problem in the text itself that no edge can express, such as
  two terms defined in terms of each other, or a concept defined again that an
  earlier module already defines. `from` and `to` are the ids or terms involved
  (or `-`), `line` and `quote` locate it, `why` says what is wrong.

Report only edges that are NOT already listed as current prerequisites. If you
find nothing, give the header line alone.

{output}

Finish with a two-line summary: how many rows of each kind, and the one finding
you are least sure of.
