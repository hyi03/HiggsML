"""Build the REVTeX PDF from checked-in assets; refresh only when requested."""
import argparse
import filecmp
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

PAPER_DIR = Path(__file__).resolve().parents[1]
LATEX_DIR = PAPER_DIR / "latex"
REQUIRED_ASSETS = (
    *(LATEX_DIR / "figures" / f"{name}.pdf" for name in (
        "subset_widths", "compact_comparisons", "shapley", "auc_width",
        "mc_uncertainty", "coverage")),
    *(LATEX_DIR / "generated" / f"{name}.tex" for name in (
        "numbers", "mc_uncertainty_rows", "nominal_rows", "interaction_rows")),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latexmk", default="latexmk", help="latexmk executable or full path")
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--run-name",
        help=("Explicitly verify and regenerate assets from "
              "runs/h4l-off-<name> before building."),
    )
    source.add_argument('--evidence-manifest', type=Path,
                        help='Explicitly verify and regenerate assets from a source manifest.')
    args = parser.parse_args()
    snapshot_dir = None
    if args.run_name or args.evidence_manifest:
        # A fresh extraction cannot overwrite the selected historical snapshot.
        snapshot_dir = Path(tempfile.mkdtemp(prefix='higgsml-paper-')) / 'snapshot'
        selection_args = (['--run-name', args.run_name] if args.run_name else
                          ['--evidence-manifest', str(args.evidence_manifest.resolve())])
        subprocess.run(
            [sys.executable, str(PAPER_DIR / "scripts/collect_evidence.py"),
             *selection_args, '--output', str(snapshot_dir)],
            cwd=PAPER_DIR.parent,
            check=True,
        )
        from paper_snapshot import load_snapshot
        load_snapshot(snapshot_dir, refreshed=True)
        subprocess.run([sys.executable, str(PAPER_DIR/'scripts/sync_manuscript.py'), '--check'],
                       cwd=PAPER_DIR.parent, check=True)
        subprocess.run(
            [sys.executable, str(PAPER_DIR / "scripts/make_figures.py"),
             '--snapshot-dir', str(snapshot_dir), '--refreshed'],
            cwd=PAPER_DIR, check=True, stdout=subprocess.DEVNULL,
        )
    missing = [str(path.relative_to(PAPER_DIR)) for path in REQUIRED_ASSETS if not path.is_file()]
    if missing:
        raise SystemExit("Missing committed LaTeX assets: " + ", ".join(missing))
    latexmk = shutil.which(args.latexmk)
    if not latexmk:
        raise SystemExit("latexmk is unavailable; add TeX Live to PATH or pass --latexmk PATH.")
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
    rendered_pdf = build / "main.pdf"
    published_pdf = LATEX_DIR / "main.pdf"
    # An unchanged PDF may be open in a Windows viewer, which prevents copy2.
    if not published_pdf.exists() or not filecmp.cmp(rendered_pdf, published_pdf, shallow=False):
        shutil.copy2(rendered_pdf, published_pdf)
    print(f"Built {LATEX_DIR / 'main.pdf'}")


if __name__ == "__main__":
    main()
