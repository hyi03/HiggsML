#!/usr/bin/env python3
"""Create the local exploratory access source used by the one-command workflow."""
from __future__ import annotations

import argparse
import getpass
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from higgsml.errors import ResearchError  # noqa: E402
from higgsml.inference.self_review import generate_self_review  # noqa: E402
from higgsml.run_names import workflow_directory_name  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Create a local exploratory off-only access review")
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--reviewer", default=getpass.getuser())
    parser.add_argument("--prepared-run", type=Path, default=Path("runs/h4l-prepare/prepare"))
    args = parser.parse_args(argv)
    try:
        leaf = workflow_directory_name(args.run_name).removeprefix("h4l-train-")
        run_root = PROJECT_ROOT / "runs" / ("h4l-off-" + leaf)
        prepared = args.prepared_run if args.prepared_run.is_absolute() else PROJECT_ROOT / args.prepared_run
        path = generate_self_review(run_root, prepared, reviewer=args.reviewer)
        print(f"Local exploratory access source created: {path}")
        print("Evidence status: self-reviewed and non-independent.")
        return 0
    except (ResearchError, ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return getattr(error, "exit_code", 3)


if __name__ == "__main__":
    raise SystemExit(main())
