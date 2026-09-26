"""Canonical model graph and tensor packages for the regional field computer.

A package is an immutable executable description.  Mutable activations, model
memory, sampler state, and unfinished execution live only in the invoking
owner's regional task state.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from programs.python.records import ModelProgram, TensorView, canonical_json_bytes, digest_value


MODEL_PACKAGE_SCHEMA = "cassifi.model-package.v1"
TENSOR_PAYLOAD_SCHEMA = "cassifi.model-tensor-payload.v1"
_ALLOWED_DTYPES = {
    "f64",
    "f32",
    "f16",
    "bf16",
    "i64",
    "i32",
    "i16",
    "i8",
    "u32",
    "q8_0",
    "q8_1",
    "q2_k",
    "q3_k",
    "q4_0",
    "q4_1",
    "q4_k",
    "q5_0",
    "q5_1",
    "q5_k",
    "q6_k",
    "q8_k",
    "iq1_m",
    "iq1_s",
    "iq2_s",
    "iq2_xs",
    "iq2_xxs",
    "iq3_s",
    "iq3_xxs",
    "iq4_nl",
    "iq4_xs",
    "mxfp4",
    "nvfp4",
    "tq1_0",
    "tq2_0",
    "q1_0",
    "q2_0",
}
_ALLOWED_OPERATIONS = {
    "add",
    "attention",
    "conv1d",
    "copy",
    "embedding",
    "external-model",
    "native-transformer",
    "gelu",
    "matmul",
    "mul",
    "qwen-attention",
    "qwen-attention-route",
    "qwen-embedding",
    "qwen-experts",
    "qwen-ffn",
    "qwen-head",
    "qwen-layer",
    "qwen-route",
    "rope",
    "sample",
    "silu",
    "softmax",
}


class ModelRecordError(ValueError):
    """A model package is not canonical or executable."""


def _plain(value: Any) -> Any:
    try:
        return json.loads(canonical_json_bytes(value).decode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise ModelRecordError("model value is not canonical JSON") from exc


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 65_536:
        raise ModelRecordError(f"{label} must be bounded nonempty text")
    return value


def _positive(value: Any, label: str, *, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ModelRecordError(f"{label} must be an integer")
    if value < (0 if allow_zero else 1):
        raise ModelRecordError(f"{label} is outside its bound")
    return value


def _shape(value: Any, *, max_elements: int = 1_048_576) -> tuple[int, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or not value:
        raise ModelRecordError("tensor shape must be a nonempty sequence")
    shape = tuple(_positive(item, "tensor extent") for item in value)
    if math.prod(shape) > max_elements:
        raise ModelRecordError("tensor exceeds the package element bound")
    return shape


def _strides(shape: Sequence[int]) -> tuple[int, ...]:
    stride = 1
    result: list[int] = []
    for extent in reversed(shape):
        result.append(stride)
        stride *= extent
    return tuple(reversed(result))


def _number(value: Any, dtype: str) -> int | float:
    if dtype.startswith("f"):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ModelRecordError("floating tensor values must be numbers")
        result = float(value)
        if not math.isfinite(result):
            raise ModelRecordError("tensor values must be finite")
        return result
    if isinstance(value, bool) or not isinstance(value, int):
        raise ModelRecordError("integer tensor values must be integers")
    if dtype == "q8_0" and not -128 <= value <= 127:
        raise ModelRecordError("q8_0 value is outside int8 range")
    if dtype == "u32" and not 0 <= value <= 0xFFFFFFFF:
        raise ModelRecordError("u32 value is outside range")
    return int(value)


def canonical_tensor_payload(
    name: str,
    specification: Mapping[str, Any],
    *,
    owner_id: str,
    scope_id: str,
) -> Mapping[str, Any]:
    """Validate and freeze one packed or directly resident tensor payload."""

    if not isinstance(specification, Mapping):
        raise ModelRecordError("tensor specification must be a mapping")
    tensor_id = _text(str(specification.get("tensor_id", name)), "tensor_id")
    dtype = str(specification.get("dtype", "f64"))
    if dtype not in _ALLOWED_DTYPES:
        raise ModelRecordError("tensor dtype is unsupported")
    raw_values = specification.get("values")
    backing_sha256 = specification.get("backing_sha256")
    shape = _shape(
        specification.get("shape"),
        max_elements=1_048_576 if raw_values is not None else (1 << 63) - 1,
    )
    immutable = bool(specification.get("immutable", True))
    if raw_values is None and backing_sha256 is None:
        raise ModelRecordError("tensor requires values or immutable backing")
    values: list[int | float] | None = None
    if raw_values is not None:
        if isinstance(raw_values, (str, bytes)) or not isinstance(raw_values, Sequence):
            raise ModelRecordError("tensor values must be a sequence")
        values = [_number(item, dtype) for item in raw_values]
        if len(values) != math.prod(shape):
            raise ModelRecordError("tensor value count does not match shape")
    quantization = specification.get("quantization")
    if quantization is not None:
        quantization = _plain(quantization)
        if not isinstance(quantization, dict):
            raise ModelRecordError("quantization must be a mapping")
    if dtype == "q8_0" and raw_values is not None:
        if not isinstance(quantization, Mapping) or not isinstance(quantization.get("scale"), (int, float)):
            raise ModelRecordError("inline q8_0 requires a finite scale")
        if not math.isfinite(float(quantization["scale"])):
            raise ModelRecordError("q8_0 scale must be finite")
    if backing_sha256 is None and immutable:
        backing_sha256 = digest_value(
            {
                "dtype": dtype,
                "shape": list(shape),
                "values": values,
                "quantization": quantization,
            }
        )
    if backing_sha256 is not None:
        if not isinstance(backing_sha256, str) or len(backing_sha256) != 64:
            raise ModelRecordError("backing_sha256 must be a SHA-256 digest")
        try:
            bytes.fromhex(backing_sha256)
        except ValueError as exc:
            raise ModelRecordError("backing_sha256 must be a SHA-256 digest") from exc
    view = TensorView(
        tensor_id=tensor_id,
        owner_id=owner_id,
        scope_id=scope_id,
        shape=shape,
        dtype=dtype,
        strides=_strides(shape),
        quantization_layout=quantization,
        backing_sha256=backing_sha256 if immutable else None,
        mutable_version=None if immutable else int(specification.get("mutable_version", 0)),
        rights=tuple(str(item) for item in specification.get("rights", ("read",) if immutable else ("read", "write"))),
        dependencies=tuple(str(item) for item in specification.get("dependencies", ())),
    )
    backing = specification.get("backing")
    if backing is not None:
        backing = _plain(backing)
        if not immutable or not isinstance(backing, dict):
            raise ModelRecordError("tensor backing descriptor must be an immutable mapping")
    return {
        "schema": TENSOR_PAYLOAD_SCHEMA,
        "view": view.as_dict(),
        "values": values,
        "values_sha256": None if values is None else digest_value(values),
        "backing": backing,
        "placement": str(specification.get("placement", "logical-cpu")),
    }


def _canonical_operation(value: Mapping[str, Any], index: int) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ModelRecordError("graph operation must be a mapping")
    operation_id = _text(str(value.get("operation_id", f"op-{index}")), "operation_id")
    op = str(value.get("op", ""))
    if op not in _ALLOWED_OPERATIONS:
        raise ModelRecordError(f"unsupported model operation {op!r}")
    inputs = value.get("inputs", ())
    if isinstance(inputs, (str, bytes)) or not isinstance(inputs, Sequence):
        raise ModelRecordError("operation inputs must be a sequence")
    output = value.get("output")
    if output is not None:
        output = _text(output, "operation output")
    parameters = _plain(value.get("parameters", {}))
    state_effects = _plain(value.get("state_effects", []))
    if not isinstance(parameters, dict) or not isinstance(state_effects, list):
        raise ModelRecordError("operation parameters or effects are invalid")
    return {
        "operation_id": operation_id,
        "stage": _text(str(value.get("stage", "model")), "stage"),
        "op": op,
        "inputs": [_text(item, "operation input") for item in inputs],
        "output": output,
        "parameters": parameters,
        "state_effects": state_effects,
    }


@dataclass(frozen=True, slots=True)
class ModelPackage:
    """An identified graph, tensor manifest, tokenizer, and numerical profile."""

    program: ModelProgram
    graph: tuple[Mapping[str, Any], ...]
    tensors: Mapping[str, Mapping[str, Any]]
    tokenizer: Mapping[str, Any]
    primitive_contracts: tuple[str, ...]
    numerical_profile: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.program, ModelProgram):
            raise ModelRecordError("program must be a ModelProgram")
        graph = tuple(_canonical_operation(item, index) for index, item in enumerate(self.graph))
        if not graph:
            raise ModelRecordError("model graph cannot be empty")
        names: set[str] = set()
        for operation in graph:
            if operation["operation_id"] in names:
                raise ModelRecordError("model operation identity is duplicated")
            names.add(operation["operation_id"])
        tensors = _plain(dict(self.tensors))
        tokenizer = _plain(dict(self.tokenizer))
        profile = _plain(dict(self.numerical_profile))
        if not isinstance(tensors, dict) or not isinstance(tokenizer, dict) or not isinstance(profile, dict):
            raise ModelRecordError("model package mappings are invalid")
        if digest_value(list(graph)) != self.program.graph_sha256:
            raise ModelRecordError("model graph digest mismatch")
        manifest = {
            name: {
                "view": payload["view"],
                "values_sha256": payload.get("values_sha256"),
            }
            for name, payload in sorted(tensors.items())
        }
        if digest_value(manifest) != self.program.tensor_manifest_sha256:
            raise ModelRecordError("tensor manifest digest mismatch")
        if digest_value(tokenizer) != self.program.tokenizer_sha256:
            raise ModelRecordError("tokenizer digest mismatch")
        object.__setattr__(self, "graph", graph)
        object.__setattr__(self, "tensors", tensors)
        object.__setattr__(self, "tokenizer", tokenizer)
        object.__setattr__(self, "primitive_contracts", tuple(_text(item, "primitive contract") for item in self.primitive_contracts))
        object.__setattr__(self, "numerical_profile", profile)
        canonical_json_bytes(self.as_dict())

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "schema": MODEL_PACKAGE_SCHEMA,
            "program": self.program.as_dict(),
            "graph": [dict(item) for item in self.graph],
            "tensors": _plain(self.tensors),
            "tokenizer": _plain(self.tokenizer),
            "primitive_contracts": list(self.primitive_contracts),
            "numerical_profile": _plain(self.numerical_profile),
        }

    @property
    def sha256(self) -> str:
        return digest_value(self.as_dict())

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ModelPackage":
        if not isinstance(value, Mapping) or value.get("schema") != MODEL_PACKAGE_SCHEMA:
            raise ModelRecordError("model package schema is invalid")
        program_value = value.get("program")
        if not isinstance(program_value, Mapping) or program_value.get("schema") != ModelProgram.SCHEMA:
            raise ModelRecordError("model program record is invalid")
        kwargs = {key: item for key, item in program_value.items() if key != "schema"}
        return cls(
            program=ModelProgram(**kwargs),
            graph=tuple(value.get("graph", ())),
            tensors=value.get("tensors", {}),
            tokenizer=value.get("tokenizer", {}),
            primitive_contracts=tuple(value.get("primitive_contracts", ())),
            numerical_profile=value.get("numerical_profile", {}),
        )


def build_model_package(
    *,
    program_id: str,
    architecture: str,
    graph: Sequence[Mapping[str, Any]],
    tensors: Mapping[str, Mapping[str, Any]],
    tokenizer: Mapping[str, Any],
    owner_id: str = "shared-import",
    scope_id: str = "model",
    quantization_profile: Mapping[str, Any] | None = None,
    operation_versions: Mapping[str, str] | None = None,
    assessment: Mapping[str, Any] | None = None,
    primitive_contracts: Sequence[str] = ("bounded-tensor-v1", "model-continuation-v1"),
    numerical_profile: Mapping[str, Any] | None = None,
) -> ModelPackage:
    """Build and digest one executable package from explicit graph components."""

    canonical_graph = tuple(_canonical_operation(item, index) for index, item in enumerate(graph))
    canonical_tensors = {
        _text(name, "tensor name"): canonical_tensor_payload(
            name,
            specification,
            owner_id=owner_id,
            scope_id=scope_id,
        )
        for name, specification in sorted(tensors.items())
    }
    canonical_tokenizer = _plain(dict(tokenizer))
    manifest = {
        name: {
            "view": payload["view"],
            "values_sha256": payload.get("values_sha256"),
        }
        for name, payload in sorted(canonical_tensors.items())
    }
    program = ModelProgram(
        program_id=_text(program_id, "program_id"),
        graph_sha256=digest_value(list(canonical_graph)),
        tensor_manifest_sha256=digest_value(manifest),
        tokenizer_sha256=digest_value(canonical_tokenizer),
        architecture=_text(architecture, "architecture"),
        quantization_profile=dict(quantization_profile or {"weights": "f64", "activations": "f64"}),
        operation_versions=dict(operation_versions or {name: "v1" for name in sorted({item["op"] for item in canonical_graph})}),
        entry=str(canonical_graph[0]["operation_id"]),
        assessment=dict(assessment or {"origin": "imported", "status": "admitted"}),
    )
    return ModelPackage(
        program=program,
        graph=canonical_graph,
        tensors=canonical_tensors,
        tokenizer=canonical_tokenizer,
        primitive_contracts=tuple(primitive_contracts),
        numerical_profile=dict(numerical_profile or {"arithmetic": "binary64", "fast_math": False}),
    )


__all__ = [
    "MODEL_PACKAGE_SCHEMA",
    "ModelPackage",
    "ModelRecordError",
    "TENSOR_PAYLOAD_SCHEMA",
    "build_model_package",
    "canonical_tensor_payload",
]
