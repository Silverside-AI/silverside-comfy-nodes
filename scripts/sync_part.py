"""Re-sync one part of Silverside Comfy Nodes from its source repo at a pinned commit.

Every part under packs/ is a MIRROR of a commit of its source repo (packs.json says which), minus everything that
shows how the workflows are built or run. This repo is public: node code only, never a workflow, an example, a
manual or a test harness (those stay in the private source repos and Silverside-AI/brand-brain-workflows).
Development happens in the source repo; never edit a part by hand here. To take a new commit:

    python3 scripts/sync_part.py <part> <commit> [--source <path to a clone of the source repo>]

It replaces packs/<part>/ with that commit (git archive), removes STRIP and every ComfyUI workflow file (UI or API
JSON) wherever it sits, moves the part's web/*.js into the pack's web/ (removing
the files the previous version contributed), drops the part's own requirements.txt after showing any line the root
requirements.txt doesn't cover (merge those by hand), records the commit in packs.json, and for automatte lists
nodes that are new or gone versus automatte_allowlist.json. Then run scripts/load_test.py and commit.
The source clone defaults to ~/Documents/ComfyUI/nodes/<repo name from packs.json>.
"""
import argparse, io, json, os, re, shutil, subprocess, sys, tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# top-level names a part never keeps here: workflows and examples, manuals, dev tools and tests, dev-only lock files
STRIP = {"workflows", "example_workflows", "examples", "tools", "tests", "test", "docs", "README.md", ".gitignore",
         "imgpost.lock.json"}


def is_workflow(path):
    """True for a ComfyUI workflow, UI format (nodes + links) or API format ({id: {class_type, inputs}})."""
    try:
        g = json.load(open(path))
    except Exception:
        return False
    if not isinstance(g, dict) or not g:
        return False
    return ("nodes" in g and "links" in g) or all(isinstance(v, dict) and "class_type" in v for v in g.values())


def strip(dest):
    gone = [n for n in sorted(os.listdir(dest)) if n in STRIP]
    for n in gone:
        p = os.path.join(dest, n)
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    for d, _, files in os.walk(dest):
        for f in files:
            if f.endswith(".json") and is_workflow(os.path.join(d, f)):
                os.remove(os.path.join(d, f)); gone.append(os.path.relpath(os.path.join(d, f), dest))
    if gone:
        print("not mirrored (private):", ", ".join(gone))
PACKS = os.path.join(ROOT, "packs")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("part"); ap.add_argument("commit"); ap.add_argument("--source")
    a = ap.parse_args()
    manifest = json.load(open(os.path.join(ROOT, "packs.json")))
    if a.part not in manifest:
        sys.exit(f"unknown part {a.part!r}; parts: {', '.join(manifest)}")
    entry = manifest[a.part]
    src = a.source or os.path.expanduser("~/Documents/ComfyUI/nodes/" + entry["from"].split("/")[-1])
    full = subprocess.run(["git", "-C", src, "rev-parse", "--verify", a.commit + "^{commit}"],
                          capture_output=True, text=True)
    if full.returncode:
        sys.exit(f"{a.commit} is not a commit in {src} (fetch it first)")
    sha = full.stdout.strip()
    tar = subprocess.run(["git", "-C", src, "archive", sha], capture_output=True, check=True).stdout

    dest = os.path.join(PACKS, a.part)
    assert os.path.dirname(dest) == PACKS and a.part and "/" not in a.part      # never remove anything else
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(dest, filter="data")
    strip(dest)

    web = os.path.join(ROOT, "web")
    for f in entry.get("web", []):                                                # the previous version's files
        p = os.path.join(web, f)
        if os.path.isfile(p):
            os.remove(p)
    new_web = []
    pw = os.path.join(dest, "web")
    if os.path.isdir(pw):
        for f in sorted(os.listdir(pw)):
            if f.endswith(".js"):
                if os.path.exists(os.path.join(web, f)):
                    sys.exit(f"web/{f} already belongs to another part: rename it in the source repo")
                shutil.copy2(os.path.join(pw, f), os.path.join(web, f)); new_web.append(f)
        shutil.rmtree(pw)

    req = os.path.join(dest, "requirements.txt")
    if os.path.isfile(req):
        root_req = open(os.path.join(ROOT, "requirements.txt")).read().lower()
        missing = []
        for line in open(req):
            name = re.split(r"[<>=!~\[ #]", line.strip(), 1)[0].lower()
            if name and name not in root_req and name not in ("torch", "torchvision", "numpy") and not name.startswith("opencv"):
                missing.append(line.strip())
        os.remove(req)
        if missing:
            print("NOT in the root requirements.txt yet (add by hand if needed):", *missing, sep="\n  ")

    if a.part == "automatte":
        code = "".join(open(os.path.join(dest, f), errors="ignore").read() for f in os.listdir(dest) if f.endswith(".py"))
        now = set(re.findall(r'"(AutoMatte[A-Za-z]+)"\s*:', code))
        allow = set(json.load(open(os.path.join(PACKS, "automatte_allowlist.json"))))
        if allow - now:
            print("allowlisted nodes this commit no longer has:", sorted(allow - now))
        print(f"AutoMatte nodes not registered (in-progress work): {len(now - allow)}; add to automatte_allowlist.json only"
              " when a finished workflow uses one")

    entry.update({"commit": sha[:7], "web": new_web})
    json.dump(manifest, open(os.path.join(ROOT, "packs.json"), "w"), indent=1)
    print(f"packs/{a.part} = {entry['from']} @ {sha[:7]}. Next: python3 scripts/load_test.py, then commit.")


if __name__ == "__main__":
    main()
