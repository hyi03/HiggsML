"""Script wrapper for the M6 sample-efficiency controls CLI."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from higgsml.cli_sample_efficiency_controls import main


if __name__ == "__main__":
    raise SystemExit(main())
