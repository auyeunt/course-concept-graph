# From course readings to a concept map and an AI tutor

A guide for faculty. No programming and no prior experience with AI tools is
needed. It goes with the Colab notebook `colab/course_concept_graph.ipynb` in
this kit.

## What you get

Give the kit your course readings, in the order students meet them. It gives
back three things.

1. **A concept map.** Every idea your readings teach, and for each one, the
   ideas it builds on directly, each connection weighted from 0 to 1 by how much
   it matters. You can see it as a diagram and as a table.
2. **A list of things to look at in your readings.** Ideas used in one reading
   but only taught in a later one; pairs of ideas each explained in terms of the
   other; ideas a reading relies on but no reading explains; ideas defined twice.
   In the course this kit was built on, this list was the most useful result: it
   found a reading that explained four ideas a later reading teaches, and a
   missing link that left a tutor unable to explain one of the course's key
   ideas.
3. **Sources for a NotebookLM tutor.** One file per reading plus a concept map
   written for NotebookLM, so that a tutor notebook can do what a good tutor
   does: when a student is stuck on an idea, step back to the ideas it rests on,
   one at a time, until it finds what the student does understand, then work
   forward again.

## What you need

- Your readings as files: Word, PDF (with real text, not scanned pages),
  Markdown, plain text or web pages. One file per reading, about the size of a
  lesson or a chapter section.
- A Google account with Colab, Gemini and NotebookLM. The California Community
  Colleges accounts for faculty include all three.
- Time: the machine work for a 20-reading course is one to three hours, mostly
  waiting. Your own review takes as long as you give it; plan on an hour for the
  concept list and an hour for the list of things to look at.

**Privacy and copyright.** On a Los Rios account, Gemini states that "chats
aren't used to improve our models"; check what your own district's account
says. The kit sends your readings to Gemini, so use material you have the right
to use this way (your own, open educational resources, or material your
license allows). A NotebookLM notebook is private until you share it.

## How it works, in plain words

An AI model does the reading; small programs check everything it says.

- The model reads one reading at a time and lists the concepts it teaches and
  the concepts each one builds on. For every claim it must quote the exact words
  from your reading that support it. A program then looks for that quote in your
  text, and any claim whose quote is not there is rejected. In our tests no
  claim was ever invented, but the check is what makes that safe to rely on.
- A second, separate reading looks only for connections the first one missed,
  and a third gives each connection a strength. The programs then remove
  connections that add nothing (another path already links the two ideas at
  least as strongly) and log every removal so you can put any back.
- The programs also check what the model cannot: that nothing is taught in
  circles, and that no reading depends on something taught later.
- Nothing you wrote is changed. The kit only reports; you decide.

## Step by step

