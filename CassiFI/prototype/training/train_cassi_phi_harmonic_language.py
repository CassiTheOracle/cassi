"""Build the production seven-pool Phi language checkpoint from corpus episodes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Sequence

import torch

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
if str(_CASSI_FI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSI_FI_ROOT))

from cassi_fi_paths import ARTIFACT_DIR, CONFIG_DIR
from cassi_persistent_provider import _load_phi_config
from cassi_phi_harmonic_language import PhiHarmonicLanguageController
from training.train_cassi_field_language import _manifest_sources, _sample_episodes

TRAINING_RECEIPT_SCHEMA = "cassi.phi-harmonic-language-training.v1"
DEFAULT_CONFIG = CONFIG_DIR / "cassi-phi-harmonic-language.json"
DEFAULT_MANIFEST = CONFIG_DIR / "cassi-qi-corpus-first-wave.json"
DEFAULT_OUTPUT_DIR = ARTIFACT_DIR / "cassi-phi-harmonic-language"


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def train(
    config_path: Path,
    manifest_path: Path,
    output_dir: Path,
    *,
    episodes_per_source: int = 10,
    max_episode_bytes: int = 96,
    device: str = "cpu",
) -> dict[str, Any]:
    if not 1 <= episodes_per_source <= 100:
        raise ValueError("episodes_per_source must lie in [1, 100]")
    if not 8 <= max_episode_bytes <= 4096:
        raise ValueError("max_episode_bytes must lie in [8, 4096]")
    started = time.perf_counter()
    config_path = Path(config_path).resolve()
    manifest_path = Path(manifest_path).resolve()
    output_dir = Path(output_dir).resolve()
    config = _load_phi_config(config_path)
    controller = PhiHarmonicLanguageController(config)
    sources, manifest = _manifest_sources(manifest_path)
    episodes = [
        episode
        for source in sources
        for episode in _sample_episodes(
            source,
            region_start=0,
            region_bytes=source.train_bytes,
            count=episodes_per_source,
            max_episode_bytes=max_episode_bytes,
            codec=controller.codec,
        )
    ]
    event_count = sum(len(episode.events) for episode in episodes)
    if event_count > config.trajectory_capacity:
        raise ValueError(
            f"sampled corpus needs {event_count} events but the tape holds "
            f"{config.trajectory_capacity}"
        )
    state = controller.learn_exchanges(
        controller.new_state(
            batch_size=1,
            device=torch.device(device),
            dtype=torch.float32,
        ),
        [(episode.prompt, episode.continuation) for episode in episodes],
    )
    checkpoint_payload = controller.dump_state_bytes(state)
    checkpoint_path = output_dir / "field-state.pt"
    _atomic_write(checkpoint_path, checkpoint_payload)
    descriptors = [episode.descriptor() for episode in episodes]
    corpus_identity = hashlib.sha256(
        _canonical(
            {
                "manifest": manifest,
                "sources": [source.identity_dict() for source in sources],
                "episodes": descriptors,
            }
        )
    ).hexdigest()
    examples = [
        {
            "source_id": episode.source_id,
            "prompt": episode.prompt.decode("utf-8"),
            "continuation": episode.continuation.decode("utf-8"),
        }
        for episode in episodes[:4]
    ]
    receipt: dict[str, Any] = {
        "schema": TRAINING_RECEIPT_SCHEMA,
        "config": {
            "path": str(config_path),
            "sha256": _sha256(config_path.read_bytes()),
            "fingerprint": controller.config_fingerprint,
        },
        "codebook_fingerprint": controller.codebook_fingerprint,
        "codec_fingerprint": controller.codec.fingerprint,
        "corpus": {
            "identity": corpus_identity,
            "manifest": manifest,
            "sources": [source.identity_dict() for source in sources],
        },
        "training": {
            "episode_count": len(episodes),
            "event_count": event_count,
            "capacity": config.trajectory_capacity,
            "episodes": descriptors,
            "examples": examples,
        },
        "checkpoint": {
            "path": str(checkpoint_path),
            "sha256": _sha256(checkpoint_payload),
            "state_sha256": controller.state_sha256(state),
            "tape_sha256": controller.tape_sha256(state),
            "tensor_count": 1,
            "shape": list(state.field.shape),
        },
        "timing_seconds": time.perf_counter() - started,
    }
    receipt["receipt_sha256"] = hashlib.sha256(_canonical(receipt)).hexdigest()
    _atomic_write(
        output_dir / "training-receipt.json",
        json.dumps(
            receipt,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n",
    )
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--episodes-per-source", type=int, default=10)
    parser.add_argument("--max-episode-bytes", type=int, default=96)
    parser.add_argument("--device", default="cpu")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    receipt = train(
        args.config,
        args.manifest,
        args.output_dir,
        episodes_per_source=args.episodes_per_source,
        max_episode_bytes=args.max_episode_bytes,
        device=args.device,
    )
    print(json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
