#!/usr/bin/env python3
"""Export the already verified Cassi math/Python capability layer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cassi_skill_bundle import build_skill_bundle, verify_skill_bundle, write_skill_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("_diag/cassi-skill-bundle.json"))
    args = parser.parse_args()
    bundle = build_skill_bundle()
    verification = verify_skill_bundle(bundle)
    write_skill_bundle(args.out, bundle)
    print(
        json.dumps(
            {
                "status": verification["status"],
                "skill_count": verification["skill_count"],
                "content_sha256": verification["content_sha256"],
                "out": str(args.out),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
