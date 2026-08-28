from __future__ import annotations

from pathlib import Path

from l18_field_language_head import FieldLanguageHead
from l18_generated_token_trajectory import L18GeneratedTokenTrajectory, RuntimeConfig


HERE = Path(__file__).resolve().parent
MODEL = HERE / "Qwen3.8-27B-Q4_K_M.gguf"


def main() -> int:
    head = FieldLanguageHead(MODEL, dll_path=HERE / "ggml-base.dll", enabled=True)
    runtime = None
    try:
        runtime = L18GeneratedTokenTrajectory(RuntimeConfig(model_path=MODEL, dll_dir=HERE, context_size=128, n_batch=64, n_ubatch=64))
        print("L21 native model owner startup PASS")
        return 0
    finally:
        if runtime is not None:
            runtime.close(suppress=True)
        head.close(unload_dll=False)


if __name__ == "__main__":
    raise SystemExit(main())
