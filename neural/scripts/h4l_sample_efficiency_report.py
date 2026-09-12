"""Script wrapper for the M5 sample-efficiency report CLI."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cli.sample_efficiency_report import main


if __name__ == "__main__":
    raise SystemExit(main())
