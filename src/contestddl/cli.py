from __future__ import annotations

import argparse
import json
from pathlib import Path

from contestddl.output import write_outputs
from contestddl.pipeline import SOURCE_ADAPTERS, run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Update competition deadline data")
    parser.add_argument("command", nargs="?", default="update", choices=("update", "check"))
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--source", action="append", choices=sorted(SOURCE_ADAPTERS), help="only run selected source; repeatable")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    result = run_pipeline(root, args.source)
    if args.command == "update":
        write_outputs(root, result)
    summary = {
        "health": result["data"]["source_health"], "stats": result["data"]["stats"],
        "sources": result["source_status"]["sources"],
        "conflicts": len(result["quality"]["conflicts"]),
        "validation_errors": len(result["quality"]["validation_errors"]),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not any(source["ok"] for source in result["source_status"]["sources"]):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
