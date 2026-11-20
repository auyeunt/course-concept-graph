"""Driver for the course-concept-graph kit, used by the Colab notebook.

Everything here calls the same scripts and prompts a person or Claude would
use; it only adds what a notebook needs: a project folder, reading import, and
a loop that sends packets to a model and files the replies where the scripts
expect them.

    import kit
    p = kit.Project("/content/drive/MyDrive/Concept graph/BIO 300")
    p.setup("BIO 300")                 # once
    p.import_readings()                # after putting files in readings/
    p.extract(ask)                     # ask(prompt) -> reply text
    p.audit(ask)
    p.results()
    p.export()

`ask` is any function from prompt text to reply text: Colab's built-in Gemini
(see colab_ask), or a manual round trip through the Gemini app (see the
notebook's manual cells).
"""
import csv, json, pathlib, re, shutil, subprocess, sys, time

SCRIPTS = pathlib.Path(__file__).resolve().parent
READABLE = {".md", ".markdown", ".txt", ".docx", ".odt", ".rtf", ".html", ".htm", ".pdf"}


class OutOfQuota(Exception):
    """The model's free allowance is used up for now."""


def colab_ask(model="google/gemini-3.8-flash", tries=3, max_tokens=(16000, 32000)):
    """A function prompt -> reply using Colab's built-in Gemini.

    Colab's own ai.generate_text reserves the model's whole output limit
    against the free allowance, which runs out after a handful of packets. So
    this makes the same request with a smaller max_tokens, raising it only if a
    reply was cut off. Falls back to ai.generate_text if Colab changes."""
    from google.colab import ai
    try:
        from openai import OpenAI
        client = OpenAI(base_url=f"{ai._get_model_proxy_host()}/models/openapi",
                        api_key=ai._get_model_proxy_token())
    except Exception:
        client = None

    def once(prompt, limit):
        if client is None:
            return ai.generate_text(prompt, model_name=model), "stop"
        r = client.chat.completions.create(
            model=model, max_tokens=limit,
            messages=[{"role": "user", "content": prompt}])
        return r.choices[0].message.content or "", r.choices[0].finish_reason

    def ask(prompt):
        for n in range(tries):
            try:
                for limit in max_tokens:
                    text, why = once(prompt, limit)
                    if why != "length":
                        return text
                    print(f"    reply cut off at {limit} tokens; asking again with more room")
                return text
            except Exception as e:
                msg = str(e)
                if "quota" in msg.lower() or "403" in msg:
                    raise OutOfQuota(msg) from None
                if n == tries - 1:
                    raise
                print(f"    model error ({msg[:120]}); retrying in {30 * (n + 1)} s")
                time.sleep(30 * (n + 1))
    return ask


QUOTA_MSG = ("\nColab's free Gemini allowance is used up for now. Everything finished so "
             "far is saved.\nRun this step again later (an hour or so), or continue "
             "by hand with the Gemini app.")


