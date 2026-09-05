"""Short-lived live demonstration for the isolated F5 field provider."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import threading
import time
from pathlib import Path

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
if str(_CASSI_FI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSI_FI_ROOT))
from cassi_fi_paths import ARTIFACT_DIR
from typing import Any

from cassi_field_daemon import CassiFieldDaemon, CassiFieldTCPServer
from cassi_f5_provider import CassiF5Provider, ProviderConfig


def _finite(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, dict):
        return all(_finite(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return all(_finite(v) for v in value)
    return True


def _contains_forbidden(value: Any) -> bool:
    forbidden = ("residual", "logit", "kv", "teacher_trace", "raw_field", "field_array", "wave")
    if isinstance(value, dict):
        return any(
            any(part in str(key).lower() for part in forbidden) or _contains_forbidden(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden(item) for item in value)
    return False


def _text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    choice = choices[0]
    message = choice.get("message") or {}
    return str(message.get("content", choice.get("text", "")))


def _tokens(response: dict[str, Any]) -> int:
    usage = response.get("usage") or {}
    value = usage.get("completion_tokens", response.get("cassi", {}).get("token_count", 0))
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _compact_response(response: dict[str, Any]) -> dict[str, Any]:
    receipt = response.get("cassi")
    if not isinstance(receipt, dict):
        receipt = {}
    # Keep only the contract's finite, non-sensitive receipt metadata.
    allowed = {
        "protocol", "version", "profile", "mode", "field_execution",
        "field_step", "field_hash", "teacher_event_count",
        "candidate_coverage", "candidate_collision",
        "candidate_coverage_count", "candidate_collision_count",
        "candidate_field_score_span_mean", "candidate_field_score_span_max",
        "selected_token_changes", "checkpoint", "checkpoint_identity",
        "checkpoint_path", "checkpoint_sha256", "field_config_fingerprint",
        "field_codebook_fingerprint", "qi", "persistence",
        "no_teacher_persistence",
    }
    safe = {k: receipt[k] for k in allowed if k in receipt and _finite(receipt[k])}
    return {"text": _text(response), "token_count": _tokens(response), "cassi": safe}


def _sha256(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 16), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError:
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the isolated Cassi F5 field demo")
    parser.add_argument("--model", required=True, help="local GGUF model path")
    parser.add_argument("--dll", required=True, help="local llama.cpp DLL path")
    parser.add_argument("--state", required=True, help="provider state directory")
    parser.add_argument("--field-port", type=int, default=17600, help="loopback test daemon port")
    parser.add_argument("--max-tokens", type=int, default=8)
    parser.add_argument("--context", type=int, default=2048)
    parser.add_argument("--batch", type=int, default=512)
    parser.add_argument("--gpu-layers", type=int, default=99)
    parser.add_argument("--field-weight", type=float, default=0.25)
    parser.add_argument("--layer-index", type=int, default=32)
    parser.add_argument("--prompt", default="Give a concise description of a stable orbit.")
    parser.add_argument("--session", default="f5-demo")
    parser.add_argument("--output", type=Path, default=ARTIFACT_DIR / "f5" / "f5-demo.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.field_port < 1 or args.field_port > 65535:
        raise SystemExit("--field-port must be in [1,65535]")
    if args.max_tokens < 1:
        raise SystemExit("--max-tokens must be positive")
    daemon = CassiFieldDaemon(host="127.0.0.1", port=args.field_port)
    server = CassiFieldTCPServer(daemon)
    thread = threading.Thread(target=server.serve_forever_bounded, name="cassi-f5-field", daemon=True)
    thread.start()
    provider: CassiF5Provider | None = None
    started = time.time()
    receipt: dict[str, Any] = {"protocol": "cassi.f5.demo.v2", "finite": True}
    try:
        config = ProviderConfig(
            model_path=args.model,
            dll_dir=args.dll,
            state_dir=args.state,
            field_host="127.0.0.1",
            field_port=args.field_port,
            context_size=args.context,
            n_batch=args.batch,
            n_ubatch=min(args.batch, 512),
            gpu_layers=args.gpu_layers,
            max_tokens=args.max_tokens,
            field_weight=args.field_weight,
            layer_index=args.layer_index,
            enable_f5=True,
        )
        provider = CassiF5Provider(config)
        provider.start()
        request = {
            "messages": [{"role": "user", "content": args.prompt}],
            "max_tokens": args.max_tokens,
            "cassi_field_mode": "baseline",
            "user": args.session,
        }
        baseline_raw = provider.complete(request)
        baseline = _compact_response(baseline_raw)
        request["cassi_field_mode"] = "field"
        first_raw = provider.complete(request)
        first = _compact_response(first_raw)
        second_raw = provider.complete(request)
        second = _compact_response(second_raw)
        first_receipt = first["cassi"]
        second_receipt = second["cassi"]
        checkpoint = first_receipt.get("checkpoint_path") or first_receipt.get("checkpoint")
        checkpoint_path = Path(checkpoint) if isinstance(checkpoint, str) else None
        first_checkpoint = first_receipt.get("checkpoint_identity") or first_receipt.get("checkpoint_sha256")
        second_checkpoint = second_receipt.get("checkpoint_identity") or second_receipt.get("checkpoint_sha256")
        receipt.update({
            "elapsed_seconds": round(time.time() - started, 6),
            "session": args.session,
            "baseline": baseline,
            "first_field": first,
            "second_field": second,
            "changed_token_count_first": int(first_receipt.get("selected_token_changes", 0) or 0),
            "changed_token_count_second": int(second_receipt.get("selected_token_changes", 0) or 0),
            "same_session": True,
            "checkpoint_exists": bool(checkpoint_path and checkpoint_path.is_file()),
            "checkpoint_sha256": _sha256(checkpoint_path) if checkpoint_path else first_receipt.get("checkpoint_sha256"),
            "checkpoint_identity_stable": bool(first_checkpoint and first_checkpoint == second_checkpoint),
            "field_hash_progressed": bool(
                first_receipt.get("field_hash")
                and first_receipt.get("field_hash") != second_receipt.get("field_hash")
            ),
            "qi_gating_active": bool(
                isinstance(first_receipt.get("qi"), dict)
                and int(first_receipt["qi"].get("available_event_count", 0)) > 0
            ),
            "no_teacher_persistence": bool(first_receipt.get("no_teacher_persistence", True)),
            "forbidden_payloads_absent": not (_contains_forbidden(baseline_raw) or _contains_forbidden(first_raw) or _contains_forbidden(second_raw)),
        })
    finally:
        if provider is not None:
            provider.close()
        daemon.handle({"cmd": "shutdown"})
        thread.join(timeout=3.0)
        server.server_close()

    receipt["finite"] = _finite(receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "finite": receipt["finite"], "baseline_tokens": receipt["baseline"]["token_count"], "field_tokens": receipt["first_field"]["token_count"]}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
