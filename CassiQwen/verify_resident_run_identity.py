"""Compare two resident runs of the same request for recorded-identity equality.

    python CassiQwen/verify_resident_run_identity.py \
        --runs perstage-base perstage-after [--runs perstage-after2]

Reads the two runs' receipts and their field stores under `--root`
(`E:/CassiData/outputs/CassiQwen/_diag` by default) and reports

* the measured identity counters (segments, stage rows, tokens) and the
  snapshot-store work counters, which must be equal for a change that only makes
  the same work cheaper; and
* every SHA-256 value recorded inside the runs' operations and manifests, by
  name, as multisets.

A run's manifests, state descriptors and the chains that link them embed
timestamps and each other, so those digests differ between any two runs of the
same request.  The check holds a change to that:

* identity and work counters must be equal;
* no digest in `NEVER_DIFFERS` (stage results, epochs, membranes, traces,
  activations, results) may differ; and
* with `--control RUN`, the difference profile must equal the profile of the
  same reference against that control run, so a change may only differ where an
  unchanged build already differs.

Exit code 0 when the counters match, no stage-scoped identity differs, and any
control profile matches; 1 otherwise.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import zlib
from pathlib import Path
from typing import Any, Iterator

DEFAULT_ROOT = Path("E:/CassiData/outputs/CassiQwen/_diag")
HEX_DIGITS = set("0123456789abcdef")
IGNORED_STORE_NAMES = {"CURRENT", "HISTORY_FLOOR", "OWNER.lock"}

# Digests that bind a stage, a token or a result: they must survive any
# change that only makes the same work cheaper.
NEVER_DIFFERS = {
    "stage_result_sha256",
    "epoch_sha256",
    "membrane_state_sha256",
    "site_trace_sha256",
    "result_sha256",
    "activation_sha256",
    "tensor_sha256",
    "response_sha256",
}

IDENTITY_KEYS = (
    "segment_count",
    "stage_cohort_rows",
    "stage_cohort_count",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "bounded_work_units",
)

WORK_KEYS = (
    "manifest_writes",
    "manifest_reuses",
    "blob_writes",
    "blob_cache_hits",
    "blob_reuses",
    "durability_syncs",
    "bytes_pruned",
    "deferred_snapshots",
    "deferred_arrays",
    "deferred_digest_reuses",
    "deferred_array_reuses",
    "snapshots_pruned",
    "backings_pruned",
)



def receipt(run: Path) -> dict[str, Any]:
    return json.loads((run / "summary.json").read_text(encoding="utf-8"))


def timed(run: Path) -> dict[str, Any]:
    return (receipt(run).get("runs") or {}).get("timed") or {}


def json_rows(path: Path) -> Iterator[Any]:
    try:
        raw = path.read_bytes()
    except OSError:
        return
    for decode in (bytes, zlib.decompress):
        try:
            payload = decode(raw)
        except Exception:  # noqa: BLE001 - a non-JSON object is simply skipped
            continue
        try:
            yield json.loads(payload.decode("utf-8"))
        except Exception:  # noqa: BLE001 - binary objects are not rows
            continue
        return


def walk(value: Any, path: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        if len(value) == 64 and all(item in HEX_DIGITS for item in value):
            yield path, value
        return
    if isinstance(value, dict):
        for key, item in value.items():
            yield from walk(item, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk(item, f"{path}[{index}]")


def recorded_digests(run: Path) -> collections.Counter:
    """Count every recorded SHA-256 by its key name."""

    counts: collections.Counter = collections.Counter()
    root = run / "home" / "field" / "field"
    for area in ("operations", "manifests"):
        directory = root / area
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file():
                continue
            for row in json_rows(path):
                for key, value in walk(row, area):
                    name = key.rsplit(".", 1)[-1].split("[", 1)[0]
                    counts[f"{name}={value}"] += 1
    return counts


def store_objects(run: Path) -> set[tuple[str, int]]:
    root = run / "home" / "field" / "field"
    found: set[tuple[str, int]] = set()
    if not root.is_dir():
        return found
    for path in root.rglob("*"):
        if not path.is_file() or path.name in IGNORED_STORE_NAMES:
            continue
        if len(path.name) == 64 and all(item in HEX_DIGITS for item in path.name):
            found.add((str(path.relative_to(root)), path.stat().st_size))
    return found


def difference_profile(
    digests_a: collections.Counter, digests_b: collections.Counter
) -> tuple[collections.Counter, int, int]:
    """Return the digest differences by name, the shared count and the totals."""

    profile: collections.Counter = collections.Counter()
    for rows in (digests_a - digests_b, digests_b - digests_a):
        for key, count in rows.items():
            profile[key.split("=", 1)[0]] += count
    shared = sum((digests_a & digests_b).values())
    return profile, shared, sum(digests_a.values()) + sum(digests_b.values()) - shared


def compare(
    reference: Path,
    other: Path,
    digests_a: collections.Counter,
    digests_b: collections.Counter,
) -> list[str]:
    failures: list[str] = []
    first, second = timed(reference), timed(other)
    if first.get("content") != second.get("content"):
        failures.append(
            f"content differs: {first.get('content')!r} against {second.get('content')!r}"
        )
    measured_a = first.get("measured") or {}
    measured_b = second.get("measured") or {}
    for key in IDENTITY_KEYS:
        if measured_a.get(key) != measured_b.get(key):
            failures.append(
                f"{key} differs: {measured_a.get(key)!r} against {measured_b.get(key)!r}"
            )
    counters_a = (first.get("counters") or {}).get("counters") or {}
    counters_b = (second.get("counters") or {}).get("counters") or {}
    for key in WORK_KEYS:
        if counters_a.get(key) != counters_b.get(key):
            failures.append(
                f"{key} differs: {counters_a.get(key)!r} against {counters_b.get(key)!r}"
            )
    profile, shared, total = difference_profile(digests_a, digests_b)
    print(
        f"{reference.name}: {sum(digests_a.values())} recorded digests, "
        f"{other.name}: {sum(digests_b.values())}, shared {shared} of {total}"
    )
    if profile:
        print(f"  differing digest names: {dict(sorted(profile.items()))}")
    forbidden = sorted(name for name in profile if name in NEVER_DIFFERS)
    if forbidden:
        failures.append("stage identity digests differ: " + ", ".join(forbidden))
    objects_a, objects_b = store_objects(reference), store_objects(other)
    print(
        f"  field objects {len(objects_a)} against {len(objects_b)}, "
        f"shared {len(objects_a & objects_b)}"
    )
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--runs",
        nargs="+",
        action="append",
        required=True,
        metavar="RUN",
        help="run directories under --root; the first is the reference",
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--control",
        metavar="RUN",
        help="a run of the same build; the difference profile must match its own",
    )
    args = parser.parse_args(argv)
    runs = [item for group in args.runs for item in group]
    paths = [args.root / name for name in runs]
    missing = [str(path) for path in paths if not (path / "summary.json").is_file()]
    if missing:
        print("missing receipts: " + ", ".join(missing), file=sys.stderr)
        return 2
    control = (args.root / args.control) if args.control else None
    if control is not None and not (control / "summary.json").is_file():
        print(f"missing control receipt: {control}", file=sys.stderr)
        return 2
    counters = {path: recorded_digests(path) for path in paths}
    expected: collections.Counter = collections.Counter()
    if control is not None:
        counters[control] = recorded_digests(control)
        expected, _, _ = difference_profile(counters[paths[0]], counters[control])
    failures: list[str] = []
    for path in paths[1:]:
        print(f"comparing {paths[0].name} against {path.name}")
        failures.extend(compare(paths[0], path, counters[paths[0]], counters[path]))
        if control is not None:
            observed, _, _ = difference_profile(counters[paths[0]], counters[path])
            if observed != expected:
                failures.append(
                    f"{path.name} differs from {control.name} in its difference profile: "
                    f"{dict(sorted(observed.items()))} against {dict(sorted(expected.items()))}"
                )
            else:
                print(f"  difference profile matches the control {control.name}")
    if failures:
        for failure in failures:
            print("FAIL " + failure)
        return 1
    print("identity preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())