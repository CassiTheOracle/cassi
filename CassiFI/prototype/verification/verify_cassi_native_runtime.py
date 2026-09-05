"""Static dependency and runtime ownership gate for Cassi-native text paths."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
for _path in (_CASSI_FI_ROOT, _CASSI_FI_ROOT / "training", _CASSI_FI_ROOT / "verification"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
from typing import Final

import torch

from cassi_field_language import CassiQiTextEngine
from cassi_qi_field import QiFieldConfig, QiFieldController
from cassi_fi_paths import ARTIFACT_DIR, CONFIG_DIR, ROOT


_ROOT: Final[Path] = ROOT
_CORPUS_CONFIG: Final[Path] = CONFIG_DIR / "cassi-qi-corpus-language.json"
_CORPUS_CHECKPOINT: Final[Path] = (
    ARTIFACT_DIR / "cassi-qi-corpus-language" / "field-state.pt"
)
_LIVE_FILES: Final[tuple[str, ...]] = (
    "cassi_field_language.py",
    "cassi_qi_field.py",
    "cassi_qi_bootstrap.py",
    "cassi_qi_profile.py",
    "cassi_qwen_displacement.py",
    "cassi_persistent_provider.py",
    "cassi_conscious_chat.py",
    "runtime/run_cassi_conscious_chat.py",
)
_ALLOWED_LOCAL_IMPORTS: Final[frozenset[str]] = frozenset(
    {
        "cassi_conscious_chat",
        "cassi_field_language",
        "cassi_qi_field",
        "cassi_fi_paths",
        "cassi_qi_bootstrap",
        "cassi_qi_profile",
        "cassi_qwen_displacement",
    }
)
_BANNED_IMPORT_PREFIXES: Final[tuple[str, ...]] = (
    "build_cassi_field_language_data",
    "evaluate_cassi_field_language",
    "aiohttp",
    "ctypes",
    "jax",
    "keras",
    "l18_generated_token_trajectory",
    "http.client",
    "importlib",
    "llama_cpp",
    "sklearn",
    "openai",
    "requests",
    "socket",
    "subprocess",
    "tensorflow",
    "urllib",
    "torch.distributions",
    "torch.nn",
    "torch.optim",
    "train_cassi_field_language",
    "transformers",
)
_BANNED_CALL_ATTRIBUTES: Final[frozenset[str]] = frozenset(
    {
        "backward",
        "bernoulli",
        "choice",
        "cross_entropy",
        "dropout",
        "gumbel_softmax",
        "kl_div",
        "log_softmax",
        "mse_loss",
        "multinomial",
        "nll_loss",
        "normal",
        "rand",
        "randint",
        "randn",
        "softmax",
    }
)
_BANNED_CONSTRUCTORS: Final[frozenset[str]] = frozenset(
    {
        "Adam",
        "AdamW",
        "Adadelta",
        "Adagrad",
        "BatchNorm1d",
        "BatchNorm2d",
        "BatchNorm3d",
        "Conv1d",
        "Conv2d",
        "Conv3d",
        "CrossEntropyLoss",
        "Dropout",
        "Embedding",
        "GRU",
        "GRUCell",
        "LSTM",
        "LSTMCell",
        "GELU",
        "LayerNorm",
        "LBFGS",
        "Linear",
        "MSELoss",
        "LogSoftmax",
        "ModuleDict",
        "ModuleList",
        "MultiheadAttention",
        "NLLLoss",
        "Parameter",
        "RMSprop",
        "RNN",
        "RNNCell",
        "Sequential",
        "ReLU",
        "SGD",
        "SiLU",
        "Sigmoid",
        "Softmax",
        "Tanh",
        "Transformer",
    }
)


def _imports(tree: ast.AST) -> tuple[str, ...]:
    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            values.append(node.module)
    return tuple(values)


def _called_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def verify_sources() -> dict[str, object]:
    violations: list[str] = []
    imports_by_file: dict[str, list[str]] = {}
    source_sha256: dict[str, str] = {}
    for relative in _LIVE_FILES:
        path = _ROOT / relative
        source_bytes = path.read_bytes()
        source_sha256[relative] = hashlib.sha256(source_bytes).hexdigest()
        source = source_bytes.decode("utf-8")
        tree = ast.parse(source, filename=str(path))
        imports = sorted(_imports(tree))
        imports_by_file[relative] = imports
        for module in imports:
            root_module = module.split(".", 1)[0]
            if (
                (_ROOT / f"{root_module}.py").is_file()
                and root_module not in _ALLOWED_LOCAL_IMPORTS
            ):
                violations.append(
                    f"{relative}: non-native local import {module}"
                )
            if any(
                module == prefix or module.startswith(prefix + ".")
                for prefix in _BANNED_IMPORT_PREFIXES
            ):
                violations.append(f"{relative}: banned live import {module}")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = _called_name(node)
            if called in _BANNED_CALL_ATTRIBUTES:
                violations.append(f"{relative}:{node.lineno}: banned call {called}")
            if called in _BANNED_CONSTRUCTORS:
                violations.append(
                    f"{relative}:{node.lineno}: banned learned constructor {called}"
                )
    if violations:
        raise RuntimeError("\n".join(violations))
    return {
        "files": list(_LIVE_FILES),
        "imports": imports_by_file,
        "source_sha256": source_sha256,
        "violations": [],
    }


def verify_runtime() -> dict[str, object]:
    torch.set_num_threads(1)
    config_bytes = _CORPUS_CONFIG.read_bytes()
    config = QiFieldConfig.from_dict(json.loads(config_bytes.decode("utf-8")))
    controller = QiFieldController(config)
    training = json.loads(
        (_CORPUS_CHECKPOINT.parent / "training-receipt.json").read_text("utf-8")
    )
    example = training["generation"]["training_examples"][0]
    prompt = str(example["prompt"])
    expected_text = str(example["expected"])
    engine = CassiQiTextEngine(
        controller,
        checkpoint_path=_CORPUS_CHECKPOINT,
        max_output_symbols=int(training["experience"]["max_episode_bytes"]),
    )
    result = engine.generate(
        engine.initial_state(),
        ({"role": "user", "content": prompt},),
    )
    architecture = result.receipt_dict()["architecture"]
    expected = {
        "adaptive_persistent_tensor_count": 1,
        "engineered_feature_width": 0,
        "learned_parameter_count": 0,
        "neural_layer_count": 0,
        "optimizer_state_bytes": 0,
        "probabilistic_sampler": False,
        "state_layout": "[S,9M,B]",
        "corpus_trained": True,
        "external_adaptive_table_count": 0,
        "lexical_boundary": "none",
    }
    for key, value in expected.items():
        if architecture.get(key) != value:
            raise RuntimeError(
                f"runtime architecture gate failed for {key}: "
                f"expected {value!r}, got {architecture.get(key)!r}"
            )
    if not result.all_outputs_field_owned:
        raise RuntimeError("runtime emitted an unowned output symbol")
    if (
        not result.output_symbols
        or result.stop_reason != "end_turn"
        or result.text != expected_text
    ):
        raise RuntimeError(
            "runtime did not reproduce a stored corpus trajectory: "
            f"{result.text!r} ({result.stop_reason}); expected {expected_text!r}"
        )
    rendered, reply_kind = result.render_text(
        controller,
        len(prompt.encode("utf-8")),
    )
    if rendered != result.text or reply_kind != "field-symbols":
        raise RuntimeError("runtime output did not cross the field-symbol boundary")
    state_fields = tuple(result.state.__dataclass_fields__)
    if state_fields != ("field",):
        raise RuntimeError(
            f"Qi state must own exactly one tensor field, got {state_fields!r}"
        )
    if result.state.field.requires_grad or result.state.field.grad_fn is not None:
        raise RuntimeError("live Qi state is attached to an autograd graph")
    if any(
        isinstance(value, torch.nn.Parameter)
        for value in vars(engine).values()
    ):
        raise RuntimeError("live Qi text engine owns a neural parameter")
    if result.corpus_memory_sha256 != engine.corpus_memory_sha256:
        raise RuntimeError("runtime generation changed the trained corpus memory")
    return {
        "architecture": architecture,
        "codebook_fingerprint": result.codebook_fingerprint,
        "config_source_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "config_fingerprint": result.config_fingerprint,
        "engine_fingerprint": result.engine_fingerprint,
        "field_text_receipt_sha256": result.receipt_sha256,
        "final_state_sha256": result.final_state_sha256,
        "output_symbols": list(result.output_symbols),
        "prompt": prompt,
        "expected_text": expected_text,
        "output_text": result.text,
        "reply_kind": reply_kind,
        "corpus_memory_sha256": result.corpus_memory_sha256,
        "stop_reason": result.stop_reason,
    }


def main() -> int:
    receipt = {
        "runtime": verify_runtime(),
        "schema": "cassi.qi-native-runtime-gate.v4",
        "source": verify_sources(),
    }
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
