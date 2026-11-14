"""Shared config and manifest loading for the course-concept-graph scripts."""
import csv, json, os, pathlib, re, sys

DEFAULTS = {
    "repo": "~/modules",
    "module_files": ["index.md", "mdModule.md"],
    "pages_base": "",
    "canvas_course": "",
    "id_pattern": r"\d{4}",
    "prereq_line": r"^-\s+Prerequisites:",
}


def load(argv=None):
    """Return (workdir, cfg). Honours a --dir argument; defaults to cwd."""
    argv = list(sys.argv[1:] if argv is None else argv)
    d = os.getcwd()
    if "--dir" in argv:
        d = argv[argv.index("--dir") + 1]
    work = pathlib.Path(d).expanduser().resolve()
    cfg = dict(DEFAULTS)
    path = work / "course.json"
    if path.exists():
        cfg.update(json.load(open(path)))
    else:
        sys.exit(f"no course.json in {work} — see the course-concept-graph skill")
    cfg["repo"] = pathlib.Path(cfg["repo"]).expanduser()
    return work, cfg


def modules(work):
    """The manifest, in Canvas presentation order: list of dicts."""
    out = []
    for line in open(work / "modules.tsv"):
        if line.startswith("#") or not line.strip():
            continue
        p = (line.rstrip("\n").split("\t") + ["", "", ""])[:4]
        out.append({"id": p[0], "canvas_module": p[1], "title": p[2],
                    "status": p[3] or "published"})
    return out


def source_file(cfg, mid):
    """Locate a module's Markdown source in the content repo."""
    for name in cfg["module_files"]:
        f = cfg["repo"] / mid / name
        if f.exists():
            return f
    return None


def tsv(path, cols):
    return list(csv.DictReader(open(path), delimiter="\t")) if path.exists() else []


def write_tsv(path, rows, cols):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t")
        w.writeheader()
        w.writerows(rows)


def prereq_ids(cfg, text):
    """Module ids referenced from a document's Prerequisites line."""
    line = [l for l in text.split("\n") if re.match(cfg["prereq_line"], l)]
    return re.findall(r"\.\./(" + cfg["id_pattern"] + r")", line[0]) if line else []


PROMPTS = pathlib.Path(__file__).resolve().parent.parent / "prompts"


def prompt(name, **kw):
    """A prompt from prompts/NAME.md with {key} placeholders filled. Only the
    keys given are replaced, so braces elsewhere (LaTeX, code) are safe.
    {output} is always filled from prompts/output.md, with {out} inside it."""
    text = (PROMPTS / f"{name}.md").read_text()
    if "{output}" in text:
        text = text.replace("{output}", (PROMPTS / "output.md").read_text().strip())
    for k, v in kw.items():
        text = text.replace("{" + k + "}", str(v))
    return text


def read_table(path, first, raw=False):
    """Rows of a TSV table whose header starts with column `first`. Accepts a
    plain TSV file, or a model's whole reply saved as-is (the table inside a
    ``` fence, possibly after other blocks). Returns [] if the file is missing;
    raises ValueError if it holds no such table. With raw=True, each row is
    the list of its fields as written, for callers that repair misaligned rows."""
    path = pathlib.Path(path)
    if not path.exists():
        return []
    text = path.read_text().replace("\r\n", "\n")
    blocks = re.findall(r"```[^\n]*\n(.*?)```", text, re.S) or [text]
    for b in blocks:
        lines = [l for l in b.split("\n") if l.strip()]
        if lines and lines[0].split("\t")[0].strip() == first and "\t" in lines[0]:
            head = [h.strip() for h in lines[0].split("\t")]
            if raw:
                return [[x.strip() for x in l.split("\t")] for l in lines[1:]]
            rows = []
            for l in lines[1:]:
                p = [x.strip() for x in l.split("\t")]
                rows.append(dict(zip(head, p + [""] * (len(head) - len(p)))))
            return rows
    raise ValueError(f"{path}: no tab-separated table with a '{first}' column first")
