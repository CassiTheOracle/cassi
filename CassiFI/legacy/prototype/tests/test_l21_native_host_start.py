from __future__ import annotations

import sys
from pathlib import Path

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
if str(_CASSI_FI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSI_FI_ROOT))
from cassi_fi_paths import QWEN_DLL_DIR, QWEN_MODEL_PATH
from l18_field_language_head import FieldLanguageHead
from l18_generated_token_trajectory import L18GeneratedTokenTrajectory, RuntimeConfig

MODEL = QWEN_MODEL_PATH


def main() -> int:
    head = FieldLanguageHead(MODEL, dll_path=QWEN_DLL_DIR / "ggml-base.dll", enabled=True)
    runtime = None
    try:
        runtime = L18GeneratedTokenTrajectory(RuntimeConfig(model_path=MODEL, dll_dir=QWEN_DLL_DIR, context_size=128, n_batch=64, n_ubatch=64))
        print("L21 native model owner startup PASS")
        return 0
    finally:
        if runtime is not None:
            runtime.close(suppress=True)
        head.close(unload_dll=False)


if __name__ == "__main__":
    raise SystemExit(main())
