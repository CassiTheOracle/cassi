"""Inventory every llama.cpp latent capture in CassiQwen/_diag.

Reads `cassi.qi.latent.v1` receipts, resolves their capture dirs, and emits a
JSON index of (arm, prompt, layers, widths, generated tokens) so downstream
lens/probe work can cite exact provenance.  Read-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

LAYER_RE = re.compile(r"^layer-(\d+)(-decode-early|-decode)?\.f32$")

TREES = (
    Path("CassiQwen/native/llama.cpp/_diag"),
    Path("CassiQwen/_diag"),
)


def norm_path(path: Path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def walk_jsons(roots):
    for root in roots:
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for name in filenames:
                if name.endswith(".json"):
                    yield Path(dirpath) / name


def walk_capture_dirs(roots):
    for root in roots:
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            if any(LAYER_RE.match(f) for f in filenames):
                yield Path(dirpath)


def load_json(path: Path):
    try:
        if path.stat().st_size > 200_000_000:
            return None
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def layer_kinds(capture_dir: Path):
    kinds: dict[str, list[int]] = {}
    if not capture_dir.is_dir():
        return kinds
    for name in os.listdir(capture_dir):
        match = LAYER_RE.match(name)
        if not match:
            continue
        kind = (match.group(2) or "-prompt").lstrip("-")
        kinds.setdefault(kind, []).append(int(match.group(1)))
    return {k: sorted(v) for k, v in kinds.items()}


def resolve_capture_dir(receipt: dict, receipt_path: Path):
    for key in ("capture_output_dir", "decode_capture_output_dir"):
        value = receipt.get(key)
        if value and Path(value).is_dir():
            return Path(value)
    files = receipt.get("capture_files") or []
    if files:
        candidate = Path(files[0]["path"]).parent
        if candidate.is_dir():
            return candidate
    for candidate in (receipt_path.parent / "captures", receipt_path.parent):
        if layer_kinds(candidate).get("prompt"):
            return candidate
    return None


def file_sha256(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def record_for(receipt: dict, receipt_path: Path, capture_dir: Path):
    kinds = layer_kinds(capture_dir)
    if not kinds.get("prompt"):
        return None
    prompt = receipt.get("prompt_text") or ""
    probe = capture_dir / f"layer-{kinds['prompt'][0]}.f32"
    width = probe.stat().st_size // 4 if probe.is_file() else None
    command = receipt.get("command") or []
    return {
        "receipt": str(receipt_path).replace("\\", "/"),
        "receipt_sha256": file_sha256(receipt_path),
        "arm_dir": str(receipt_path.parent).replace("\\", "/"),
        "capture_dir": str(capture_dir).replace("\\", "/"),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt": prompt,
        "prompt_token_ids": list(receipt.get("prompt_token_ids") or []),
        "generation_token_ids": list(receipt.get("generation_token_ids") or []),
        "decode_logits_count": len(
            [f for f in os.listdir(capture_dir) if f.startswith("decode-logits-")]
        ),
        "qi_enabled": bool(receipt.get("qi_enabled")),
        "substitute": receipt.get("substitute"),
        "field_layer": receipt.get("layer"),
        "state_field_width": receipt.get("state_field_width"),
        "row_width_requested": receipt.get("row_width_requested"),
        "layer_kinds": kinds,
        "capture_width": width,
        "model": next((a for a in command if str(a).endswith(".gguf")), None),
        "verdict": receipt.get("verdict"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="CassiQwen/hidden-state-lens/capture-inventory.json")
    args = parser.parse_args()

    records = []
    seen_dirs = set()
    for receipt_path in walk_jsons(TREES):
        receipt = load_json(receipt_path)
        if not isinstance(receipt, dict) or receipt.get("schema") != "cassi.qi.latent.v1":
            continue
        capture_dir = resolve_capture_dir(receipt, receipt_path)
        if capture_dir is None:
            continue
        record = record_for(receipt, receipt_path, capture_dir)
        if record is None:
            continue
        seen_dirs.add(norm_path(Path(record["capture_dir"])))
        records.append(record)

    orphan_dirs = sorted(
        str(d).replace("\\", "/") for d in walk_capture_dirs(TREES)
        if norm_path(d) not in seen_dirs
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"records": records, "capture_dirs_without_receipt": orphan_dirs},
                   indent=1, sort_keys=True),
        encoding="utf-8",
    )

    prompts = {r["prompt_sha256"] for r in records}
    print(f"records={len(records)} distinct_prompts={len(prompts)} capture_dirs={len(seen_dirs)}")
    widths: dict[int, int] = {}
    for record in records:
        widths[record["capture_width"]] = widths.get(record["capture_width"], 0) + 1
    print("widths:", widths)
    print(f"capture dirs without a receipt: {len(orphan_dirs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
