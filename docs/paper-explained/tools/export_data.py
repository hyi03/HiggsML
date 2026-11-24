"""Export only selected, published aggregates for the offline teaching deck."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "paper/scripts"))
from paper_snapshot import load_snapshot


def payload():
    source = load_snapshot()
    selection = json.loads((ROOT / "paper/selected-snapshot.json").read_text(encoding="utf-8"))
    return {
        "source": {**selection, "verified_date": "2026-10-26",
                   "scope": "Selected aggregate byte identity only; no independent scientific validation."},
        "seeds": source["seeds"],
        "subsets": source["subsets"],
        "records": [{k: r[k] for k in ("seed", "subset", "width68", "auc", "status")}
                    for r in source["records"]],
        "attribution": source["attribution"],
        "interactions": source["interactions"],
        "pairwise": source["pairwise"],
        "bootstrap": source["bootstrap"],
        "bootstrap_intervals": source["bootstrap_intervals"],
        "diagnostics": [r for r in source["diagnostics"]
                        if r["metric"] == "conditional_coverage" and float(r["mu"]) == 1
                        and r["subset"] in ("", "AC", "BC", "ABCD")],
        "example_model_spec": source["example_model_spec"],
        "qualification": source["qualification"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify without writing files.")
    args = parser.parse_args()
    target = ROOT / "docs/paper-explained/data.js"
    text = "// Selected publication aggregates. Regenerate with tools/export_data.py.\n"
    text += "globalThis.H4L_DATA = " + json.dumps(payload(), ensure_ascii=False, separators=(",", ":")) + ";\n"
    if args.check:
        if target.read_text(encoding="utf-8") != text:
            raise SystemExit("Teaching data differs from the pinned aggregate projection.")
    else:
        target.write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps({"mode": "check" if args.check else "export", "bytes": len(text.encode()),
                      "sha256": hashlib.sha256(text.encode()).hexdigest()}))


if __name__ == "__main__":
    main()
