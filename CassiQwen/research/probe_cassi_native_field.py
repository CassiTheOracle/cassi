"""Attest whether a running server's native Qi field changes generation.

The server reports neither its launch flags nor its effective field state: the
per-response `cassi` receipt is written only by apprentice mode, `/props` exposes
build and template identity, `/metrics` carries `cassi_modal_*` but nothing for
the Qi field, and the startup log prints no field state at default verbosity. So
a run's field configuration is established behaviorally: capture the same
prompts at temperature 0 from two launches of the same binary that differ only
in `--cassi-qi-field`, then compare the generations byte for byte.

Usage:
  python probe_cassi_native_field.py --out _diag/cassi-field-attestation/field-on.json
  python probe_cassi_native_field.py --out .../field-off.json --label field-off
  python probe_cassi_native_field.py --compare field-on.json field-off.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any, Mapping, Sequence
_CASSIQWEN_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_CASSIQWEN_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSIQWEN_ROOT))


from cassi_field_qwen_workbench import LocalQwenClient

DEFAULT_MODEL = pathlib.Path(__file__).resolve().parent.parent / "Qwen3.8-27B-Q4_K_M.gguf"

PROMPTS: tuple[tuple[str, str], ...] = (
    (
        "trivial-json",
        'Return exactly one JSON object with key "sum". The values are 17 and 25.',
    ),
    (
        "short-answer",
        'Return exactly one JSON object with key "answer". Question: what is the capital of Peru?',
    ),
    (
        "workcase-shaped",
        'Return exactly one JSON object with keys "owner" and "page".\n\n'
        "Retained records:\n"
        "- atlas/pager: {\"owner\": \"helio-sre\", \"page\": true}\n\n"
        "Task: name the pager owner and whether they are paged for the atlas backup failure.",
    ),
)


def capture(base_url: str, model_path: pathlib.Path, max_tokens: int = 48) -> dict[str, Any]:
    client = LocalQwenClient(base_url, model_path=model_path)
    readings = []
    for name, prompt in PROMPTS:
        result = client.complete(prompt=prompt, max_tokens=max_tokens, thinking=False)
        readings.append(
            {
                "name": name,
                "content": result["content"],
                "reasoning_chars": len(str(result.get("reasoning_content") or "")),
                "completion_tokens": int((result.get("usage") or {}).get("completion_tokens") or 0),
                "prompt_sha256": result.get("prompt_sha256"),
            }
        )
    return {
        "base_url": base_url,
        "model": {"path": str(model_path.resolve()), "sha256": client.model_sha256},
        "max_tokens": max_tokens,
        "temperature": 0,
        "readings": readings,
    }


def compare(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    left_by_name = {r["name"]: r for r in left["readings"]}
    right_by_name = {r["name"]: r for r in right["readings"]}
    names = sorted(set(left_by_name) | set(right_by_name))
    rows = []
    for name in names:
        a = left_by_name.get(name)
        b = right_by_name.get(name)
        same = bool(a and b and a["content"] == b["content"])
        rows.append(
            {
                "name": name,
                "identical": same,
                "left": (a or {}).get("content"),
                "right": (b or {}).get("content"),
                "left_tokens": (a or {}).get("completion_tokens"),
                "right_tokens": (b or {}).get("completion_tokens"),
            }
        )
    identical = sum(1 for r in rows if r["identical"])
    return {
        "prompts": len(rows),
        "identical": identical,
        "differing": len(rows) - identical,
        "verdict": "field changes generation" if identical < len(rows) else "no observed field effect",
        "rows": rows,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=pathlib.Path, help="write this server's readings here")
    parser.add_argument("--base-url", default="http://127.0.0.1:8084")
    parser.add_argument("--model", type=pathlib.Path, default=DEFAULT_MODEL)
    parser.add_argument("--max-tokens", type=int, default=48)
    parser.add_argument("--label", default="")
    parser.add_argument("--compare", nargs=2, type=pathlib.Path, metavar=("LEFT", "RIGHT"))
    args = parser.parse_args(argv)

    if args.compare:
        left, right = (json.loads(path.read_text(encoding="utf-8")) for path in args.compare)
        report = compare(left, right)
        print(json.dumps(report, indent=2, sort_keys=True))
        for row in report["rows"]:
            mark = "=" if row["identical"] else "!"
            print(f'{mark} {row["name"]}: {row["left"]!r} vs {row["right"]!r}', file=sys.stderr)
        return 0

    if not args.out:
        parser.error("--out is required unless --compare is given")
    reading = capture(args.base_url, args.model, max_tokens=args.max_tokens)
    reading["label"] = args.label
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(reading, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"out": str(args.out), "label": args.label, "prompts": len(reading["readings"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
