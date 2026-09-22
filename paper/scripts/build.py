"""Build paper assets and the REVTeX PDF; does not execute scientific workflows."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

PAPER_DIR = Path(__file__).resolve().parents[1]
LATEX_DIR = PAPER_DIR / "latex"
EVIDENCE_DIR = PAPER_DIR / "evidence"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latexmk", default="latexmk", help="latexmk executable or full path")
    args = parser.parse_args()
    if not (EVIDENCE_DIR / "data/results.json").is_file():
        raise SystemExit("Missing checked snapshot. Run paper/scripts/collect_evidence.py first.")
    latexmk = shutil.which(args.latexmk)
    if not latexmk:
        raise SystemExit("latexmk is unavailable; add TeX Live to PATH or pass --latexmk PATH.")
    subprocess.run([sys.executable, str(PAPER_DIR / "scripts/make_figures.py")], cwd=PAPER_DIR, check=True,
                   stdout=subprocess.DEVNULL)
    build = LATEX_DIR / ".build"
    build.mkdir(exist_ok=True)
    with (build / "build-output.txt").open("w", encoding="utf-8") as log:
        result = subprocess.run([latexmk, "-pdf", "-interaction=nonstopmode", "-halt-on-error",
                                 "-outdir=.build", "main.tex"], cwd=LATEX_DIR, stdout=log,
                                stderr=subprocess.STDOUT)
    if result.returncode:
        print((build / "build-output.txt").read_text(encoding="utf-8", errors="replace")[-6000:])
        raise SystemExit(result.returncode)
    text = (build / "main.log").read_text(encoding="utf-8", errors="replace")
    problems = [line for line in text.splitlines() if
                "Overfull" in line or "undefined" in line or "A float is stuck" in line
                or "Deferred float stuck" in line]
    if problems:
        raise SystemExit("Resolve manuscript layout/reference warnings:\n"+"\n".join(problems))
    shutil.copy2(build / "main.pdf", LATEX_DIR / "main.pdf")
    print(f"Built {LATEX_DIR / 'main.pdf'}")


if __name__ == "__main__":
    main()
