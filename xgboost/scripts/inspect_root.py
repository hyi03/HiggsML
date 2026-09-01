from __future__ import annotations

import argparse
import json

from src.io import inspect_root


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a ROOT file and its TTree")
    parser.add_argument("path")
    parser.add_argument("--tree")
    args = parser.parse_args()
    print(json.dumps(inspect_root(args.path, args.tree), indent=2))


if __name__ == "__main__":
    main()

