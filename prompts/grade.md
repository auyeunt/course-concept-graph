# Edge grading packet: module {mid}, {title}

You are grading the strength of prerequisite edges in a concept dependency
graph. An edge X -> Y means a student must understand X to follow how this
module develops Y. Read the whole module text (at the end) before grading.

{rubric}
## What to write

One tab-separated table with this header line and one row per edge. No tabs
or newlines inside a field.

ref	from	to	strength	line	why

- Every E and C ref listed below gets exactly one row. Copy its ref, from and to.
  `line` is the line that best shows the dependency, or 0 if the text never
  uses X in developing Y. `why` is one sentence naming the anchor you used.
- Then add rows with ref `W` for edges between two concepts defined in this
  module that are missing from both lists below, graded the same way. Only
  report W edges of strength 0.4 or more, and never one that runs from a concept
  to itself or that would contradict an E edge's direction.

{output}

Finish with one line: how many E, C and W rows you wrote, and the grade you are
least sure of.