class Project:
    def __init__(self, folder):
        self.dir = pathlib.Path(folder).expanduser()
        self.g = self.dir / "graph"

    # ---------------------------------------------------------------- setup
    def setup(self, course_name):
        for d in ("readings", "clean", "graph"):
            (self.dir / d).mkdir(parents=True, exist_ok=True)
        cj = self.dir / "course.json"
        if not cj.exists():
            cj.write_text(json.dumps({
                "course_name": course_name,
                "repo": str(self.dir / "readings"),
                "module_files": [],
                "pages_base": "",
                "canvas_course": "",
                "id_pattern": r"m\d{2,3}",
                "unit_label": "Unit",
                "order_source": "the reading list",
            }, indent=2) + "\n")
        for name, head in (("concepts.tsv", "id\tmodule\tlabel\tdefinition\trestated_in"),
                           ("edges.tsv", "from\tto\tstrength\tnote")):
            f = self.g / name
            if not f.exists():
                f.write_text(head + "\n")
        print(f"Project folder: {self.dir}")
        print(f"Put your readings in: {self.dir / 'readings'}")

    def run(self, script, *args, quiet=False):
        r = subprocess.run([sys.executable, str(SCRIPTS / script), *args, "--dir", str(self.dir)],
                           capture_output=True, text=True)
        out = (r.stdout + r.stderr).strip()
        if not quiet and out:
            print(out)
        if r.returncode:
            raise RuntimeError(f"{script} {' '.join(args)} failed:\n{out}")
        return out

    # ------------------------------------------------------------- readings
    def import_readings(self):
        """Convert readings/ into clean/mNN.md and write modules.tsv.

        Teaching order is the order of the file names (number them: "01 Cells.docx",
        "02 Membranes.pdf"). Files in a subfolder belong to a unit named after the
        subfolder; subfolders are ordered by name too. A reading keeps its id
        across re-imports, so the graph survives adding or renaming files only if
        the file name is unchanged; ids are recorded in readings.tsv.
        """
        src = self.dir / "readings"
        files = sorted([f for f in src.rglob("*") if f.is_file() and not f.name.startswith(".")],
                       key=lambda f: [p.lower() for p in f.relative_to(src).parts])
        skipped = [f for f in files if f.suffix.lower() not in READABLE]
        files = [f for f in files if f.suffix.lower() in READABLE]
        idmap_f = self.dir / "readings.tsv"
        idmap = {}
        if idmap_f.exists():
            for row in csv.DictReader(open(idmap_f), delimiter="\t"):
                idmap[row["file"]] = row["id"]
        used = set(idmap.values())
        n = 1
        rows, report = [], []
        for f in files:
            rel = str(f.relative_to(src))
            if rel not in idmap:
                while f"m{n:02d}" in used:
                    n += 1
                idmap[rel] = f"m{n:02d}"
                used.add(idmap[rel])
            mid = idmap[rel]
            unit = f.relative_to(src).parts[0] if len(f.relative_to(src).parts) > 1 else ""
            title = re.sub(r"^\s*\d+[\s._-]*", "", f.stem).strip() or f.stem
            text, warn = to_markdown(f)
            body = f'---\ntitle: "{title.replace(chr(34), chr(39))}"\n---\n\n{text.strip()}\n'
            (self.dir / "clean" / f"{mid}.md").write_text(body)
            words = len(text.split())
            if words < 200 and not warn:
                warn = "very little text; is it a scanned PDF or a slide deck?"
            rows.append((mid, unit, title))
            report.append((mid, title, words, warn))
        with open(self.dir / "modules.tsv", "w") as fh:
            fh.write("# Readings in teaching order: id, unit, title, status. "
                     "Written by kit.import_readings from readings/.\n")
            for mid, unit, title in rows:
                fh.write(f"{mid}\t{unit}\t{title}\tpublished\n")
        with open(idmap_f, "w") as fh:
            fh.write("id\tfile\n")
            for rel, mid in sorted(idmap.items(), key=lambda kv: kv[1]):
                fh.write(f"{mid}\t{rel}\n")
        for mid, title, words, warn in report:
            print(f"  {mid}  {words:6} words  {title}" + (f"   <- {warn}" if warn else ""))
        for f in skipped:
            print(f"  skipped {f.name}: not a format this kit reads "
                  "(save Google Docs as .docx or .md first)")
        print(f"{len(rows)} readings, in this teaching order.")
        return report

    # ----------------------------------------------------------- the model
    def _send(self, packet, reply_path, ask, label):
        t = time.time()
        print(f"  {label}: asking the model (usually 1 to 5 minutes)...", flush=True)
        reply = ask(packet.read_text())
        reply_path.parent.mkdir(parents=True, exist_ok=True)
        reply_path.write_text(reply)
        print(f"  {label}: reply in {time.time() - t:.0f} s")
        return reply

    def extract(self, ask, limit=None):
        """Extract concepts, one reading at a time in teaching order."""
        try:
            self._extract(ask, limit)
        except OutOfQuota:
            print(QUOTA_MSG)

    def _extract(self, ask, limit):
        done = 0
        while limit is None or done < limit:
            out = self.run("extract.py", "prepare", quiet=True)
            m = re.search(r"packets/(\S+)\.md", out)
            if not m:
                print("All readings have concepts.")
                break
            mid = m.group(1)
            packet = self.g / "extract" / "packets" / f"{mid}.md"
            reply = self.g / "extract" / f"{mid}.txt"
            for attempt in (1, 2):
                self._send(packet, reply, ask, f"{mid} concepts")
                try:
                    res = self.run("extract.py", "apply", mid, quiet=True)
                    break
                except RuntimeError as e:
                    if attempt == 2:
                        raise
                    print(f"  {mid}: reply had no usable table; asking again")
            print("    " + "\n    ".join(l for l in res.splitlines() if l.startswith(("accepted", "  "))))
            self.run("extract.py", "apply", mid, "--write", quiet=True)
            done += 1

    def reapply_extract(self):
        """Rebuild concepts.tsv and edges.tsv from the saved extraction replies,
        in teaching order, without asking the model again (after fixing a reply
        by hand, or after a kit update). The old files are kept as *.bak."""
        for name in ("concepts.tsv", "edges.tsv"):
            f = self.g / name
            if f.exists():
                shutil.copy(f, f.with_suffix(".tsv.bak"))
                f.write_text(f.read_text().splitlines()[0] + "\n")
        ex = self.g / "extract"
        for m in ex.glob("*.done"):
            m.unlink()
        order = [l.split("\t")[0] for l in (self.dir / "modules.tsv").read_text().splitlines()
                 if l.strip() and not l.startswith("#")]
        for mid in order:
            if (ex / f"{mid}.txt").exists() or (ex / f"{mid}.tsv").exists():
                res = self.run("extract.py", "apply", mid, quiet=True)
                print(f"  {mid}: " + next((l for l in res.splitlines() if l.startswith("accepted")), res))
                self.run("extract.py", "apply", mid, "--write", quiet=True)

    def audit(self, ask, redo=False):
        """Second reading for missed edges, then strength grading, then pruning."""
        try:
            self._audit(ask, redo)
        except OutOfQuota:
            print(QUOTA_MSG)

    def _audit(self, ask, redo):
        self.run("edge_audit.py", "prepare", quiet=True)
        for p in sorted((self.g / "audit" / "packets").glob("*.md")):
            r = self.g / "audit" / "findings" / f"{p.stem}.txt"
            if redo or not (r.exists() or r.with_suffix(".tsv").exists()):
                self._send(p, r, ask, f"{p.stem} review")
        self.run("edge_audit.py", "verify")
        self.run("edge_audit.py", "grade-prepare", quiet=True)
        for p in sorted((self.g / "audit" / "grade-packets").glob("*.md")):
            r = self.g / "audit" / "grades" / f"{p.stem}.txt"
            if redo or not (r.exists() or r.with_suffix(".tsv").exists()):
                self._send(p, r, ask, f"{p.stem} grading")
        self.audit_finish()

    def audit_finish(self):
        """Apply the grades, prune implied edges, scan for forward references."""
        shutil.copy(self.g / "edges.tsv", self.g / "audit" / "edges.before-audit.tsv")
        self.run("edge_audit.py", "grade-apply", "--write")
        self.run("edge_audit.py", "prune", "--write")
        self.run("edge_audit.py", "forward")
        self.run("edge_audit.py", "grade-apply", quiet=True)  # refresh alerts.md

    # ------------------------------------------- manual round trips (Gemini app)
    def next_extract_packet(self):
        """Prepare the next reading's extraction packet; (id, path) or None."""
        out = self.run("extract.py", "prepare", quiet=True)
        m = re.search(r"packets/(\S+)\.md", out)
        if not m:
            return None
        return m.group(1), self.g / "extract" / "packets" / f"{m.group(1)}.md"

    def apply_extract_reply(self, mid, text):
        """File a reply for reading `mid`, check it, and add it to the graph."""
        (self.g / "extract" / f"{mid}.txt").write_text(text)
        res = self.run("extract.py", "apply", mid, quiet=True)
        print(res)
        self.run("extract.py", "apply", mid, "--write", quiet=True)

    def audit_packets(self, stage):
        """Zip the review (stage 'review') or grading ('grade') packets that
        still need a reply. Returns (zip path, ids)."""
        if stage == "review":
            self.run("edge_audit.py", "prepare", quiet=True)
            pk, rp = self.g / "audit" / "packets", self.g / "audit" / "findings"
        else:
            self.run("edge_audit.py", "verify", quiet=True)
            self.run("edge_audit.py", "grade-prepare", quiet=True)
            pk, rp = self.g / "audit" / "grade-packets", self.g / "audit" / "grades"
        need = [p for p in sorted(pk.glob("*.md"))
                if not (rp / f"{p.stem}.txt").exists() and not (rp / f"{p.stem}.tsv").exists()]
        out = self.dir / f"to-gemini-{stage}"
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir()
        for p in need:
            shutil.copy(p, out / f"{stage}-{p.stem}.md")
        z = shutil.make_archive(str(out), "zip", out)
        return pathlib.Path(z), [p.stem for p in need]

    def save_audit_replies(self, stage, files):
        """files: {file name: bytes}. Each name must contain the reading id
        (e.g. 'm03.txt' or 'review-m03 reply.tsv')."""
        pat = re.compile(r"(?<![a-z0-9])(" + json.loads((self.dir / "course.json").read_text())
                         .get("id_pattern", r"m\d{2,3}") + r")(?![0-9])")
        rp = self.g / "audit" / ("findings" if stage == "review" else "grades")
        rp.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            m = pat.search(name)
            if not m:
                print(f"  {name}: no reading id in the file name; rename it, e.g. m03.txt")
                continue
            (rp / f"{m.group(1)}.txt").write_bytes(data)
            print(f"  {name} -> {stage} reply for {m.group(1)}")
        if stage == "review":
            self.run("edge_audit.py", "verify")

    # -------------------------------------------------------------- results
    def results(self):
        self.run("check.py")
        try:
            self.run("render.py", quiet=True)
        except RuntimeError as e:
            print(f"(diagrams not drawn: {e})")
        return self.g / "audit" / "alerts.md"

    def export(self):
        self.run("notebooklm.py")
        nb = self.dir / "notebooklm"
        # only the sources: the chat instructions go in Configure chat, not in as a source
        tmp = self.dir / "notebooklm-sources"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir()
        for f in [*nb.glob("*concept map.md"), *nb.glob("AI literacy*.md"),
                  *(nb / "modules").glob("*.md")]:
            shutil.copy(f, tmp / f.name)
        z = shutil.make_archive(str(tmp), "zip", tmp)
        shutil.rmtree(tmp)
        print(f"Sources zipped to {z}")
        return pathlib.Path(z)


def to_markdown(f):
    """(text, warning) for one reading."""
    ext = f.suffix.lower()
    try:
        if ext in (".md", ".markdown", ".txt"):
            text = f.read_text(errors="replace")
            return re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S), ""
        if ext == ".pdf":
            if shutil.which("pdftotext") is None:
                return "", "pdftotext is missing (the notebook's setup cell installs it)"
            r = subprocess.run(["pdftotext", "-enc", "UTF-8", str(f), "-"],
                               capture_output=True, text=True)
            return r.stdout, ("" if r.returncode == 0 else r.stderr.strip()[:200])
        r = subprocess.run(["pandoc", str(f), "-t", "gfm", "--wrap=none"],
                           capture_output=True, text=True)
        return r.stdout, ("" if r.returncode == 0 else r.stderr.strip()[:200])
    except Exception as e:
        return "", str(e)[:200]
