#!/usr/bin/env python3
"""Rebuild links/ and clean/ from modules.tsv.

links/<id>.md  symlinks the module's source in the content repo — verbatim.
clean/<id>.md  is the same text with the sections named in ai-sections.tsv
               removed. clean/ is what gets indexed and analysed.

Usage: build_corpus.py [--dir WORKDIR]
"""
import csv, collections, pathlib, sys
import courselib

work, cfg = courselib.load()
mods = courselib.modules(work)

drops = collections.defaultdict(set)
ai = work / "ai-sections.tsv"
if ai.exists():
    for line in open(ai):
        if line.startswith("#") or not line.strip():
            continue
        mid, heading = line.rstrip("\n").split("\t", 1)
        drops[mid].add(heading)

for sub in ("links", "clean"):
    (work / sub).mkdir(exist_ok=True)
for old in (work / "links").glob("*.md"):
    old.unlink()
for old in (work / "clean").glob("*.md"):
    old.unlink()

missing, dropped_total = [], 0
for m in mods:
    src = courselib.source_file(cfg, m["id"])
    if not src:
        missing.append(m["id"])
        continue
    (work / "links" / f"{m['id']}.md").symlink_to(src)
    lines = src.read_text().split("\n")
    if drops[m["id"]]:
        kept, skip = [], False
        for line in lines:
            if line.startswith("# "):
                skip = line in drops[m["id"]]
            if not skip:
                kept.append(line)
        if len(kept) != len(lines):
            print(f"  {m['id']}: dropped {len(lines) - len(kept)} of {len(lines)} lines")
            dropped_total += len(lines) - len(kept)
        lines = kept
    # normalise the tail so output is identical wherever a dropped section sat
    (work / "clean" / f"{m['id']}.md").write_text("\n".join(lines).rstrip("\n") + "\n")

print(f"links/ and clean/: {len(mods) - len(missing)} modules, {dropped_total} lines dropped")
if missing:
    print(f"MISSING from {cfg['repo']}: {', '.join(missing)}", file=sys.stderr)
    sys.exit(1)
