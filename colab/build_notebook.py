#!/usr/bin/env python3
"""Write course_concept_graph.ipynb from the cell texts below.

Edit this file, not the notebook: run `python3 build_notebook.py` after changes.
"""
import json, pathlib

MD, CODE = "markdown", "code"

CELLS = [
(MD, """# Course concept map and AI tutor sources

This notebook turns your course readings into:

1. a **concept map**: every idea your readings teach, and which ideas each one
   builds on;
2. a list of **things to look at in your readings**: ideas used before they are
   taught, circular definitions, ideas used but never explained;
3. **sources for a NotebookLM tutor** that guides students back through the
   ideas a concept rests on, instead of handing them answers.

You do not need to write code. Each step below is a box: fill in the form if it
has one, then press its ▶ button (or click in it and press Shift+Enter). Run the
steps in order. You can stop after any step and come back later: your work is
saved in your Google Drive.

The [faculty guide](https://github.com/auyeunt/course-concept-graph/blob/main/guide/faculty-guide.md) explains what each
step does and what to check. Kit, license and source: [github.com/auyeunt/course-concept-graph](https://github.com/auyeunt/course-concept-graph)."""),

(CODE, """#@title Step 1 · Set up your project { display-mode: "form" }
#@markdown Give your course a short name. It becomes a folder in your Google Drive
#@markdown (My Drive › Concept graph › *name*), where every step saves its work.
COURSE_NAME = "My course"  #@param {type:"string"}
#@markdown Keep your work in Google Drive (recommended), or only for this session.
SAVE_IN = "Google Drive"  #@param ["Google Drive", "This session only (lost when you close it)"]
#@markdown Where the kit comes from. Leave as is unless told otherwise.
KIT = "https://github.com/auyeunt/course-concept-graph"  #@param {type:"string"}

import os, pathlib, shutil, subprocess, sys
if SAVE_IN.startswith("Google"):
    from google.colab import drive
    drive.mount("/content/drive")
    base = pathlib.Path("/content/drive/MyDrive/Concept graph")
else:
    base = pathlib.Path("/content/Concept graph")
kit_dir = pathlib.Path("/content/kit")
if KIT.endswith(".zip") and pathlib.Path(KIT).exists():
    shutil.rmtree(kit_dir, ignore_errors=True)
    shutil.unpack_archive(KIT, kit_dir)
elif KIT.startswith("http"):
    if kit_dir.exists():
        subprocess.run(["git", "-C", str(kit_dir), "pull", "-q"])
    else:
        subprocess.run(["git", "clone", "-q", KIT, str(kit_dir)], check=True)
elif pathlib.Path(KIT).is_dir():
    kit_dir = pathlib.Path(KIT)
scripts = next(kit_dir.rglob("kit.py")).parent
sys.path.insert(0, str(scripts))
if shutil.which("pdftotext") is None:
    subprocess.run("apt-get -qq install -y poppler-utils > /dev/null", shell=True)
import importlib, kit
importlib.reload(kit)
p = kit.Project(base / COURSE_NAME)
p.setup(COURSE_NAME)"""),

(MD, """## Step 2 · Add your readings

Put your readings in the **readings** folder Step 1 printed (open Google Drive
in another tab: My Drive › Concept graph › *your course* › readings), or tick
the box below to upload them from your computer.

- **Formats:** Word (.docx), PDF, Markdown (.md), plain text (.txt), web pages
  (.html), OpenDocument (.odt). For a Google Doc, use File › Download ›
  Microsoft Word first. Scanned PDFs (pictures of pages) do not work.
- **Order matters.** Students meet the readings in the order of their file
  names, so number them: `01 Introduction.docx`, `02 Cells.pdf`, …
- **Units (optional):** put each unit's readings in a subfolder (`01 Unit
  one/`, `02 Unit two/`); the subfolders are ordered by name too.
- **One reading per file**, about the size of a chapter section or a lesson.
  Very long files (a whole textbook) give poor results; split them first.

You can run this step again after adding or renaming files. A reading keeps its
id (m01, m02, …) as long as its file name stays the same."""),

(CODE, """#@title Step 2 · Import the readings { display-mode: "form" }
UPLOAD_FROM_MY_COMPUTER = False  #@param {type:"boolean"}
if UPLOAD_FROM_MY_COMPUTER:
    from google.colab import files
    for name, data in files.upload().items():
        (p.dir / "readings" / name).write_bytes(data)
report = p.import_readings()"""),

(MD, """## Step 3 · Find the concepts in each reading

A Gemini model reads one reading at a time, in your teaching order, and lists
the concepts it teaches and what each builds on. Every quote it gives is checked
word for word against your text; anything that does not check out is rejected.

**Automatic** (below) uses the Gemini model built into Colab. It is fast and
needs nothing from you, but it is a "Flash" model that finds fewer connections
than the Gemini app's *Thinking* model.

**By hand** (the two boxes after it) uses the Gemini app instead: you download a
packet, attach it in a Gemini chat, and bring the answer back. Slower, more
thorough. You can mix the two: automatic for most readings, by hand for the
hardest ones."""),

(CODE, """#@title Step 3 · Automatic { display-mode: "form" }
MODEL = "google/gemini-3.8-flash"  #@param ["google/gemini-3.8-flash", "google/gemini-3.6-flash", "google/gemini-3.5-flash-lite"]
#@markdown How many readings to do now (0 = all that are left).
HOW_MANY = 0  #@param {type:"integer"}
p.extract(kit.colab_ask(MODEL), limit=HOW_MANY or None)"""),

(CODE, """#@title Step 3 · By hand, part A: get the next packet { display-mode: "form" }
#@markdown Downloads the packet for the next reading. Then, in
#@markdown [gemini.google.com](https://gemini.google.com): new chat, choose the
#@markdown *Thinking* model, attach the file with **+**, and send:
#@markdown *The attached file is a task packet. Read all of it and follow its instructions exactly.*
#@markdown When it answers, use **Download** on the table it gives (the ⤓ icon on
#@markdown the code box), then run part B.
from google.colab import files
nxt = p.next_extract_packet()
if nxt is None:
    print("All readings have concepts.")
else:
    current_reading, packet = nxt
    print(f"Packet for reading {current_reading}: {packet.name}")
    files.download(str(packet))"""),

(CODE, """#@title Step 3 · By hand, part B: bring back Gemini's answer { display-mode: "form" }
#@markdown Choose the file you downloaded from Gemini (any name is fine).
from google.colab import files
up = files.upload()
for name, data in up.items():
    p.apply_extract_reply(current_reading, data.decode("utf-8", "replace"))
print("Now run part A again for the next reading.")"""),

(CODE, """#@title Look at the concepts found so far { display-mode: "form" }
#@markdown Read this list before going on: the later steps check the connections
#@markdown between concepts, but not where one concept ends and the next begins.
#@markdown To change a concept: Files panel (folder icon, left) › drive › MyDrive ›
#@markdown Concept graph › your course › graph, double-click concepts.tsv. Keep the tabs.
import pandas as pd
c = pd.read_csv(p.g / "concepts.tsv", sep="\\t", dtype=str, quoting=3).fillna("")
pd.set_option("display.max_colwidth", 120)
display(c[["module", "id", "label", "definition"]])"""),

(CODE, """#@title (Optional) Rebuild the concept list from the saved answers { display-mode: "form" }
#@markdown Use after correcting one of Gemini's answers by hand (in
#@markdown graph/extract/m03.txt and so on), or after updating the kit. Gemini is
#@markdown not asked again; the old lists are kept as .bak files.
p.reapply_extract()"""),

(MD, """## Step 4 · Check and weigh the connections

A second reading of every text, looking for connections the first pass missed,
then a grading pass that gives each connection a strength from 0 to 1
(1 = the concept cannot even be stated without the other; 0.2 = only notation
or an example). Connections that add nothing, because a path at least as
strong already links the two concepts, are removed and logged.

This step is also where the kit looks for **ideas used before they are taught**.
Expect a few; they are the most useful thing it finds."""),

(CODE, """#@title Step 4 · Automatic { display-mode: "form" }
MODEL = "google/gemini-3.8-flash"  #@param ["google/gemini-3.8-flash", "google/gemini-3.6-flash", "google/gemini-3.5-flash-lite"]
p.audit(kit.colab_ask(MODEL))"""),

(CODE, """#@title Step 4 · By hand { display-mode: "form" }
#@markdown Two rounds: STAGE = review, then STAGE = grade. Each round:
#@markdown 1. Run with ACTION = get packets: a zip of packets downloads.
#@markdown 2. Give each packet to Gemini as in Step 3, and save each answer with
#@markdown    the reading id in its name (m03.txt, …).
#@markdown 3. Run with ACTION = bring back answers and choose all the files.
#@markdown After the grade round, run ACTION = finish.
STAGE = "review"  #@param ["review", "grade"]
ACTION = "get packets"  #@param ["get packets", "bring back answers", "finish"]
from google.colab import files
if ACTION == "get packets":
    z, ids = p.audit_packets(STAGE)
    print(f"{len(ids)} packets: {', '.join(ids) or 'none needed'}")
    if ids:
        files.download(str(z))
elif ACTION == "bring back answers":
    p.save_audit_replies(STAGE, files.upload())
else:
    p.audit_finish()"""),

(CODE, """#@title Step 5 · Results { display-mode: "form" }
from IPython.display import Markdown, SVG, display
alerts = p.results()
for name, title in (("modules.svg", "How the readings depend on each other"),
                    ("concepts.svg", "The concept map")):
    f = p.g / name
    if f.exists():
        display(Markdown(f"### {title}"))
        display(SVG(filename=str(f)))
if alerts.exists():
    display(Markdown("### Things to look at in your readings\\n\\n" + alerts.read_text()))"""),

(MD, """## Step 6 · Sources for a NotebookLM tutor

The next box makes a zip of sources: one concept map and one file per reading,
each written so that NotebookLM can find how ideas connect, plus a short reading,
"AI literacy for higher ed students", that the tutor uses when a student asks
why it will not just give the answer. In
[notebooklm.google.com](https://notebooklm.google.com) (now also called Gemini
Notebook):

1. Create a notebook and add every file from the zip as a source.
2. Open **Configure chat** and paste the tutor instructions printed below
   (or your own; see the faculty guide).
3. Try it yourself as a student before sharing it: ask "What is …?" about a
   concept from the middle of the course, then ask it to just give you the
   answer."""),

(CODE, """#@title Step 6 · Make the NotebookLM sources { display-mode: "form" }
from google.colab import files
z = p.export()
files.download(str(z))
print("\\nTutor instructions for Configure chat:\\n")
print((p.dir / "notebooklm" / "chat-instructions.txt").read_text())"""),
]


def cell(kind, text):
    lines = text.split("\n")
    src = [l + "\n" for l in lines[:-1]] + [lines[-1]]
    if kind == MD:
        return {"cell_type": "markdown", "metadata": {}, "source": src}
    return {"cell_type": "code", "metadata": {"cellView": "form"}, "execution_count": None,
            "outputs": [], "source": src}


nb = {"nbformat": 4, "nbformat_minor": 0,
      "metadata": {"colab": {"provenance": [], "toc_visible": True},
                   "kernelspec": {"name": "python3", "display_name": "Python 3"},
                   "language_info": {"name": "python"}},
      "cells": [cell(k, t) for k, t in CELLS]}
out = pathlib.Path(__file__).with_name("course_concept_graph.ipynb")
out.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
print(f"wrote {out}")
