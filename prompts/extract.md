You are building a concept dependency graph for a course, one module at a time
in teaching order. The modules before this one are done: their concepts are
listed below. Your job is to list the concepts THIS module defines and, for
each, the concepts it builds directly on.

## What counts as a concept

A concept is an idea the module defines, explains or establishes that a student
could later be asked about ("what is X?", "why does X hold?", "how do you do
X?"), and that a later passage or module could build on:
- a defined term, notation or symbol;
- a named rule, formula, theorem or result;
- a procedure, method or technique the module teaches;
- a distinction or classification the module draws.

Not concepts: worked examples, exercises, anecdotes and history, the module's
own outline, and ideas the module only mentions.

Granularity: if two terms are always introduced and used together, they are one
concept; if a later passage could need one without the other, they are two.
Prefer several small concepts to one large one: the graph is only as useful as
its resolution. A typical module defines 3 to 12.

## Ids and labels

- `id`: `area.short-name`, lowercase, words joined by hyphens, for example
  `int.twos-complement`. The area is a short prefix that groups related
  concepts; reuse an area from the list below when one fits. The id must not
  already be in the list.
- `label`: the name a student would say or search for, in words. For a symbol
  concept, say what it is in words and give the symbol after it, for example
  "Signed interpreted value v_s(x,w)".
- definition (the `note` column of a `concept` row): one or two sentences in the
  module's own terms, enough to recognise the idea without the module.

## Concepts from outside the course

If the module relies on something that it does not explain and that no earlier
module defines (background from a prerequisite course, general knowledge), write
a `prior` row for it, with an id starting `prior.`. Reuse an existing `prior.`
id from the list when one fits. Do not write `prior` rows for everyday words.

## Edges

An edge X -> Y means: to follow how this module introduces, explains or
justifies Y, a student must already understand X. X may be a concept from an
earlier module, a `prior` concept, or a concept this module defines earlier
than Y. Count X when the passage that develops Y
- names X or uses X's term, symbol or notation;
- applies X's rule, formula, procedure or result;
- reasons from X, or defines Y in terms of X.
Count direct use even if X is also reachable through other concepts. Do not
count X when it appears only in an exercise, when the shared word is everyday
vocabulary, or when the text uses Y to explain X (that is the reverse edge).
Give each edge a strength using the rubric below, and leave out edges of
strength 0.

{rubric}
## Other findings

- `restated`: the module defines again a concept that is already in the list.
  Do not make a new concept; write this row instead.
- `undefined`: the module uses a term, symbol or idea as if the reader knew it,
  but it is neither in the list nor defined here. It may be taught later in the
  course, or nowhere. One row per term.

## How to work

Read the whole module first. Then go through it in order and, at each place
where something is defined or established, decide whether it is a new concept,
a restatement, or an example. For each new concept, reread the passage that
develops it and ask of every term, symbol and step: which concept (from the
list, `prior`, or earlier in this module) does a student need here?

## What to write

One tab-separated table with this header line and one row per finding. No tabs
or newlines inside a field; use `-` for a field that does not apply.

kind	id	label	from	strength	line	quote	note

Every row has exactly these 8 fields, in this order. Write `-` in a field that
does not apply; never leave a field out. One row of each kind, for shape only:

concept	bio.osmosis	Osmosis	-	-	41	Osmosis is the movement of water	Movement of water across a membrane toward the higher solute concentration.
prior	prior.percent	Percentages	-	-	52	a 5% solution	Parts per hundred.
edge	bio.osmosis	-	bio.membrane	0.8	41	across a semi-permeable membrane	Core: osmosis is explained as movement through the membrane.
restated	bio.diffusion	-	-	-	30	Recall that diffusion	Repeats the earlier definition; adds nothing.
undefined	-	solute	-	-	44	the solute concentration	Seems to mean the dissolved substance.

- `concept`: `id` and `label` of a concept this module defines, in the order
  the module introduces them. `line` and `quote` locate where it is defined.
  `note` is its definition.
- `prior`: `id` and `label` of a concept from outside the course. `line` and
  `quote` show where the module relies on it. `note` is its definition.
- `edge`: `id` is the concept defined here (Y); `from` is its prerequisite (X);
  `strength` is a number from the rubric; `line` and `quote` show the passage
  developing Y using X; `note` is one sentence naming the rubric anchor.
- `restated`: `id` is the existing concept; `line`, `quote` locate it; `note`
  says whether the module adds anything.
- `undefined`: `label` is the term as written; `line`, `quote` locate its
  first use; `note` says what it seems to mean.

`quote` is always the shortest exact span (at most 200 characters) copied
verbatim from the numbered line, markup and all, without adding delimiters of
your own. Quotes are checked mechanically against the text; a row whose quote
is not found is rejected.

{output}

Finish with a two-line summary: how many rows of each kind, and the concept
boundary you are least sure of.