Open the notebook from the kit's page,
[github.com/auyeunt/course-concept-graph](https://github.com/auyeunt/course-concept-graph)
("Open the notebook in Google Colab"), signed in with your college Google
account. Each step is a box with a ▶ button. Run them in order. Your work is
saved in Google Drive, in My Drive › Concept graph › *your course*, so you can
stop after any step and continue another day: run Step 1 again first, then
carry on.

### Step 1: set up

Type a short course name and press ▶. Two questions come up the first time:

- "Warning: This notebook was not authored by Google." Colab says this about
  every notebook that comes from GitHub. Choose **Run anyway**. (The code is
  public in the kit's repository if you or your IT staff want to read it.)
- Permission to use your Google Drive. Allow it: this is how your work is
  saved between sessions.

The step prints the folder it made. You do not need Colab's "Copy to Drive":
your work is saved in the course folder, and the notebook itself is always
opened fresh from the kit's page.

### Step 2: add your readings

Put the files in the `readings` folder inside your course folder (or tick the
upload box and choose them from your computer), then press ▶.

- **Name the files in teaching order**: `01 Introduction.docx`,
  `02 Cells.pdf`, and so on. The kit takes the order from the names.
- To group readings into units, put each unit in a subfolder named in order
  (`01 Foundations`, `02 Applications`).
- For a Google Doc, download it as Word first (File › Download).
- The step prints each reading with its id (m01, m02, …) and word count. A
  warning such as "very little text" usually means a scanned PDF or a slide
  deck: replace it with a text version.

You can add or rename readings later and run this step again. A reading keeps
its id as long as its file name stays the same.

### Step 3: find the concepts

Choose **Automatic** (Colab's built-in Gemini does every reading in a row) or
**By hand** (you take each reading's packet to the Gemini app yourself; see
"Automatic or by hand?" below). Either way the readings are done in teaching
order, because each one is read with the list of concepts found so far.

For each reading the step reports how many concepts, connections and
outside-knowledge items it accepted, and anything it rejected and why.

**Then read the concept list** (the "Look at the concepts" box). This is the one
place your judgment cannot be replaced by a later check. Look for:

- **Granularity.** A concept is one idea a student could be asked about. The
  model tends to split finely (in our test, 36 concepts where a careful reader
  made 27). That is usually fine; merge only true duplicates.
- **Missing ideas.** Something a reading clearly teaches that is not listed.
- **Prior knowledge** (ids starting `prior.`). Things the readings assume from
  outside the course. Is each one really assumed, or should a reading teach it?
- **Undefined terms** (`graph/extract/undefined.tsv`). Terms a reading uses as
  if the student knew them. Some are taught later; some are taught nowhere.

To edit, open the Files panel (folder icon on the left), go to
`drive/MyDrive/Concept graph/your course/graph/`, and double-click
`concepts.tsv`. Keep the columns separated by tabs.

### Step 4: check and weigh the connections

Again automatic or by hand. Three things happen:

1. **A second reading** of each text, looking only for connections the first
   pass missed, and for any use of an idea the course teaches later.
2. **Grading.** Each connection gets a strength:

   | strength | meaning |
   |---|---|
   | 1.0 | the idea cannot even be stated without the other |
   | 0.8 | its central explanation rests on the other |
   | 0.6 | the other carries a real step, or the worked example that teaches it |
   | 0.4 | used, but the idea could be taught without it with a little rewording |
   | 0.2 | only notation, a check, an illustration or a side remark |

   The tutor uses connections of 0.5 and up to decide what to ask a stuck
   student about; weaker ones are mentioned as supporting.
3. **Pruning.** A connection is removed when another chain of connections
   already links the two ideas at least as strongly. (A chain is only as strong
   as its weakest link, so a strong direct connection is never removed in favour
   of a weak detour.) Every removal is logged in `graph/audit/removed.tsv`.

### Step 5: results

The step shows two diagrams (how the readings depend on each other, and the full
concept map) and the list of **things to look at**, from
`graph/audit/alerts.md`. Each section of that list, and what to do about it:

- **Teaching order.** A reading depends on an idea that a later reading
  teaches. Either move the material, or teach enough of the idea where it is
  first needed.
- **Forward mentions without a pointer.** A reading names an idea that a later
  reading teaches, without saying so. Foreshadowing does not help a reader, but
  a forward reference does: one sentence that says where the idea is taught and
  whether the reader needs it now. For example:

  > This section only states the conventions, for reference. What a stack is
  > and why push and pop are written this way is explained in module 0304. You
  > do not need that yet to read the rest of this module; return to this section
  > after 0304.

  Once a reading says where an idea is taught (by naming that reading), the
  kit lists it as an acknowledged forward reference instead, and the tutor
  tells a student "that comes later" instead of digging into it.
- **Cycles.** Two ideas each explained in terms of the other. Usually one of
  them needs splitting, or one is explained before it is taught.
- **Notes on the text.** Circular or repeated definitions the reader spotted.
- **Ideas with no concept.** Something a reading develops that the concept list
  lacks. Add it in Step 3's table if it matters.
- **Connections with no support.** Connections the grader found no evidence for.

Some items will be wrong, especially in the forward-mention list (an everyday
word that happens to match a concept's name). That is expected: it is a list of
places to look, not a list of errors.

### Step 6: the NotebookLM tutor

The step downloads a zip and prints a set of tutor instructions.

1. In [notebooklm.google.com](https://notebooklm.google.com), create a
   notebook and add every file from the zip as a source.
2. Open **Configure chat** and paste the instructions. Adjust them to your
   course; the ones that worked best in our tests are below.
3. Before sharing, use it as a student would: ask "What is …?" about a concept
   from the middle of the course, give a wrong answer on purpose, and see
   whether it asks you how you got it.

Instructions that made the biggest difference in our tests:

- *First reply about a concept.* "When a student asks what a concept is, how it
  works, or why it is needed, do not state its definition, formula or mechanism
  in your first reply. Instead, name the concepts it builds directly on (from
  the concept map), then ask one question that checks the first of them."
  General rules such as "never give the final answer" were ignored for concept
  questions; this specific one was followed every time.
- *During the conversation.* When a student's answer is wrong, ask how they got
  it before correcting it. When two of the student's statements contradict each
  other, quote both and ask which is right. When a step is a calculation the
  readings cover, ask the student to do it.
- *Reading help.* Encourage the student to stop at the first unclear term and
  look it up, keeping track of where they were, and to treat an idea the map
  marks "mentioned before it is taught" as something to note and come back to.

Two things instructions cannot control: NotebookLM's suggested follow-up
questions sometimes give the answer away, and there is a daily limit on chats.

## Automatic or by hand?

We compared Gemini against a reference built by a stronger model, on three
readings of a computer architecture course.

| | Colab automatic (Flash) | Gemini app, by hand (Thinking) |
|---|---|---|
| Your effort | press ▶ and wait | about 3 minutes of yours per packet |
| Model time per packet | 3 to 4 minutes | 1 to 3 minutes |
| Quotes invented | none | none |
| Concepts found in one reading (0283) | 7 and 13 (two runs) | 11 |
| Connections found in that reading | 39 and 40 | 53 |
| Connections found by the second reading (0432) | 9 | 19 |
| Ideas-taught-later reported (0432) | 17 | 24 |
| Strength grades | close to the reference | close to the reference |

The Flash model is as careful as the Thinking model (nothing invented) but finds
fewer connections, about half to three quarters as many, and varies more from
run to run.

**Colab's built-in model has a usage allowance.** In our test it was used up
after about ten packets with Colab's default settings; the kit now asks for
shorter answers, which stretches it further, and stops with a plain message
when it runs out. Everything finished so far is kept: run the step again later
and it carries on. A 20-reading course needs about 60 packets in all (three per
reading), so plan to spread the automatic run over a day, or do part by hand.

A reasonable plan: run everything automatically, then redo by hand the
readings whose results look thin (few connections, or a concept list that
misses something you know is there).

## When something goes wrong

- **"Reply had no usable table".** The model answered without the table. The
  automatic mode asks once more by itself; by hand, start a new Gemini chat and
  send the packet again.
- **Rejected rows.** A claim whose quote is not in the reading, or that points
  to a later reading, is left out and reported. A few per reading are normal.
- **Model or quota errors.** The automatic mode waits and retries. If it keeps
  failing, continue later: every finished reading is saved, and the step
  carries on where it stopped.
- **Fixing an answer by hand.** Every answer Gemini gave is saved
  (`graph/extract/m03.txt` and so on). Correct one in the Files panel, then run
  "(Optional) Rebuild the concept list from the saved answers": the list is
  rebuilt without asking Gemini again.
- **Redoing one reading's concepts.** Delete its line(s) from
  `graph/concepts.tsv` and its files `graph/extract/mNN.*`, then run Step 3
  again. (Connections into its concepts are removed with them.)
- **Starting over.** Delete the course folder's `graph` folder and run from
  Step 3. Your readings are not touched.

## Words used in this guide

- **Concept**: one idea a reading teaches that a student could be asked about.
- **Connection** (edge): concept A → concept B means a student needs A to follow
  how the reading develops B.
- **Strength**: how much B depends on A, from 0 to 1.
- **Prior knowledge**: something the readings assume from outside the course.
- **Forward reference**: a mention of an idea before the reading that teaches
  it, together with a pointer to that reading.
- **Packet**: one file holding the instructions for the model and one reading's
  text. The by-hand mode is just carrying packets to Gemini and answers back.
