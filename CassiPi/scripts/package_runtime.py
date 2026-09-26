from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Sequence
import uuid


ROOT = Path(__file__).resolve().parents[1]
FI_RUNTIME = ROOT.parent / "CassiFI" / "runtime"
sys.path.insert(0, str(FI_RUNTIME))

try:
    from build_cassipi_runtime import MANIFEST_NAME, RuntimePackageError, build_runtime, verify_runtime
except ModuleNotFoundError as exc:
    raise SystemExit(f"canonical CassiFI runtime builder is unavailable: {exc}") from None


def _install(destination: Path) -> dict:
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging_parent = Path(tempfile.mkdtemp(prefix=".cassipi-runtime-package-", dir=destination.parent))
    staging = staging_parent / "runtime"
    backup = destination.with_name(f".{destination.name}.backup-{uuid.uuid4().hex}")
    moved_existing = False
    try:
        manifest = build_runtime(staging)
        verified = verify_runtime(staging)
        if destination.exists():
            os.replace(destination, backup)
            moved_existing = True
        os.replace(staging, destination)
        if moved_existing:
            shutil.rmtree(backup)
        return {
            "status": "PASS",
            "runtime_root": str(destination),
            "runtime_id": manifest["runtime_id"],
            "file_count": len(manifest["files"]),
            "manifest_sha256": hashlib.sha256(
                (destination / MANIFEST_NAME).read_bytes()
            ).hexdigest(),
        }
    except BaseException:
        if moved_existing and not destination.exists() and backup.exists():
            os.replace(backup, destination)
        raise
    finally:
        shutil.rmtree(staging_parent, ignore_errors=True)
        if backup.exists() and destination.exists():
            shutil.rmtree(backup, ignore_errors=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build and atomically install the verified CassiPi-private FI runtime"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "fi-runtime")
    args = parser.parse_args(argv)
    try:
        result = _install(args.output)
    except (RuntimePackageError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
