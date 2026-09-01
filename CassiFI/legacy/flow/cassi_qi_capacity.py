"""W6A intrinsic live-state admissible-capacity law.

This module is deliberately offline and immutable.  It consumes the public
W6T geometry, topology-codebook, port, and scattering surfaces, materializes a
finite Cartesian candidate universe, and then removes candidates which are
provably dark, null, or colliding.  No result is stored in ``QiFieldState``
and no semantic/task interpretation is accepted at this boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from types import MappingProxyType
from typing import Any, Mapping

import torch

from cassi_qi_profile import canonical_hash, finite_bits
from cassi_qi_scattering import (
    CANDIDATE_MODE_IDS,
    QiPortDescriptor,
    QiScaleGeometryCandidate,
    QiScaleGeometryComparisonReceipt,
    QiScaleGeometryProfile,
    QiScatteringReceipt,
    QiTopologyCodebookEvidence,
    validate_scattering_receipt,
    validate_scale_geometry_comparison,
    validate_topology_codebook_evidence,
)


INTRINSIC_CAPACITY_PROFILE_SCHEMA = "cassi.qi-flow-intrinsic-capacity-profile.v1"
INTRINSIC_CAPACITY_RECEIPT_SCHEMA = "cassi.qi-flow-intrinsic-capacity-receipt.v1"
INTRINSIC_CAPACITY_CANDIDATE_SCHEMA = "cassi.qi-flow-intrinsic-capacity-candidate.v1"
INTRINSIC_CAPACITY_PROOF_SCHEMA = "cassi.qi-flow-intrinsic-capacity-proof.v1"
INTRINSIC_CAPACITY_PROFILE_DOMAIN = INTRINSIC_CAPACITY_PROFILE_SCHEMA
INTRINSIC_CAPACITY_RECEIPT_DOMAIN = INTRINSIC_CAPACITY_RECEIPT_SCHEMA
INTRINSIC_CAPACITY_CANDIDATE_DOMAIN = INTRINSIC_CAPACITY_CANDIDATE_SCHEMA
INTRINSIC_CAPACITY_PROOF_DOMAIN = INTRINSIC_CAPACITY_PROOF_SCHEMA
TOPOLOGY_CODEWORD_DOMAIN = "cassi.qi-flow-topology-codeword.v1"
STATE_LAYOUT_DOMAIN = "cassi.qi-flow-state-layout.v3"
PORT_SET_DOMAIN = "cassi.qi-flow-intrinsic-port-set.v1"
ENUMERATION_DOMAIN = "cassi.qi-flow-intrinsic-capacity-enumeration.v1"
GEOMETRY_CANDIDATE_DOMAIN = "cassi.qi-flow-scale-geometry-candidate.v1"


class IntrinsicCapacityError(ValueError):
    """Raised when the finite intrinsic-capacity contract is not admissible."""


QiCapacityError = IntrinsicCapacityError


_FORBIDDEN_LABEL_KEYS = {
    "semantic",
    "semantic_label",
    "task",
    "task_label",
    "task_id",
    "meaning",
    "intent",
    "class_label",
    "target_label",
    "category_label",
    "label",
}


def _source_surface(value: Any) -> Any:
    """Normalize public payload containers without changing numeric encoding."""
    if isinstance(value, Mapping):
        return {str(key): _source_surface(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_source_surface(item) for item in value]
    if torch.is_tensor(value):
        return _source_surface(value.detach().cpu().tolist())
    return value


def _external_canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _external_canonical(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_external_canonical(item) for item in value]
    if isinstance(value, complex):
        return {"re": finite_bits(float(value.real)), "im": finite_bits(float(value.imag))}
    if isinstance(value, float):
        return finite_bits(value)
    return value


def _external_hash(value: Any, domain: str) -> str:
    return str(canonical_hash(_external_canonical(value), domain))


def _f64_tag(value: float) -> str:
    result = float(value)
    if not math.isfinite(result) or (result == 0.0 and math.copysign(1.0, result) < 0.0):
        raise IntrinsicCapacityError("capacity values must be finite non-negative-zero f64")
    return finite_bits(result)


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if torch.is_tensor(value):
        return _plain(value.detach().cpu().tolist())
    if isinstance(value, complex):
        return [_f64_tag(float(value.real)), _f64_tag(float(value.imag))]
    if isinstance(value, float):
        return _f64_tag(value)
    return value


def _hash(value: Any, domain: str) -> str:
    return str(canonical_hash(_plain(value), domain))


def _tensor_hash(value: torch.Tensor, domain: str) -> str:
    tensor = value.detach().contiguous().to(device="cpu", dtype=torch.float64)
    raw = tensor.numpy().astype("<f8", copy=False).tobytes(order="C")
    return _hash(
        {
            "dtype": "float64-le",
            "shape": [int(item) for item in tensor.shape],
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        },
        domain,
    )

def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value == value.lower()


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    if torch.is_tensor(value):
        return tuple(_freeze(item) for item in value.detach().cpu().tolist())
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise IntrinsicCapacityError(message)


def _int(name: str, value: Any, *, minimum: int = 0) -> int:
    _require(isinstance(value, int) and not isinstance(value, bool) and value >= minimum, f"{name} must be an integer >= {minimum}")
    return int(value)


def _text(name: str, value: Any, *, allow_empty: bool = False) -> str:
    _require(isinstance(value, str) and (allow_empty or bool(value)), f"{name} must be a nonempty string")
    return value


def _reject_labels(value: Any, *, path: str = "input") -> None:
    """Reject semantic/task labels before they can influence enumeration."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).lower()
            _require(key_text not in _FORBIDDEN_LABEL_KEYS, f"{path}.{key} is a semantic/task label")
            _require(not key_text.endswith("_semantic") and not key_text.endswith("_task"), f"{path}.{key} is a semantic/task label")
            _reject_labels(item, path=f"{path}.{key}")
    elif isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            _reject_labels(item, path=f"{path}[{index}]")


def _source_payload(value: Any, *, name: str) -> Mapping[str, Any]:
    payload = value.payload() if callable(getattr(value, "payload", None)) else getattr(value, "payload", value)
    _require(isinstance(payload, Mapping), f"{name} has no immutable public payload")
    return _source_surface(payload)


def _attr(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _interval(value: Any, *, name: str) -> tuple[float, float, bool]:
    if hasattr(value, "lower") and hasattr(value, "upper"):
        lower, upper, resolved = value.lower, value.upper, getattr(value, "resolved", True)
    elif isinstance(value, Mapping):
        if "lower" in value and "upper" in value:
            lower, upper, resolved = value["lower"], value["upper"], value.get("resolved", True)
        elif "value" in value:
            lower = upper = value["value"]
            resolved = True
        else:
            raise IntrinsicCapacityError(f"{name} interval is incomplete")
    elif isinstance(value, (tuple, list)) and len(value) == 2:
        lower, upper, resolved = value[0], value[1], True
    else:
        lower = upper = value
        resolved = True
    _require(isinstance(resolved, bool), f"{name} interval resolved flag is invalid")
    try:
        lo, hi = float(lower), float(upper)
    except (TypeError, ValueError) as exc:
        raise IntrinsicCapacityError(f"{name} interval is not numeric") from exc
    _require(math.isfinite(lo) and math.isfinite(hi) and lo <= hi, f"{name} interval is not finite/ordered")
    _require(resolved, f"{name} interval is unresolved")
    return lo, hi, True


def _number(value: Any, *, name: str) -> float | complex:
    _require(not isinstance(value, bool), f"{name} cannot be boolean")
    _require(isinstance(value, (int, float, complex)), f"{name} must be numeric")
    result = complex(value) if isinstance(value, complex) else float(value)
    if isinstance(result, complex):
        _require(math.isfinite(result.real) and math.isfinite(result.imag), f"{name} is non-finite")
    else:
        _require(math.isfinite(result), f"{name} is non-finite")
    return value


def _flatten_numbers(value: Any, *, name: str) -> tuple[float | complex, ...]:
    if isinstance(value, Mapping):
        # A structured codeword is accepted only through its numeric values;
        # labels have already been rejected by _reject_labels.
        values: list[float | complex] = []
        for key in sorted(value, key=str):
            values.extend(_flatten_numbers(value[key], name=f"{name}.{key}"))
        return tuple(values)
    if isinstance(value, (tuple, list)):
        values: list[float | complex] = []
        for index, item in enumerate(value):
            values.extend(_flatten_numbers(item, name=f"{name}[{index}]"))
        return tuple(values)
    return (_number(value, name=name),)


def _codeword_hash(value: Any) -> str:
    return _hash(value, TOPOLOGY_CODEWORD_DOMAIN)


def _sector_parts(word: Any, *, name: str) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...], bool]:
    """Return (cycle-x, cycle-y, plaquette, structured)."""
    _reject_labels(word, path=name)
    if isinstance(word, Mapping):
        aliases = (
            ("n_x", "n_topo_x", "cycle_x", "nx", "x_cycle"),
            ("n_y", "n_topo_y", "cycle_y", "ny", "y_cycle"),
            ("p", "p_topo", "plaquette", "plaquettes", "vorticity"),
        )
        parts: list[Any] = []
        for choices in aliases:
            found = next((word[key] for key in choices if key in word), None)
            _require(found is not None, f"{name} is missing a complete topology sector vector")
            parts.append(found)
        return tuple(tuple(_flatten_numbers(item, name=f"{name}.{index}")) for index, item in enumerate(parts)) + (True,)  # type: ignore[return-value]
    if isinstance(word, (tuple, list)) and len(word) == 3 and all(isinstance(item, (tuple, list)) for item in word):
        return tuple(tuple(_flatten_numbers(item, name=f"{name}.{index}")) for index, item in enumerate(word)) + (True,)  # type: ignore[return-value]
    flat = tuple(_flatten_numbers(word, name=name))
    _require(flat, f"{name} cannot be empty")
    return flat, (), (), False


def _codeword_dimensions(word: Any, *, resolution: tuple[int, int]) -> tuple[dict[str, int], bool]:
    first, second, third, structured = _sector_parts(word, name="topology codeword")
    if structured:
        ny, nx = resolution
        _require(len(first) == ny and len(second) == nx and len(third) == ny * nx, "topology sector vector dimensions do not match selected resolution")
        return {"cycle_x": ny, "cycle_y": nx, "plaquette": ny * nx, "total": ny + nx + ny * nx}, True
    return {"flat": len(first), "total": len(first)}, False


def _normalise_codebook(codebook: Any, *, resolution: tuple[int, int], remap: Any = None) -> tuple[Mapping[str, Any], tuple[Any, ...], tuple[str, ...], dict[str, int], str, str]:
    payload = _source_payload(codebook, name="topology codebook")
    _require(bool(payload.get("schema")), "topology codebook schema is missing")
    _require(payload.get("schema") == getattr(codebook, "schema", payload.get("schema")) or isinstance(codebook, Mapping), "topology codebook schema is not public immutable evidence")
    raw_words = _attr(codebook, "codewords", payload.get("codewords"))
    raw_witnesses = _attr(codebook, "witness_hashes", payload.get("witness_hashes"))
    if isinstance(codebook, QiTopologyCodebookEvidence):
        try:
            validate_topology_codebook_evidence(
                codebook,
                resolution=resolution,
                periodic_fft_identity=str(_attr(codebook, "periodic_fft_identity")),
                metric_identity=str(_attr(codebook, "metric_identity")),
                operator_identity=str(_attr(codebook, "operator_identity")),
                remap=None,
            )
        except Exception as exc:
            raise IntrinsicCapacityError("topology codebook public validation failed") from exc
    _require(isinstance(raw_words, (tuple, list)) and raw_words, "topology codebook registry is incomplete")
    _require(isinstance(raw_witnesses, (tuple, list)) and len(raw_witnesses) == len(raw_words), "topology witness registry is incomplete")
    words = tuple(_freeze(word) for word in raw_words)
    word_hashes = tuple(_codeword_hash(word) for word in words)
    _require(len(set(word_hashes)) == len(word_hashes), "topology codebook contains duplicate codewords")
    witnesses = tuple(_text("topology witness hash", str(item)) for item in raw_witnesses)
    if hasattr(codebook, "resolution"):
        _require(tuple(_attr(codebook, "resolution")) == tuple(resolution), "topology codebook resolution mismatch")
    elif payload.get("resolution") is not None:
        _require(tuple(payload["resolution"]) == tuple(resolution), "topology codebook resolution mismatch")
    for name in ("realizable", "resolution_scaled", "zero_clock_remap_preserved"):
        value = _attr(codebook, name, payload.get(name, True))
        _require(value is True, f"topology codebook {name} is not proven")
    remap_identity = str(_attr(codebook, "zero_clock_remap_identity", payload.get("zero_clock_remap_identity", "")))
    _require(bool(remap_identity), "topology codebook has no zero-clock remap identity")
    dimensions, structured = _codeword_dimensions(words[0], resolution=resolution)
    for word in words[1:]:
        other, other_structured = _codeword_dimensions(word, resolution=resolution)
        _require(other == dimensions and other_structured == structured, "topology codeword dimensions are inconsistent")
    if structured:
        # Topological vectors are integer sectors, not arbitrary continuous labels.
        for word in words:
            first, second, third, _ = _sector_parts(word, name="topology codeword")
            for part in (first, second, third):
                _require(all(isinstance(item, int) and not isinstance(item, bool) for item in part), "topology sector entries must be integers")
    if remap is not None:
        _validate_remap(remap, words, word_hashes, remap_identity)
    payload_without_self = dict(payload)
    payload_without_self.pop("self_sha256", None)
    supplied_hash = str(_attr(codebook, "self_sha256", payload.get("self_sha256", "")))
    _require(_is_sha256(supplied_hash), "topology codebook identity is missing")
    if _external_hash(payload_without_self, str(payload.get("schema", "cassi.qi-flow-topology-codebook-resolution.v1"))) != supplied_hash:
        raise IntrinsicCapacityError("topology codebook identity mismatch")
    return MappingProxyType(_plain(payload_without_self)), words, witnesses, dimensions, supplied_hash, remap_identity


def _validate_remap(remap: Any, words: tuple[Any, ...], hashes: tuple[str, ...], remap_identity: str) -> None:
    if isinstance(remap, Mapping) and "preserved" in remap:
        _require(remap.get("preserved") is True, "zero-clock remap does not preserve the topology codebook")
        _require(str(remap.get("identity", remap_identity)) == remap_identity, "zero-clock remap identity mismatch")
        return
    _require(isinstance(remap, Mapping), "zero-clock remap must be a complete mapping")
    mapped: list[str] = []
    for word, word_hash in zip(words, hashes):
        candidate = remap.get(word_hash)
        if candidate is None:
            try:
                candidate = remap.get(word)
            except TypeError:
                candidate = None
        _require(candidate is not None, "zero-clock remap is incomplete")
        mapped.append(_codeword_hash(candidate))
    _require(set(mapped) == set(hashes) and len(mapped) == len(set(mapped)), "zero-clock remap changes or aliases the codebook")


def _selected_candidate(geometry: Any, selected_geometry: Any = None) -> tuple[Any, Mapping[str, Any], Mapping[str, Any]]:
    source = selected_geometry if selected_geometry is not None else geometry
    if isinstance(source, QiScaleGeometryComparisonReceipt) or (hasattr(source, "selected_mode") and hasattr(source, "candidates")):
        try:
            validate_scale_geometry_comparison(source)
        except Exception as exc:
            raise IntrinsicCapacityError("scale geometry comparison public validation failed") from exc
        mode = _attr(source, "selected_mode")
        _require(mode in CANDIDATE_MODE_IDS, "selected geometry mode is not registered")
        candidates = _attr(source, "candidates")
        _require(isinstance(candidates, Mapping) and mode in candidates, "selected geometry candidate is missing")
        candidate = candidates[mode]
        profile_payload = _source_payload(_attr(source, "profile"), name="scale geometry profile") if _attr(source, "profile") is not None else {}
        return candidate, _source_payload(candidate, name="selected geometry candidate"), profile_payload
    if isinstance(source, QiScaleGeometryProfile) or (hasattr(source, "scale_geometry_mode") and hasattr(source, "candidate_profile_hashes")):
        mode = _attr(source, "scale_geometry_mode")
        _require(mode in CANDIDATE_MODE_IDS, "scale geometry profile has no selected mode")
        candidate = _attr(source, "selected_candidate", None)
        _require(candidate is not None, "scale geometry profile requires its selected immutable candidate")
        return candidate, _source_payload(candidate, name="selected geometry candidate"), _source_payload(source, name="scale geometry profile")
    payload = _source_payload(source, name="selected geometry")
    mode = _attr(source, "mode_id", payload.get("mode_id"))
    _require(mode in CANDIDATE_MODE_IDS or bool(mode), "selected geometry mode is missing")
    return source, payload, {}


def _normalise_geometry(geometry: Any, selected_geometry: Any = None) -> tuple[Mapping[str, Any], Mapping[str, Any], str, tuple[tuple[int, int], ...], tuple[int, ...], int, str, tuple[Mapping[str, Any], ...]]:
    candidate, candidate_payload, profile_payload = _selected_candidate(geometry, selected_geometry)
    mode = str(_attr(candidate, "mode_id", candidate_payload.get("mode_id", "")))
    _require(mode in CANDIDATE_MODE_IDS, "selected geometry mode is not registered")
    for interval_name in ("rank_interval", "condition_interval", "cross_talk_interval", "work_interval", "cost_interval", "physical_horizon"):
        interval_value = _attr(candidate, interval_name, None)
        if interval_value is not None:
            _interval(interval_value, name=f"geometry.{interval_name}")
    shapes_raw = _attr(candidate, "active_shapes", candidate_payload.get("active_shapes"))
    counts_raw = _attr(candidate, "active_site_counts", candidate_payload.get("active_site_counts"))
    _require(isinstance(shapes_raw, (tuple, list)) and shapes_raw, "selected geometry has no complete active shape registry")
    _require(all(isinstance(shape, (tuple, list)) and len(shape) == 2 for shape in shapes_raw), "active shapes must be [Ny,Nx]")
    shapes = tuple((_int("active Ny", int(shape[0]), minimum=1), _int("active Nx", int(shape[1]), minimum=1)) for shape in shapes_raw)
    _require(isinstance(counts_raw, (tuple, list)), "selected geometry has no complete active site-count registry")
    counts = tuple(_int("active site count", int(value), minimum=1) for value in counts_raw)
    _require(tuple(ny * nx for ny, nx in shapes) == counts, "active shapes/counts disagree")
    packed_raw = _attr(candidate, "packed_mode_count", candidate_payload.get("packed_mode_count"))
    _require(packed_raw is not None, "selected geometry packed mode count is missing")
    mode_count = _int("packed mode count", int(packed_raw), minimum=max(counts))
    batch_raw = _attr(candidate, "batch_lanes", candidate_payload.get("batch_lanes"))
    _require(batch_raw is not None, "selected geometry batch registry is missing")
    candidate_batch = _int("geometry batch lanes", int(batch_raw), minimum=1)
    candidate_hash = str(_attr(candidate, "candidate_sha256", candidate_payload.get("candidate_sha256", "")))
    _require(_is_sha256(candidate_hash), "selected geometry candidate identity is missing")
    candidate_without_hash = dict(candidate_payload)
    candidate_without_hash.pop("candidate_sha256", None)
    if _external_hash(candidate_without_hash, GEOMETRY_CANDIDATE_DOMAIN) != candidate_hash:
        raise IntrinsicCapacityError("selected geometry candidate identity mismatch")
    operator_rows: list[Mapping[str, Any]] = []
    maps = _attr(candidate, "restriction_maps", candidate_payload.get("restriction_maps", ()))
    adjoints = _attr(candidate, "adjoint_maps", candidate_payload.get("adjoint_maps", ()))
    if maps or adjoints:
        _require(len(maps) == len(shapes) - 1 and len(adjoints) == len(shapes) - 1, "selected geometry scale-link registry is incomplete")
        for index, (mapping, adjoint) in enumerate(zip(maps, adjoints)):
            map_tensor = _matrix(mapping, name=f"geometry restriction map {index}")
            adjoint_tensor = _matrix(adjoint, name=f"geometry adjoint map {index}")
            _require(tuple(adjoint_tensor.shape) == (map_tensor.shape[1], map_tensor.shape[0]), f"geometry adjoint map {index} shape mismatch")
            operator_rows.append(MappingProxyType({"link": index, "restriction": _matrix_plain(map_tensor), "adjoint": _matrix_plain(adjoint_tensor)}))
    registered_ranks = _attr(candidate, "effective_ranks", candidate_payload.get("effective_ranks", ()))
    registered_nulls = _attr(candidate, "nullspace_dimensions", candidate_payload.get("nullspace_dimensions", ()))
    if maps:
        _require(len(registered_ranks) == len(maps) and len(registered_nulls) == len(maps), "selected geometry rank/nullspace registry is incomplete")
        for index, row in enumerate(operator_rows):
            mapping = _matrix(row["restriction"], name="geometry restriction")
            rank = _matrix_rank(mapping)
            _require(int(registered_ranks[index]) == rank, f"selected geometry rank mismatch at link {index}")
            _require(int(registered_nulls[index]) == int(mapping.shape[1]) - rank, f"selected geometry nullspace mismatch at link {index}")
    geometry_payload = MappingProxyType({"candidate": candidate_without_hash, "profile": profile_payload, "mode": mode, "batch_lanes": candidate_batch})
    return geometry_payload, MappingProxyType(candidate_payload), mode, shapes, counts, mode_count, candidate_hash, tuple(operator_rows)
def _normalise_state_layout(state_layout: Any, *, shapes: tuple[tuple[int, int], ...], mode_count: int) -> tuple[Mapping[str, Any], str, int]:
    if state_layout is None:
        raise IntrinsicCapacityError("state layout registry is required")
    raw = _attr(state_layout, "state_layout", state_layout)
    payload = _plain(raw)
    _require(isinstance(payload, Mapping), "state layout is not a mapping")
    _require(payload.get("layout_id") == "cassi.qi-flow-state-layout.v3", "state layout is not v3")
    scale_count = _int("state scale count", int(payload.get("scale_count", -1)), minimum=1)
    components = _int("state component count", int(payload.get("component_count", -1)), minimum=1)
    packed = _int("state mode count", int(payload.get("mode_count", -1)), minimum=1)
    batch = _int("state batch limit", int(payload.get("batch_limit", -1)), minimum=1)
    _require(scale_count == len(shapes) and components == 9 and packed == mode_count, "state layout does not match selected geometry")
    declared_shapes = payload.get("active_shapes")
    _require(isinstance(declared_shapes, (tuple, list)) and tuple(tuple(int(v) for v in item) for item in declared_shapes) == shapes, "state active-shape registry mismatch")
    declared_counts = payload.get("active_site_counts")
    _require(isinstance(declared_counts, (tuple, list)) and tuple(int(v) for v in declared_counts) == tuple(ny * nx for ny, nx in shapes), "state active-count registry mismatch")
    shape = payload.get("shape", (scale_count, 9 * packed, batch))
    _require(isinstance(shape, (tuple, list)) and len(shape) == 3 and int(shape[0]) == scale_count and int(shape[1]) == 9 * packed and (shape[2] is None or int(shape[2]) == batch), "state shape is not [S,9M,B]")
    layout_without_identity = dict(payload)
    layout_without_identity["shape"] = [scale_count, 9 * packed, batch]
    supplied = layout_without_identity.pop("state_layout_sha256", None)
    identity = _hash(layout_without_identity, STATE_LAYOUT_DOMAIN)
    if supplied is not None:
        _require(str(supplied) == identity, "state layout identity mismatch")
    return MappingProxyType(_plain(layout_without_identity)), identity, batch

def _matrix_cell(value: Any) -> complex | float | int:
    if isinstance(value, Mapping) and set(value) >= {"real", "imag"}:
        return complex(float(value["real"]), float(value["imag"]))
    return value


def _matrix(value: Any, *, name: str) -> torch.Tensor:
    if torch.is_tensor(value):
        tensor = value.detach().cpu()
        _require(tensor.ndim == 2, f"{name} must be a matrix")
        _require(tensor.dtype in (torch.float32, torch.float64, torch.complex64, torch.complex128), f"{name} has unsupported dtype")
        tensor = tensor.to(torch.complex128).contiguous()
    else:
        try:
            if isinstance(value, (tuple, list)):
                value = [[_matrix_cell(cell) for cell in row] for row in value]
            tensor = torch.tensor(value, dtype=torch.complex128)
        except Exception as exc:
            raise IntrinsicCapacityError(f"{name} is not a matrix") from exc
        _require(tensor.ndim == 2, f"{name} must be a matrix")
    _require(bool(torch.isfinite(tensor.real).all().item()) and bool(torch.isfinite(tensor.imag).all().item()), f"{name} contains nonfinite values")
    return tensor


def _matrix_plain(value: torch.Tensor) -> tuple[tuple[Any, ...], ...]:
    rows: list[tuple[Any, ...]] = []
    for row in value.detach().cpu():
        cells: list[Any] = []
        for item in row:
            number = complex(item.item())
            cells.append(float(number.real) if number.imag == 0.0 else {"real": float(number.real), "imag": float(number.imag)})
        rows.append(tuple(cells))
    return tuple(rows)


def _matrix_rank(value: torch.Tensor) -> int:
    if value.numel() == 0 or value.shape[0] == 0 or value.shape[1] == 0:
        return 0
    singular = torch.linalg.svdvals(value)
    maximum = float(singular.max().item()) if singular.numel() else 0.0
    tolerance = maximum * 1.0e-12
    return int(torch.count_nonzero(singular > tolerance).item())


def _normalise_ports(ports: Any, *, mode: str, scales: int, geometry_hash: str) -> tuple[tuple[Mapping[str, Any], ...], str]:
    provided_identity = _attr(ports, "self_sha256", None)
    if isinstance(ports, Mapping) and "ports" in ports:
        provided_identity = ports.get("self_sha256", provided_identity)
        ports = ports["ports"]
    elif hasattr(ports, "ports"):
        ports = _attr(ports, "ports")
    _require(isinstance(ports, (tuple, list)) and ports, "port registry is incomplete")
    rows: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    covered: set[int] = set()
    for item in ports:
        payload = _source_payload(item, name="port descriptor")
        port_id = str(_attr(item, "port_id", payload.get("port_id", "")))
        _require(port_id and port_id not in seen, "port registry has a missing or duplicate port id")
        seen.add(port_id)
        item_mode = str(_attr(item, "scale_geometry_mode", payload.get("scale_geometry_mode", mode)))
        _require(item_mode == mode, "port scale-geometry mode mismatch")
        kind = str(_attr(item, "kind", payload.get("kind", "")))
        _require(kind in {"internal", "external"}, "port kind is invalid")
        source = _attr(item, "source_scale", payload.get("source_scale"))
        target = _attr(item, "target_scale", payload.get("target_scale"))
        for scale in (source, target):
            if scale is not None:
                _require(isinstance(scale, int) and 0 <= scale < scales, "port scale is outside selected geometry")
                covered.add(int(scale))
        orientation = int(_attr(item, "orientation", payload.get("orientation", 1)))
        _require(orientation in {-1, 1}, "port orientation is invalid")
        descriptor_hash = str(_attr(item, "descriptor_sha256", payload.get("descriptor_sha256", "")))
        _require(_is_sha256(descriptor_hash), "port descriptor identity is missing")
        descriptor_payload = dict(payload)
        descriptor_payload.pop("descriptor_sha256", None)
        _require(_external_hash(descriptor_payload, "cassi.qi-flow-port-descriptor.v1") == descriptor_hash, "port descriptor identity mismatch")
        profile_hash = str(_attr(item, "profile_sha256", payload.get("profile_sha256", "")))
        if profile_hash:
            _require(profile_hash == geometry_hash or _is_sha256(profile_hash), "port profile identity is invalid")
        rows.append(MappingProxyType({"payload": descriptor_payload, "port_id": port_id, "kind": kind, "source_scale": source, "target_scale": target, "orientation": orientation, "scale_geometry_mode": item_mode, "descriptor_sha256": descriptor_hash, "profile_sha256": profile_hash}))
    rows.sort(key=lambda row: (row["source_scale"] is None, row["source_scale"] if row["source_scale"] is not None else -1, row["target_scale"] is None, row["target_scale"] if row["target_scale"] is not None else -1, row["port_id"]))
    identity = _hash([dict(row) for row in rows], PORT_SET_DOMAIN)
    if provided_identity is not None:
        _require(_is_sha256(str(provided_identity)) and str(provided_identity) == identity, "port set identity mismatch")
    return tuple(rows), identity


def _operator_entry(value: Any, *, port_id: str, port: Mapping[str, Any]) -> Mapping[str, Any]:
    role = None
    scale = port["source_scale"] if port["source_scale"] is not None else port["target_scale"]
    if isinstance(value, Mapping):
        scale = value.get("scale", scale)
        role = value.get("role")
        reach = value.get("reachability", value.get("source", value.get("B")))
        observe = value.get("observability", value.get("readout", value.get("target", value.get("C"))))
        channel = value.get("matrix", value.get("operator", value.get("P")))
    else:
        reach = observe = channel = value
    _require(isinstance(scale, int) and scale >= 0, f"operator {port_id} needs an explicit scale")
    if reach is None and observe is None and channel is None:
        raise IntrinsicCapacityError(f"operator {port_id} has no matrix")
    if channel is not None and reach is None and observe is None:
        _require(role in {"channel", "both", None}, f"operator {port_id} role is invalid")
        if port["kind"] == "internal" or role == "channel":
            return MappingProxyType({"scale": scale, "channel": _matrix(channel, name=f"operator {port_id}")})
        _require(role in {"reachability", "observability", "both"}, f"operator {port_id} role is required for an external matrix")
        if role == "reachability":
            reach = channel
        elif role == "observability":
            observe = channel
        else:
            reach = observe = channel
    _require(role in {None, "both", "reachability", "observability"}, f"operator {port_id} role is invalid")
    result: dict[str, Any] = {"scale": scale}
    if reach is not None:
        result["reachability"] = _matrix(reach, name=f"operator {port_id} reachability")
    if observe is not None:
        result["observability"] = _matrix(observe, name=f"operator {port_id} observability")
    return MappingProxyType(result)


def _normalise_operators(operators: Any, *, ports: tuple[Mapping[str, Any], ...], scales: int) -> tuple[Mapping[str, Any], ...]:
    if hasattr(operators, "operators"):
        operators = _attr(operators, "operators")
    _require(isinstance(operators, Mapping), "fixed port/scattering operator registry is incomplete")
    known_ids = {str(port["port_id"]) for port in ports}
    extras = set(str(key) for key in operators) - known_ids - {"operator", "matrix"}
    _require(not extras, "fixed operator registry contains undeclared ports")
    rows: list[Mapping[str, Any]] = []
    for port in ports:
        port_id = str(port["port_id"])
        raw = operators.get(port_id)
        if raw is None and len(ports) == 1:
            raw = operators.get("operator", operators.get("matrix"))
        _require(raw is not None, f"missing fixed operator for port {port_id}")
        entry = _operator_entry(raw, port_id=port_id, port=port)
        _require(int(entry["scale"]) < scales, f"operator {port_id} scale is outside geometry")
        declared_scales = {value for value in (port["source_scale"], port["target_scale"]) if value is not None}
        _require(not declared_scales or int(entry["scale"]) in declared_scales, f"operator {port_id} scale disagrees with port descriptor")
        payload: dict[str, Any] = {"port_id": port_id, "scale": entry["scale"]}
        for key in ("reachability", "observability", "channel"):
            if key in entry:
                payload[key] = _matrix_plain(entry[key])
        rows.append(MappingProxyType(payload))
    return tuple(rows)


def _aggregate_operator_rows(operators: tuple[Mapping[str, Any], ...], ports: tuple[Mapping[str, Any], ...], *, scales: int, batch_limit: int) -> tuple[Mapping[str, Any], ...]:
    by_scale: list[list[Mapping[str, Any]]] = [[] for _ in range(scales)]
    for op in operators:
        by_scale[int(op["scale"])].append(op)
    port_by_id = {str(row["port_id"]): row for row in ports}
    result: list[Mapping[str, Any]] = []
    for scale in range(scales):
        reach_matrices: list[torch.Tensor] = []
        observe_matrices: list[torch.Tensor] = []
        channel_sources: list[tuple[torch.Tensor, Mapping[str, Any]]] = []
        for op in by_scale[scale]:
            if "reachability" in op:
                reach_matrices.append(_matrix(op["reachability"], name=f"operator {op['port_id']} reachability"))
            if "observability" in op:
                observe_matrices.append(_matrix(op["observability"], name=f"operator {op['port_id']} observability"))
        for op in operators:
            if "channel" in op:
                port = port_by_id[str(op["port_id"])]
                channel_sources.append((_matrix(op["channel"], name=f"operator {op['port_id']} channel"), port))
        # Internal P maps are channels: the source receives the readout row
        # space and the target receives the reachable column space.
        for matrix, port in channel_sources:
            source, target = port["source_scale"], port["target_scale"]
            _require(source is not None and target is not None, f"channel operator {port['port_id']} needs source/target scales")
            if scale == target:
                reach_matrices.append(matrix)
            if scale == source:
                observe_matrices.append(matrix)
        state_dims = set()
        if reach_matrices:
            state_dims.add(int(reach_matrices[0].shape[0]))
            _require(all(int(item.shape[0]) == int(reach_matrices[0].shape[0]) for item in reach_matrices), f"reachability state dimensions disagree at scale {scale}")
            reach = torch.cat(reach_matrices, dim=1)
        else:
            reach = None
        if observe_matrices:
            state_dims.add(int(observe_matrices[0].shape[1]))
            _require(all(int(item.shape[1]) == int(observe_matrices[0].shape[1]) for item in observe_matrices), f"observability state dimensions disagree at scale {scale}")
            observe = torch.cat(observe_matrices, dim=0)
        else:
            observe = None
        _require(len(state_dims) <= 1 and state_dims, f"operator registry has no complete state dimension at scale {scale}")
        state_dim = next(iter(state_dims))
        if reach is None:
            reach = torch.zeros((state_dim, 0), dtype=torch.complex128)
        if observe is None:
            observe = torch.zeros((0, state_dim), dtype=torch.complex128)
        reach_rank = _matrix_rank(reach)
        observe_rank = _matrix_rank(observe)
        if reach_rank and observe_rank:
            combined = torch.cat((reach, observe.conj().T), dim=1)
            intersection = max(0, reach_rank + observe_rank - _matrix_rank(combined))
        else:
            intersection = 0
        row = {
            "scale": scale,
            "state_dimension": state_dim,
            "reachability_dimension": reach_rank,
            "observability_dimension": observe_rank,
            "reachable_observable_intersection": intersection,
            "reachable_nullspace_dimension": max(0, int(reach.shape[1]) - reach_rank),
            "observable_nullspace_dimension": max(0, state_dim - observe_rank),
            "intersection_nullspace_dimension": max(0, state_dim - intersection),
            "source_dimension": int(reach.shape[1]),
            "readout_dimension": int(observe.shape[0]),
            "operator_ids": tuple(str(op["port_id"]) for op in by_scale[scale]),
            "batch_count": batch_limit,
        }
        result.append(MappingProxyType(row))
    return tuple(result)


def _normalise_codeword_registry(raw: Any, *, words: tuple[Any, ...], hashes: tuple[str, ...], name: str) -> tuple[tuple[Any, ...], ...]:
    _require(raw is not None, f"{name} registry is required")
    _reject_labels(raw, path=name)
    if isinstance(raw, Mapping):
        if "codewords" in raw or "values" in raw:
            raw = raw.get("codewords", raw.get("values"))
        else:
            rows: list[Any] = []
            for index, word_hash in enumerate(hashes):
                value = raw.get(word_hash, raw.get(index, raw.get(str(index), None)))
                _require(value is not None, f"{name} registry is incomplete for sector {index}")
                rows.append(value)
            per_sector = tuple(
                tuple(_freeze(item) for item in row)
                if isinstance(row, (tuple, list))
                else (_freeze(row),)
                for row in rows
            )
            for sector_index, row in enumerate(per_sector):
                _require(row, f"{name} registry has an empty sector {sector_index}")
            return per_sector
    _require(isinstance(raw, (tuple, list)) and raw, f"{name} registry is incomplete")
    shared = tuple(_freeze(item) for item in raw)
    per_sector = tuple(shared for _ in words)
    for sector_index, row in enumerate(per_sector):
        _require(row, f"{name} registry has an empty sector {sector_index}")
        for codeword in row:
            _require(_flatten_numbers(codeword, name=f"{name}[{sector_index}]") or False, f"{name} codeword is empty")
    return per_sector


def _codeword_dimension(value: Any, *, name: str) -> int:
    return len(_flatten_numbers(value, name=name))


def _normalise_scattering_receipts(receipts: Any, *, ports: tuple[Mapping[str, Any], ...], mode: str) -> tuple[Mapping[str, Any], ...]:
    if receipts is None:
        return ()
    _require(isinstance(receipts, (tuple, list)) and receipts, "scattering receipt registry is incomplete")
    port_ids = {str(row["port_id"]) for row in ports}
    rows: list[Mapping[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for receipt in receipts:
        if isinstance(receipt, QiScatteringReceipt):
            try:
                validate_scattering_receipt(receipt)
            except Exception as exc:
                raise IntrinsicCapacityError("scattering receipt public validation failed") from exc
        payload = _source_payload(receipt, name="scattering receipt")
        _require(str(_attr(receipt, "status", payload.get("status", "ACCEPTED"))) == "ACCEPTED", "rejected scattering receipt cannot support capacity")
        port_id = str(_attr(receipt, "port_id", payload.get("port_id", "")))
        step = _int("scattering step", int(_attr(receipt, "step", payload.get("step", 0))), minimum=0)
        _require(port_id in port_ids, "scattering receipt references an undeclared port")
        port = next(row for row in ports if row["port_id"] == port_id)
        _require(str(_attr(receipt, "interface_id", payload.get("interface_id", port["payload"].get("interface_id", "")))) == str(port["payload"].get("interface_id", "")), "scattering receipt interface mismatch")
        _require(str(_attr(receipt, "kind", payload.get("kind", port["kind"]))) == str(port["kind"]), "scattering receipt kind mismatch")
        _require(_attr(receipt, "source_scale", payload.get("source_scale", port["source_scale"])) == port["source_scale"], "scattering receipt source scale mismatch")
        _require(_attr(receipt, "target_scale", payload.get("target_scale", port["target_scale"])) == port["target_scale"], "scattering receipt target scale mismatch")
        _require(int(_attr(receipt, "orientation", payload.get("orientation", port["orientation"]))) == int(port["orientation"]), "scattering receipt orientation mismatch")
        _require((port_id, step) not in seen, "scattering receipt registry has duplicate rows")
        seen.add((port_id, step))
        _require(str(_attr(receipt, "scale_geometry_mode", payload.get("scale_geometry_mode", mode))) == mode, "scattering mode mismatch")
        for channel in ("W_incident", "W_reflected", "W_transmitted", "W_absorbed"):
            if hasattr(receipt, channel):
                _interval(getattr(receipt, channel), name=channel)
            elif channel in payload:
                _interval(payload[channel], name=channel)
            else:
                raise IntrinsicCapacityError(f"scattering receipt lacks {channel}")
        rows.append(MappingProxyType({"port_id": port_id, "step": step, "receipt_id": str(_attr(receipt, "receipt_id", payload.get("receipt_id", ""))), "self_sha256": str(_attr(receipt, "self_sha256", payload.get("self_sha256", ""))), "raw_work_sha256": str(_attr(receipt, "raw_work_sha256", payload.get("raw_work_sha256", "")))}))
    _require({str(row["port_id"]) for row in rows} == port_ids, "scattering receipt registry does not cover every port")
    return tuple(sorted(rows, key=lambda row: (row["port_id"], row["step"])))


def _validate_proof_registry(raw: Any, generated: tuple[Mapping[str, Any], ...], *, scales: int, batch_limit: int) -> tuple[Mapping[str, Any], ...]:
    expected_keys = {(int(row["scale"]), int(row["batch"])) for row in generated}
    if raw is None:
        return generated
    if isinstance(raw, Mapping):
        source = list(raw.values())
    else:
        _require(isinstance(raw, (tuple, list)), "proof-search registry must be a sequence or mapping")
        source = list(raw)
    rows: dict[tuple[int, int], Mapping[str, Any]] = {}
    for item in source:
        _reject_labels(item, path="proof_registry")
        _require(isinstance(item, Mapping), "proof-search row must be a mapping")
        _require({
            "schema",
            "scale",
            "batch",
            "status",
            "reachability_lower",
            "observability_lower",
            "intersection_lower",
            "reachable_nullspace_upper",
            "observable_nullspace_upper",
            "collision_pairs_upper",
            "bound_method",
            "operator_ids",
        } <= set(item), "proof-search row is incomplete")
        _require(str(item["schema"]) == INTRINSIC_CAPACITY_PROOF_SCHEMA, "proof-search row schema mismatch")
        key = (
            _int("proof scale", int(item.get("scale", -1)), minimum=0),
            _int("proof batch", int(item.get("batch", -1)), minimum=0),
        )
        _require(key not in rows, "proof-search registry has duplicate scale/batch rows")
        rows[key] = item
    _require(set(rows) == expected_keys, "proof-search registry is incomplete or has extra rows")
    out: list[Mapping[str, Any]] = []
    for generated_row in generated:
        key = (int(generated_row["scale"]), int(generated_row["batch"]))
        supplied = rows[key]
        for field in (
            "reachability_lower",
            "observability_lower",
            "intersection_lower",
            "reachable_nullspace_upper",
            "observable_nullspace_upper",
            "collision_pairs_upper",
        ):
            if field in supplied:
                lo, hi, _ = _interval(supplied[field], name=f"proof[{key}].{field}")
                value = float(generated_row[field])
                if field.endswith("_upper"):
                    _require(value <= hi, f"proof bound disagrees at {key} field {field}")
                else:
                    _require(lo <= value, f"proof lower bound disagrees at {key} field {field}")
        _require(str(supplied.get("status", "PROVEN")) == "PROVEN", f"proof row {key} is not proven")
        out.append(MappingProxyType(dict(generated_row) | {"proof_source": _plain(supplied)}))
    return tuple(out)


def _normalise_proof_rows(operator_rows: tuple[Mapping[str, Any], ...], *, batch_limit: int, candidate_count: int) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    collision_upper = candidate_count * max(0, candidate_count - 1) // 2
    for op in operator_rows:
        for batch in range(batch_limit):
            rows.append(MappingProxyType({
                "schema": INTRINSIC_CAPACITY_PROOF_SCHEMA,
                "scale": int(op["scale"]),
                "batch": batch,
                "status": "PROVEN",
                "reachability_lower": int(op["reachability_dimension"]),
                "observability_lower": int(op["observability_dimension"]),
                "intersection_lower": int(op["reachable_observable_intersection"]),
                "reachable_nullspace_upper": int(op["reachable_nullspace_dimension"]),
                "observable_nullspace_upper": int(op["observable_nullspace_dimension"]),
                "collision_pairs_upper": collision_upper,
                "bound_method": "exact-finite-matrix-rank-and-conservative-pair-bound.v1",
                "operator_ids": tuple(op["operator_ids"]),
            }))
    return tuple(rows)


@dataclass(frozen=True)
class QiIntrinsicCapacityCandidate:
    """One complete Cartesian candidate, including an exclusion reason."""

    candidate_id: str
    sector_index: int
    sector_sha256: str
    scale: int
    batch: int
    phase_index: int
    amplitude_index: int
    phase_dimension: int
    amplitude_dimension: int
    reachability_dimension: int
    observability_dimension: int
    intersection_dimension: int
    reachable_nullspace: bool
    observable_nullspace: bool
    collision: bool
    admissible: bool
    exclusion_reason: str | None = None
    phase_codeword_sha256: str = ""
    amplitude_codeword_sha256: str = ""
    self_sha256: str = ""

    def __post_init__(self) -> None:
        _text("candidate id", self.candidate_id)
        for name in ("sector_sha256", "phase_codeword_sha256", "amplitude_codeword_sha256"):
            _require(_is_sha256(getattr(self, name)), f"candidate {name} is not a hash")
        for name in ("sector_index", "scale", "batch", "phase_index", "amplitude_index", "phase_dimension", "amplitude_dimension", "reachability_dimension", "observability_dimension", "intersection_dimension"):
            _int(f"candidate {name}", getattr(self, name), minimum=0)
        for name in ("reachable_nullspace", "observable_nullspace", "collision", "admissible"):
            _require(isinstance(getattr(self, name), bool), f"candidate {name} must be boolean")
        reasons = {None, "dark-reachability", "dark-observability", "reachable-nullspace", "observable-nullspace", "collision"}
        _require(self.exclusion_reason in reasons, "candidate exclusion reason is invalid")
        _require(self.admissible == (self.exclusion_reason is None), "candidate admissibility/reason mismatch")
        payload = self.payload()
        expected = _hash(payload, INTRINSIC_CAPACITY_CANDIDATE_DOMAIN)
        if self.self_sha256:
            _require(self.self_sha256 == expected, "candidate identity mismatch")
        else:
            object.__setattr__(self, "self_sha256", expected)

    def payload(self) -> dict[str, Any]:
        return {
            "schema": INTRINSIC_CAPACITY_CANDIDATE_SCHEMA,
            "candidate_id": self.candidate_id,
            "sector_index": self.sector_index,
            "sector_sha256": self.sector_sha256,
            "scale": self.scale,
            "batch": self.batch,
            "phase_index": self.phase_index,
            "amplitude_index": self.amplitude_index,
            "phase_dimension": self.phase_dimension,
            "amplitude_dimension": self.amplitude_dimension,
            "reachability_dimension": self.reachability_dimension,
            "observability_dimension": self.observability_dimension,
            "intersection_dimension": self.intersection_dimension,
            "reachable_nullspace": self.reachable_nullspace,
            "observable_nullspace": self.observable_nullspace,
            "collision": self.collision,
            "admissible": self.admissible,
            "exclusion_reason": self.exclusion_reason,
            "phase_codeword_sha256": self.phase_codeword_sha256,
            "amplitude_codeword_sha256": self.amplitude_codeword_sha256,
        }


@dataclass(frozen=True)
class QiIntrinsicCapacityProfile:
    """Immutable W6A profile and complete finite proof-search registry."""

    selected_mode: str
    geometry_identity_sha256: str
    topology_codebook_identity_sha256: str
    port_set_identity_sha256: str
    state_layout_identity_sha256: str
    enumeration_identity_sha256: str
    scale_shapes: tuple[tuple[int, int], ...]
    active_site_counts: tuple[int, ...]
    packed_mode_count: int
    batch_limit: int
    sector_dimensions: Mapping[str, int]
    topology_codewords: tuple[Any, ...]
    topology_witness_hashes: tuple[str, ...]
    phase_codewords_by_sector: tuple[tuple[Any, ...], ...]
    amplitude_codewords_by_sector: tuple[tuple[Any, ...], ...]
    phase_dimensions_by_sector: tuple[tuple[int, ...], ...]
    amplitude_dimensions_by_sector: tuple[tuple[int, ...], ...]
    port_registry: tuple[Mapping[str, Any], ...]
    operator_registry: tuple[Mapping[str, Any], ...]
    proof_search_registry: tuple[Mapping[str, Any], ...]
    geometry_surface: Mapping[str, Any]
    topology_surface: Mapping[str, Any]
    state_layout: Mapping[str, Any]
    enumeration: Mapping[str, Any]
    scattering_receipts: tuple[Mapping[str, Any], ...] = ()
    profile_sha256: str = ""

    def __post_init__(self) -> None:
        _require(self.selected_mode, "capacity selected mode is empty")
        for name in ("geometry_identity_sha256", "topology_codebook_identity_sha256", "port_set_identity_sha256", "state_layout_identity_sha256", "enumeration_identity_sha256"):
            _require(_is_sha256(getattr(self, name)), f"capacity {name} is not a hash")
        shapes = tuple(tuple(int(v) for v in shape) for shape in self.scale_shapes)
        _require(shapes and all(len(shape) == 2 and shape[0] > 0 and shape[1] > 0 for shape in shapes), "capacity scale shapes are invalid")
        object.__setattr__(self, "scale_shapes", shapes)
        counts = tuple(_int("capacity active count", int(v), minimum=1) for v in self.active_site_counts)
        _require(tuple(ny * nx for ny, nx in shapes) == counts, "capacity active counts disagree")
        object.__setattr__(self, "active_site_counts", counts)
        object.__setattr__(self, "sector_dimensions", MappingProxyType({str(k): _int(f"sector dimension {k}", int(v), minimum=0) for k, v in dict(self.sector_dimensions).items()}))
        object.__setattr__(self, "topology_codewords", tuple(_freeze(item) for item in self.topology_codewords))
        object.__setattr__(self, "topology_witness_hashes", tuple(str(item) for item in self.topology_witness_hashes))
        _require(len(self.topology_codewords) == len(self.topology_witness_hashes), "capacity topology registry is incomplete")
        for name in ("phase_codewords_by_sector", "amplitude_codewords_by_sector", "phase_dimensions_by_sector", "amplitude_dimensions_by_sector"):
            object.__setattr__(self, name, tuple(tuple(_freeze(item) for item in row) for row in getattr(self, name)))
        _require(len(self.phase_codewords_by_sector) == len(self.topology_codewords) and len(self.amplitude_codewords_by_sector) == len(self.topology_codewords), "capacity codeword registry is incomplete")
        _require(len(self.phase_dimensions_by_sector) == len(self.topology_codewords) and len(self.amplitude_dimensions_by_sector) == len(self.topology_codewords), "capacity dimension registry is incomplete")
        _require(all(len(self.phase_dimensions_by_sector[index]) == len(self.phase_codewords_by_sector[index]) and len(self.amplitude_dimensions_by_sector[index]) == len(self.amplitude_codewords_by_sector[index]) for index in range(len(self.topology_codewords))), "capacity codeword dimensions are incomplete")
        _require(isinstance(self.enumeration, Mapping), "capacity enumeration metadata is incomplete")
        expected_candidate_count = sum(len(self.phase_codewords_by_sector[index]) * len(self.amplitude_codewords_by_sector[index]) for index in range(len(self.topology_codewords))) * len(shapes) * int(self.batch_limit)
        _require(int(self.enumeration.get("candidate_count", -1)) == expected_candidate_count, "capacity enumeration candidate count mismatch")
        object.__setattr__(self, "port_registry", tuple(_freeze(item) for item in self.port_registry))
        object.__setattr__(self, "operator_registry", tuple(_freeze(item) for item in self.operator_registry))
        _require(
            {(int(row.get("scale", -1)), int(row.get("batch", -1))) for row in self.proof_search_registry}
            == {(scale, batch) for scale in range(len(self.scale_shapes)) for batch in range(self.batch_limit)},
            "capacity proof-search registry is incomplete",
        )
        object.__setattr__(self, "proof_search_registry", tuple(_freeze(item) for item in self.proof_search_registry))
        object.__setattr__(self, "geometry_surface", _freeze(self.geometry_surface))
        object.__setattr__(self, "topology_surface", _freeze(self.topology_surface))
        object.__setattr__(self, "state_layout", _freeze(self.state_layout))
        object.__setattr__(self, "enumeration", _freeze(self.enumeration))
        object.__setattr__(self, "scattering_receipts", tuple(_freeze(item) for item in self.scattering_receipts))
        expected = _hash(self.payload(), INTRINSIC_CAPACITY_PROFILE_DOMAIN)
        if self.profile_sha256:
            _require(self.profile_sha256 == expected, "capacity profile identity mismatch")
        else:
            object.__setattr__(self, "profile_sha256", expected)

    @property
    def schema(self) -> str:
        return INTRINSIC_CAPACITY_PROFILE_SCHEMA

    @property
    def geometry_sha256(self) -> str:
        return self.geometry_identity_sha256

    @property
    def topology_codebook_sha256(self) -> str:
        return self.topology_codebook_identity_sha256

    @property
    def port_set_sha256(self) -> str:
        return self.port_set_identity_sha256

    @property
    def state_layout_sha256(self) -> str:
        return self.state_layout_identity_sha256

    @property
    def enumeration_sha256(self) -> str:
        return self.enumeration_identity_sha256

    @property
    def sector_count(self) -> int:
        return len(self.topology_codewords)

    def payload(self) -> dict[str, Any]:
        return {
            "schema": INTRINSIC_CAPACITY_PROFILE_SCHEMA,
            "selected_mode": self.selected_mode,
            "geometry_identity_sha256": self.geometry_identity_sha256,
            "topology_codebook_identity_sha256": self.topology_codebook_identity_sha256,
            "port_set_identity_sha256": self.port_set_identity_sha256,
            "state_layout_identity_sha256": self.state_layout_identity_sha256,
            "enumeration_identity_sha256": self.enumeration_identity_sha256,
            "scale_shapes": [list(shape) for shape in self.scale_shapes],
            "active_site_counts": list(self.active_site_counts),
            "packed_mode_count": self.packed_mode_count,
            "batch_limit": self.batch_limit,
            "sector_dimensions": dict(self.sector_dimensions),
            "topology_codewords": _plain(self.topology_codewords),
            "topology_witness_hashes": list(self.topology_witness_hashes),
            "phase_codewords_by_sector": _plain(self.phase_codewords_by_sector),
            "amplitude_codewords_by_sector": _plain(self.amplitude_codewords_by_sector),
            "phase_dimensions_by_sector": _plain(self.phase_dimensions_by_sector),
            "amplitude_dimensions_by_sector": _plain(self.amplitude_dimensions_by_sector),
            "port_registry": _plain(self.port_registry),
            "operator_registry": _plain(self.operator_registry),
            "proof_search_registry": _plain(self.proof_search_registry),
            "geometry_surface": _plain(self.geometry_surface),
            "topology_surface": _plain(self.topology_surface),
            "state_layout": _plain(self.state_layout),
            "enumeration": _plain(self.enumeration),
            "scattering_receipts": _plain(self.scattering_receipts),
        }

    def enumerate(self) -> "QiIntrinsicCapacityReceipt":
        return enumerate_intrinsic_capacity(self)

    def materialize(self) -> "QiIntrinsicCapacityReceipt":
        return self.enumerate()
    @classmethod
    def build(cls, **kwargs: Any) -> "QiIntrinsicCapacityProfile":
        return build_intrinsic_capacity_profile(**kwargs)

    @classmethod
    def from_current(cls, **kwargs: Any) -> "QiIntrinsicCapacityProfile":
        return build_intrinsic_capacity_profile(**kwargs)

    @property
    def topological_sector_dimensions(self) -> Mapping[str, int]:
        return self.sector_dimensions

    @property
    def phase_codeword_dimensions(self) -> tuple[tuple[int, ...], ...]:
        return self.phase_dimensions_by_sector

    @property
    def amplitude_codeword_dimensions(self) -> tuple[tuple[int, ...], ...]:
        return self.amplitude_dimensions_by_sector


@dataclass(frozen=True)
class QiIntrinsicCapacityReceipt:
    """Content-addressed result of complete W6A candidate enumeration."""

    profile_sha256: str
    geometry_identity_sha256: str
    topology_codebook_identity_sha256: str
    port_set_identity_sha256: str
    state_layout_identity_sha256: str
    enumeration_identity_sha256: str
    candidates: tuple[QiIntrinsicCapacityCandidate, ...]
    admissible_candidate_ids: tuple[str, ...]
    excluded_candidate_ids: tuple[str, ...]
    capacity_levels: Mapping[str, int]
    capacity_lower_bounds: Mapping[str, int]
    per_scale_batch: tuple[Mapping[str, Any], ...]
    collision_counts: Mapping[str, int]
    nullspace_counts: Mapping[str, int]
    proof_search_registry: tuple[Mapping[str, Any], ...]
    status: str = "MATERIALIZED"
    receipt_id: str = ""
    self_sha256: str = ""

    def __post_init__(self) -> None:
        for name in ("profile_sha256", "geometry_identity_sha256", "topology_codebook_identity_sha256", "port_set_identity_sha256", "state_layout_identity_sha256", "enumeration_identity_sha256"):
            _require(_is_sha256(getattr(self, name)), f"receipt {name} is not a hash")
        candidates = tuple(self.candidates)
        _require(all(isinstance(item, QiIntrinsicCapacityCandidate) for item in candidates), "receipt candidate registry is not immutable")
        ids = tuple(item.candidate_id for item in candidates)
        _require(len(ids) == len(set(ids)) and ids == tuple(sorted(ids)), "receipt candidate order is not canonical")
        object.__setattr__(self, "candidates", candidates)
        admissible = tuple(self.admissible_candidate_ids)
        excluded = tuple(self.excluded_candidate_ids)
        _require(set(admissible).isdisjoint(excluded) and set(admissible) | set(excluded) == set(ids), "receipt candidate partitions are incomplete")
        _require(admissible == tuple(item.candidate_id for item in candidates if item.admissible), "receipt admissible set disagrees with candidates")
        _require(excluded == tuple(item.candidate_id for item in candidates if not item.admissible), "receipt exclusion set disagrees with candidates")
        object.__setattr__(self, "admissible_candidate_ids", admissible)
        object.__setattr__(self, "excluded_candidate_ids", excluded)
        levels = {str(k): _int(f"capacity level {k}", int(v), minimum=0) for k, v in dict(self.capacity_levels).items()}
        lower = {str(k): _int(f"capacity lower bound {k}", int(v), minimum=0) for k, v in dict(self.capacity_lower_bounds).items()}
        _require(set(lower) <= set(levels), "receipt lower bound has an unknown capacity level")
        _require(all(lower[key] <= levels[key] for key in lower), "receipt lower bound exceeds capacity")
        object.__setattr__(self, "capacity_levels", MappingProxyType(levels))
        object.__setattr__(self, "capacity_lower_bounds", MappingProxyType(lower))
        object.__setattr__(self, "per_scale_batch", tuple(_freeze(item) for item in self.per_scale_batch))
        object.__setattr__(self, "collision_counts", MappingProxyType({str(k): _int(f"collision count {k}", int(v), minimum=0) for k, v in dict(self.collision_counts).items()}))
        object.__setattr__(self, "nullspace_counts", MappingProxyType({str(k): _int(f"nullspace count {k}", int(v), minimum=0) for k, v in dict(self.nullspace_counts).items()}))
        object.__setattr__(self, "proof_search_registry", tuple(_freeze(item) for item in self.proof_search_registry))
        _require(self.status == "MATERIALIZED", "intrinsic capacity receipt cannot silently degrade")
        expected_id = _hash({"profile_sha256": self.profile_sha256, "enumeration_identity_sha256": self.enumeration_identity_sha256, "candidate_ids": list(ids)}, "cassi.qi-flow-intrinsic-capacity-receipt-id.v1")
        if self.receipt_id:
            _require(self.receipt_id == expected_id, "receipt id mismatch")
        else:
            object.__setattr__(self, "receipt_id", expected_id)
        expected = _hash(self.payload(), INTRINSIC_CAPACITY_RECEIPT_DOMAIN)
        if self.self_sha256:
            _require(self.self_sha256 == expected, "receipt identity mismatch")
        else:
            object.__setattr__(self, "self_sha256", expected)

    @property
    def schema(self) -> str:
        return INTRINSIC_CAPACITY_RECEIPT_SCHEMA

    @property
    def admissible_set(self) -> tuple[str, ...]:
        return self.admissible_candidate_ids

    @property
    def admissible_candidates(self) -> tuple[QiIntrinsicCapacityCandidate, ...]:
        accepted = set(self.admissible_candidate_ids)
        return tuple(item for item in self.candidates if item.candidate_id in accepted)

    @property
    def geometric_capacity(self) -> int:
        return int(self.capacity_levels.get("geometric", 0))

    @property
    def reachable_capacity(self) -> int:
        return int(self.capacity_levels.get("reachable", 0))

    @property
    def observable_capacity(self) -> int:
        return int(self.capacity_levels.get("observable", 0))

    @property
    def usable_capacity(self) -> int:
        return int(self.capacity_levels.get("admissible", 0))
    @property
    def collision_count(self) -> int:
        return int(self.collision_counts.get("pairs", 0))

    @property
    def nullspace_count(self) -> int:
        return int(self.nullspace_counts.get("reachable_candidate_rows", 0) + self.nullspace_counts.get("observable_candidate_rows", 0))

    @property
    def capacity_receipt_sha256(self) -> str:
        return self.self_sha256


    def payload(self) -> dict[str, Any]:
        return {
            "schema": INTRINSIC_CAPACITY_RECEIPT_SCHEMA,
            "receipt_id": self.receipt_id,
            "profile_sha256": self.profile_sha256,
            "geometry_identity_sha256": self.geometry_identity_sha256,
            "topology_codebook_identity_sha256": self.topology_codebook_identity_sha256,
            "port_set_identity_sha256": self.port_set_identity_sha256,
            "state_layout_identity_sha256": self.state_layout_identity_sha256,
            "enumeration_identity_sha256": self.enumeration_identity_sha256,
            "candidates": [item.payload() for item in self.candidates],
            "admissible_candidate_ids": list(self.admissible_candidate_ids),
            "excluded_candidate_ids": list(self.excluded_candidate_ids),
            "capacity_levels": dict(self.capacity_levels),
            "capacity_lower_bounds": dict(self.capacity_lower_bounds),
            "per_scale_batch": _plain(self.per_scale_batch),
            "collision_counts": dict(self.collision_counts),
            "nullspace_counts": dict(self.nullspace_counts),
            "proof_search_registry": _plain(self.proof_search_registry),
            "status": self.status,
        }

    def to_dict(self) -> Mapping[str, Any]:
        return MappingProxyType(self.payload() | {"self_sha256": self.self_sha256})


def build_intrinsic_capacity_profile(
    *,
    geometry: Any | None = None,
    topology_codebook: Any | None = None,
    ports: Any | None = None,
    state_layout: Any | None = None,
    phase_codewords: Any | None = None,
    amplitude_codewords: Any | None = None,
    scattering_operators: Any | None = None,
    selected_geometry: Any | None = None,
    remap: Any = None,
    scattering_receipts: Any = None,
    proof_search_registry: Any = None,
    geometry_profile: Any | None = None,
    topology: Any | None = None,
    port_set: Any | None = None,
    phase_codebook: Any | None = None,
    amplitude_codebook: Any | None = None,
    port_operators: Any | None = None,
    operators: Any | None = None,
) -> QiIntrinsicCapacityProfile:
    """Build a validated immutable profile from explicit public dependencies."""
    geometry = geometry if geometry is not None else geometry_profile
    topology_codebook = topology_codebook if topology_codebook is not None else topology
    ports = ports if ports is not None else port_set
    phase_codewords = phase_codewords if phase_codewords is not None else phase_codebook
    amplitude_codewords = amplitude_codewords if amplitude_codewords is not None else amplitude_codebook
    scattering_operators = scattering_operators if scattering_operators is not None else (port_operators if port_operators is not None else operators)
    _require(geometry is not None, "selected W6T geometry is required")
    _require(topology_codebook is not None, "current W4R topology codebook is required")
    _require(ports is not None, "complete port set is required")
    _require(scattering_operators is not None, "fixed port/scattering operators are required")
    geometry_surface, candidate_payload, mode, shapes, counts, mode_count, geometry_hash, _ = _normalise_geometry(geometry, selected_geometry)
    codebook_surface, words, witnesses, dimensions, codebook_hash, remap_identity = _normalise_codebook(topology_codebook, resolution=shapes[-1], remap=remap)
    layout, layout_hash, batch_limit = _normalise_state_layout(state_layout, shapes=shapes, mode_count=mode_count)
    port_rows, port_hash = _normalise_ports(ports, mode=mode, scales=len(shapes), geometry_hash=geometry_hash)
    operator_rows = _normalise_operators(scattering_operators, ports=port_rows, scales=len(shapes))
    scale_operator_rows = _aggregate_operator_rows(operator_rows, port_rows, scales=len(shapes), batch_limit=batch_limit)
    phase_rows = _normalise_codeword_registry(phase_codewords, words=words, hashes=tuple(_codeword_hash(word) for word in words), name="phase")
    amplitude_rows = _normalise_codeword_registry(amplitude_codewords, words=words, hashes=tuple(_codeword_hash(word) for word in words), name="amplitude")
    phase_dimensions = tuple(tuple(_codeword_dimension(item, name=f"phase[{s}]") for item in row) for s, row in enumerate(phase_rows))
    amplitude_dimensions = tuple(tuple(_codeword_dimension(item, name=f"amplitude[{s}]") for item in row) for s, row in enumerate(amplitude_rows))
    _require(all(all(value > 0 for value in row) for row in phase_dimensions + amplitude_dimensions), "phase/amplitude codeword dimensions must be positive")
    scattering_rows = _normalise_scattering_receipts(scattering_receipts, ports=port_rows, mode=mode)
    candidate_count_per_scale_batch = sum(len(phase_rows[index]) * len(amplitude_rows[index]) for index in range(len(words)))
    generated_proof = _normalise_proof_rows(scale_operator_rows, batch_limit=batch_limit, candidate_count=candidate_count_per_scale_batch)
    proof_rows = _validate_proof_registry(proof_search_registry, generated_proof, scales=len(shapes), batch_limit=batch_limit)
    enumeration = {
        "schema": ENUMERATION_DOMAIN,
        "order": "scale,batch,sector,phase,amplitude.v1",
        "scales": list(range(len(shapes))),
        "batches": list(range(batch_limit)),
        "sector_indices": list(range(len(words))),
        "phase_counts": [len(row) for row in phase_rows],
        "amplitude_counts": [len(row) for row in amplitude_rows],
        "remap_identity": remap_identity,
        "sector_codeword_sha256": [_codeword_hash(word) for word in words],
        "phase_codeword_sha256_by_sector": [[_hash(item, "cassi.qi-flow-phase-codeword.v1") for item in row] for row in phase_rows],
        "amplitude_codeword_sha256_by_sector": [[_hash(item, "cassi.qi-flow-amplitude-codeword.v1") for item in row] for row in amplitude_rows],
        "operator_registry_sha256": _hash(operator_rows, "cassi.qi-flow-intrinsic-operator-registry.v1"),
        "candidate_count_per_scale_batch": candidate_count_per_scale_batch,
        "candidate_count": sum(len(phase_rows[s]) * len(amplitude_rows[s]) for s in range(len(words))) * len(shapes) * batch_limit,
    }
    enumeration_hash = _hash(enumeration, ENUMERATION_DOMAIN)
    return QiIntrinsicCapacityProfile(
        selected_mode=mode,
        geometry_identity_sha256=geometry_hash,
        topology_codebook_identity_sha256=codebook_hash,
        port_set_identity_sha256=port_hash,
        state_layout_identity_sha256=layout_hash,
        enumeration_identity_sha256=enumeration_hash,
        scale_shapes=shapes,
        active_site_counts=counts,
        packed_mode_count=mode_count,
        batch_limit=batch_limit,
        sector_dimensions=dimensions,
        topology_codewords=words,
        topology_witness_hashes=witnesses,
        phase_codewords_by_sector=phase_rows,
        amplitude_codewords_by_sector=amplitude_rows,
        phase_dimensions_by_sector=phase_dimensions,
        amplitude_dimensions_by_sector=amplitude_dimensions,
        port_registry=port_rows,
        operator_registry=operator_rows,
        proof_search_registry=proof_rows,
        geometry_surface=geometry_surface,
        topology_surface=codebook_surface,
        state_layout=layout,
        enumeration=enumeration,
        scattering_receipts=scattering_rows,
    )


def _candidate_numeric_vector(sector: Any, phase: Any, amplitude: Any, *, target_dimension: int, mode_count: int) -> tuple[complex, ...]:
    sector_values = tuple(complex(value) for value in _flatten_numbers(sector, name="candidate sector"))
    phase_values = tuple(complex(value) for value in _flatten_numbers(phase, name="candidate phase"))
    amplitude_values = tuple(complex(value) for value in _flatten_numbers(amplitude, name="candidate amplitude"))
    _require(phase_values and amplitude_values, "candidate phase/amplitude codewords cannot be empty")
    def _phase_unit(value: complex) -> complex:
        real = math.cos(value.real)
        imag = math.sin(value.real)
        if abs(real) <= 1.0e-12:
            real = 0.0
        if abs(imag) <= 1.0e-12:
            imag = 0.0
        return complex(real, imag)
    if len(phase_values) == len(amplitude_values):
        complex_values = tuple(amplitude_values[index] * _phase_unit(phase_values[index]) for index in range(len(phase_values)))
    elif len(phase_values) == 1:
        complex_values = tuple(amplitude_values[index] * _phase_unit(phase_values[0]) for index in range(len(amplitude_values)))
    elif len(amplitude_values) == 1:
        complex_values = tuple(amplitude_values[0] * _phase_unit(phase_values[index]) for index in range(len(phase_values)))
    else:
        raise IntrinsicCapacityError("phase/amplitude codeword dimensions cannot be paired")
    # The state-layout embedding is explicit: topology values precede the
    # complex phase/amplitude values and inactive coordinates are zero.
    features = sector_values + complex_values
    raw_features = phase_values + amplitude_values
    if target_dimension == len(features):
        return features
    if target_dimension == len(raw_features):
        return raw_features
    if target_dimension == 9 * mode_count and len(features) <= target_dimension:
        return features + (0j,) * (target_dimension - len(features))
    if target_dimension >= len(features):
        return features + (0j,) * (target_dimension - len(features))
    raise IntrinsicCapacityError(f"candidate state embedding dimension {len(features)} does not match operator input dimension {target_dimension}")


def _signature(value: torch.Tensor, *, kind: str) -> tuple[Any, ...]:
    if value.numel() == 0:
        return (kind, "empty")
    flat = value.detach().cpu().reshape(-1)
    return (kind,) + tuple((_f64_tag(float(complex(item.item()).real)), _f64_tag(float(complex(item.item()).imag))) for item in flat)


def _project_signature(matrix: torch.Tensor, vector: tuple[complex, ...], *, candidate_key: str, kind: str) -> tuple[Any, ...]:
    if _matrix_rank(matrix) == 0:
        return (f"{kind}-nullspace",)
    _require(len(vector) == int(matrix.shape[1]), f"{kind} operator input dimension is incompatible with the explicit state embedding")
    source = torch.tensor(vector, dtype=torch.complex128).reshape(-1, 1)
    projected = matrix @ source
    scale = float(torch.linalg.vector_norm(projected).item()) if projected.numel() else 0.0
    if scale <= 1.0e-12:
        return (f"{kind}-nullspace",)
    return _signature(projected, kind=kind)


def enumerate_intrinsic_capacity(profile: QiIntrinsicCapacityProfile) -> QiIntrinsicCapacityReceipt:
    """Materialize every scale/batch/sector/phase/amplitude candidate."""
    _require(isinstance(profile, QiIntrinsicCapacityProfile), "enumeration requires QiIntrinsicCapacityProfile")
    operator_rows = _aggregate_operator_rows(profile.operator_registry, profile.port_registry, scales=len(profile.scale_shapes), batch_limit=profile.batch_limit)
    proof_keys = {(int(row["scale"]), int(row["batch"])) for row in profile.proof_search_registry}
    _require(proof_keys == {(scale, batch) for scale in range(len(profile.scale_shapes)) for batch in range(profile.batch_limit)}, "profile proof-search registry is incomplete")
    raw_candidates: list[QiIntrinsicCapacityCandidate] = []
    per_rows: list[Mapping[str, Any]] = []
    collision_total = 0
    null_reach_total = 0
    null_observe_total = 0
    for scale in range(len(profile.scale_shapes)):
        op = operator_rows[scale]
        source_dim = int(op["source_dimension"])
        readout_dim = int(op["readout_dimension"])
        # The matrices are reconstructed from the immutable operator registry.
        by_scale = [row for row in profile.operator_registry if int(row["scale"]) == scale]
        reach_matrices = [_matrix(row["reachability"], name="profile reachability") for row in by_scale if "reachability" in row]
        observe_matrices = [_matrix(row["observability"], name="profile observability") for row in by_scale if "observability" in row]
        channel_matrices = [(_matrix(row["channel"], name="profile channel"), next(port for port in profile.port_registry if port["port_id"] == row["port_id"])) for row in profile.operator_registry if "channel" in row]
        for matrix, port in channel_matrices:
            if int(port["target_scale"]) == scale:
                reach_matrices.append(matrix)
            if int(port["source_scale"]) == scale:
                observe_matrices.append(matrix)
        reach = torch.cat(reach_matrices, dim=1) if reach_matrices else torch.zeros((int(op["state_dimension"]), 0), dtype=torch.complex128)
        observe = torch.cat(observe_matrices, dim=0) if observe_matrices else torch.zeros((0, int(op["state_dimension"])), dtype=torch.complex128)
        for batch in range(profile.batch_limit):
            rows_for_scale_batch: list[QiIntrinsicCapacityCandidate] = []
            for sector_index, sector in enumerate(profile.topology_codewords):
                sector_hash = _codeword_hash(sector)
                for phase_index, phase in enumerate(profile.phase_codewords_by_sector[sector_index]):
                    for amplitude_index, amplitude in enumerate(profile.amplitude_codewords_by_sector[sector_index]):
                        candidate_key = f"s{scale}:b{batch}:t{sector_index}:p{phase_index}:a{amplitude_index}"
                        candidate_id = _hash({"key": candidate_key, "profile": profile.profile_sha256}, INTRINSIC_CAPACITY_CANDIDATE_DOMAIN)
                        source_vector = _candidate_numeric_vector(sector, phase, amplitude, target_dimension=int(reach.shape[1]), mode_count=profile.packed_mode_count) if _matrix_rank(reach) else ()
                        observe_vector = _candidate_numeric_vector(sector, phase, amplitude, target_dimension=int(observe.shape[1]), mode_count=profile.packed_mode_count) if _matrix_rank(observe) else ()
                        source_signature = _project_signature(reach, source_vector, candidate_key=candidate_key, kind="reachable")
                        observe_signature = _project_signature(observe, observe_vector, candidate_key=candidate_key, kind="observable")
                        combined_signature = source_signature + observe_signature
                        rows_for_scale_batch.append((candidate_key, candidate_id, sector_hash, phase_index, amplitude_index, source_signature, observe_signature, combined_signature))
            signature_counts: dict[tuple[Any, ...], int] = {}
            for row in rows_for_scale_batch:
                signature_counts[row[7]] = signature_counts.get(row[7], 0) + 1
            collisions = sum(count * (count - 1) // 2 for count in signature_counts.values() if count > 1)
            collision_total += collisions
            for row in rows_for_scale_batch:
                candidate_key, candidate_id, sector_hash, phase_index, amplitude_index, source_signature, observe_signature, combined_signature = row
                reachable_null = source_signature[0].startswith("reachable-nullspace") or int(op["reachability_dimension"]) == 0
                observable_null = observe_signature[0].startswith("observable-nullspace") or int(op["observability_dimension"]) == 0
                collision = signature_counts[combined_signature] > 1
                reason = None
                if int(op["reachability_dimension"]) == 0:
                    reason = "dark-reachability"
                elif int(op["observability_dimension"]) == 0:
                    reason = "dark-observability"
                elif reachable_null:
                    reason = "reachable-nullspace"
                elif observable_null:
                    reason = "observable-nullspace"
                elif collision:
                    reason = "collision"
                admissible = reason is None and int(op["reachable_observable_intersection"]) > 0
                if reason is None and not admissible:
                    reason = "dark-observability"
                if reachable_null:
                    null_reach_total += 1
                if observable_null:
                    null_observe_total += 1
                raw_candidates.append(QiIntrinsicCapacityCandidate(
                    candidate_id=candidate_id,
                    sector_index=int(sector_index),
                    sector_sha256=sector_hash,
                    scale=scale,
                    batch=batch,
                    phase_index=phase_index,
                    amplitude_index=amplitude_index,
                    phase_dimension=profile.phase_dimensions_by_sector[sector_index][phase_index],
                    amplitude_dimension=profile.amplitude_dimensions_by_sector[sector_index][amplitude_index],
                    reachability_dimension=int(op["reachability_dimension"]),
                    observability_dimension=int(op["observability_dimension"]),
                    intersection_dimension=int(op["reachable_observable_intersection"]),
                    reachable_nullspace=reachable_null,
                    observable_nullspace=observable_null,
                    collision=collision,
                    admissible=admissible,
                    exclusion_reason=reason,
                    phase_codeword_sha256=_hash(profile.phase_codewords_by_sector[sector_index][phase_index], "cassi.qi-flow-phase-codeword.v1"),
                    amplitude_codeword_sha256=_hash(profile.amplitude_codewords_by_sector[sector_index][amplitude_index], "cassi.qi-flow-amplitude-codeword.v1"),
                ))
            accepted = sum(1 for item in raw_candidates if item.scale == scale and item.batch == batch and item.admissible)
            total = sum(1 for item in raw_candidates if item.scale == scale and item.batch == batch)
            per_rows.append(MappingProxyType({
                "scale": scale,
                "batch": batch,
                "candidate_count": total,
                "admissible_count": accepted,
                "reachability_dimension": int(op["reachability_dimension"]),
                "observability_dimension": int(op["observability_dimension"]),
                "reachable_observable_intersection": int(op["reachable_observable_intersection"]),
                "reachable_nullspace_dimension": int(op["reachable_nullspace_dimension"]),
                "observable_nullspace_dimension": int(op["observable_nullspace_dimension"]),
                "collision_pairs": collisions,
                "operator_ids": tuple(op["operator_ids"]),
            }))
    candidates = tuple(sorted(raw_candidates, key=lambda item: item.candidate_id))
    accepted_ids = tuple(item.candidate_id for item in candidates if item.admissible)
    excluded_ids = tuple(item.candidate_id for item in candidates if not item.admissible)
    geometric = len(candidates)
    reachable = sum(1 for item in candidates if item.reachability_dimension > 0 and not item.reachable_nullspace)
    observable = sum(1 for item in candidates if item.observability_dimension > 0 and not item.observable_nullspace)
    intersection = sum(1 for item in candidates if item.intersection_dimension > 0 and not item.reachable_nullspace and not item.observable_nullspace)
    levels = {"geometric": geometric, "reachable": reachable, "observable": observable, "reachable_observable_intersection": intersection, "admissible": len(accepted_ids)}
    by_scale_counts = [int(row["admissible_count"]) for row in per_rows]
    lower = {
        "geometric": geometric,
        "reachable": min((int(row["reachability_dimension"]) for row in per_rows), default=0),
        "observable": min((int(row["observability_dimension"]) for row in per_rows), default=0),
        "reachable_observable_intersection": min((int(row["reachable_observable_intersection"]) for row in per_rows), default=0),
        "admissible": min(by_scale_counts, default=0),
    }
    collision_counts = {"pairs": collision_total, "candidate_rows": sum(1 for item in candidates if item.collision)}
    nullspace_counts = {"reachable_candidate_rows": null_reach_total, "observable_candidate_rows": null_observe_total, "operator_reachable": sum(int(row["reachable_nullspace_dimension"]) for row in per_rows), "operator_observable": sum(int(row["observable_nullspace_dimension"]) for row in per_rows)}
    return QiIntrinsicCapacityReceipt(
        profile_sha256=profile.profile_sha256,
        geometry_identity_sha256=profile.geometry_identity_sha256,
        topology_codebook_identity_sha256=profile.topology_codebook_identity_sha256,
        port_set_identity_sha256=profile.port_set_identity_sha256,
        state_layout_identity_sha256=profile.state_layout_identity_sha256,
        enumeration_identity_sha256=profile.enumeration_identity_sha256,
        candidates=candidates,
        admissible_candidate_ids=accepted_ids,
        excluded_candidate_ids=excluded_ids,
        capacity_levels=levels,
        capacity_lower_bounds=lower,
        per_scale_batch=tuple(sorted(per_rows, key=lambda row: (int(row["scale"]), int(row["batch"])))),
        collision_counts=collision_counts,
        nullspace_counts=nullspace_counts,
        proof_search_registry=profile.proof_search_registry,
    )


def enumerate_admissible_set(profile: QiIntrinsicCapacityProfile) -> tuple[QiIntrinsicCapacityCandidate, ...]:
    """Return the complete accepted finite set, never a top-one selection."""
    return enumerate_intrinsic_capacity(profile).admissible_candidates


def validate_intrinsic_capacity_profile(profile: QiIntrinsicCapacityProfile) -> None:
    _require(isinstance(profile, QiIntrinsicCapacityProfile), "not an intrinsic capacity profile")
    _require(_hash(profile.payload(), INTRINSIC_CAPACITY_PROFILE_DOMAIN) == profile.profile_sha256, "intrinsic capacity profile hash mismatch")
    _require(len(profile.proof_search_registry) == len(profile.scale_shapes) * profile.batch_limit, "intrinsic proof-search registry is incomplete")


def validate_intrinsic_capacity_receipt(receipt: QiIntrinsicCapacityReceipt, *, profile: QiIntrinsicCapacityProfile | None = None) -> None:
    _require(isinstance(receipt, QiIntrinsicCapacityReceipt), "not an intrinsic capacity receipt")
    if profile is not None:
        validate_intrinsic_capacity_profile(profile)
        for name in ("profile_sha256", "geometry_identity_sha256", "topology_codebook_identity_sha256", "port_set_identity_sha256", "state_layout_identity_sha256", "enumeration_identity_sha256"):
            _require(getattr(receipt, name) == (profile.profile_sha256 if name == "profile_sha256" else getattr(profile, name)), f"receipt {name} disagrees with profile")
    _require(_hash(receipt.payload(), INTRINSIC_CAPACITY_RECEIPT_DOMAIN) == receipt.self_sha256, "intrinsic capacity receipt hash mismatch")


build_capacity_profile = build_intrinsic_capacity_profile
materialize_intrinsic_capacity = enumerate_intrinsic_capacity
validate_capacity_profile = validate_intrinsic_capacity_profile
validate_capacity_receipt = validate_intrinsic_capacity_receipt
build_qi_intrinsic_capacity_profile = build_intrinsic_capacity_profile
enumerate_qi_intrinsic_capacity = enumerate_intrinsic_capacity
build_qi_intrinsic_capacity_receipt = enumerate_intrinsic_capacity
validate_qi_intrinsic_capacity_profile = validate_intrinsic_capacity_profile
validate_qi_intrinsic_capacity_receipt = validate_intrinsic_capacity_receipt


__all__ = [
    "INTRINSIC_CAPACITY_PROFILE_SCHEMA",
    "INTRINSIC_CAPACITY_RECEIPT_SCHEMA",
    "INTRINSIC_CAPACITY_CANDIDATE_SCHEMA",
    "INTRINSIC_CAPACITY_PROOF_SCHEMA",
    "IntrinsicCapacityError",
    "QiCapacityError",
    "QiIntrinsicCapacityCandidate",
    "QiIntrinsicCapacityProfile",
    "QiIntrinsicCapacityReceipt",
    "build_intrinsic_capacity_profile",
    "build_capacity_profile",
    "enumerate_intrinsic_capacity",
    "materialize_intrinsic_capacity",
    "enumerate_admissible_set",
    "validate_intrinsic_capacity_profile",
    "validate_intrinsic_capacity_receipt",
    "validate_capacity_profile",
    "validate_capacity_receipt",
    "build_qi_intrinsic_capacity_profile",
    "enumerate_qi_intrinsic_capacity",
    "build_qi_intrinsic_capacity_receipt",
    "validate_qi_intrinsic_capacity_profile",
    "validate_qi_intrinsic_capacity_receipt",
]
CAPACITY_LADDER_SCHEMA = "cassi.qi-flow-capacity-ladder.v1"
CAPACITY_LADDER_DOMAIN = CAPACITY_LADDER_SCHEMA
CAPACITY_LADDER_ID_DOMAIN = "cassi.qi-flow-capacity-ladder-id.v1"
CAPACITY_LADDER_CONTROLLER_DOMAIN = "cassi.qi-flow-controller-grammar.v1"
CAPACITY_LADDER_STATE_DOMAIN = "cassi.qi-flow-capacity-state.v1"
CAPACITY_LADDER_LEVELS = ("geometric", "reachable", "observable", "usable", "retained", "reusable")


class CapacityLadderError(IntrinsicCapacityError):
    """A canonical W6A trajectory ladder cannot be admitted."""


QiCapacityLadderError = CapacityLadderError


def _ladder_require_sha(value: Any, *, name: str) -> str:
    _require(_is_sha256(value), f"{name} must be a lowercase SHA-256 digest")
    return str(value)
_LADDER_WORK_KEYS = frozenset({"incident", "admitted", "reflected", "absorbed", "port_reaction", "damping_dissipation", "residual", "conversion", "closure_residual"})
_LADDER_NONNEGATIVE_WORK_KEYS = frozenset({"incident", "admitted", "reflected", "absorbed", "port_reaction", "damping_dissipation"})
_LADDER_INTERVAL_UNITS = frozenset({"tick", "second", "microsecond", "item", "joule", "normalized", "radian"})
_LADDER_WORK_UNITS = frozenset({"joule", "normalized"})

_LADDER_SUBHASH_NAMES = frozenset({"state_contract_sha256", "boundary_action_sha256", "world_protocol_sha256", "session_storage_sha256", "provider_api_sha256", "backend_capacity_sha256", "security_evidence_sha256"})

def _ladder_identifier(value: Any, *, name: str) -> str:
    text = _text(name, value)
    _require(len(text) <= 128 and (text[0].isdigit() or ("a" <= text[0] <= "z")) and all(ch.isdigit() or ("a" <= ch <= "z") or ch in "._:-" for ch in text), f"{name} is not an identifier-v1")
    return text


def _ladder_finite(value: Any, *, name: str) -> float:
    try:
        from cassi_qi_bootstrap import finite_float

        result = finite_float(value, name=name)
    except Exception as exc:
        raise CapacityLadderError(f"{name} must be a finite canonical scalar") from exc
    _require(math.isfinite(result), f"{name} must be finite")
    return float(result)


def _ladder_interval(
    value: Any,
    *,
    name: str,
    unit: str,
    sign: str = "nonnegative",
    require_nonnegative: bool = True,
) -> tuple[Mapping[str, Any], float, float]:
    if hasattr(value, "lower") and hasattr(value, "upper"):
        lower, upper = getattr(value, "lower"), getattr(value, "upper")
        resolved = getattr(value, "resolved", True)
        raw_unit = getattr(value, "unit", unit)
        uncertainty = getattr(value, "uncertainty_radius", getattr(value, "uncertainty", 0.0))
    elif isinstance(value, Mapping):
        if "value" in value and "lower" not in value and "upper" not in value:
            lower = upper = value["value"]
        else:
            _require("lower" in value and "upper" in value, f"{name} interval is incomplete")
            lower, upper = value["lower"], value["upper"]
        resolved = value.get("resolved", True)
        raw_unit = value.get("unit", unit)
        uncertainty = value.get("uncertainty_radius", value.get("uncertainty", 0.0))
    elif isinstance(value, (tuple, list)) and len(value) == 2:
        lower, upper, resolved, raw_unit, uncertainty = value[0], value[1], True, unit, 0.0
    else:
        lower = upper = value
        resolved, raw_unit, uncertainty = True, unit, 0.0
    _require(isinstance(resolved, bool) and resolved, f"{name} interval is unresolved")
    raw_unit = _text(f"{name} unit", raw_unit)
    _require(raw_unit in _LADDER_INTERVAL_UNITS, f"{name} unit is not canonical")
    lo, hi = _ladder_finite(lower, name=f"{name}.lower"), _ladder_finite(upper, name=f"{name}.upper")
    _require(lo <= hi, f"{name} interval is reversed")
    if require_nonnegative:
        _require(lo >= 0.0, f"{name} interval is negative")
    radius = _ladder_finite(uncertainty, name=f"{name}.uncertainty_radius")
    _require(radius >= 0.0, f"{name} uncertainty radius is negative")
    return (
        MappingProxyType(
            {
                "lower": finite_bits(lo),
                "upper": finite_bits(hi),
                "uncertainty_radius": finite_bits(radius),
                "unit": raw_unit,
                "sign": sign,
            }
        ),
        lo,
        hi,
    )


def _ladder_canonical_interval(value: Any, *, name: str, require_nonnegative: bool = True) -> Mapping[str, Any]:
    result, _, _ = _ladder_interval(value, name=name, unit="item", require_nonnegative=require_nonnegative)
    return result


def _ladder_horizon(value: Any, *, name: str = "physical_horizon") -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        _require({"num", "den", "unit"} <= set(value), f"{name} requires num, den, and unit")
        raw_num, raw_den, raw_unit = value["num"], value["den"], value["unit"]
    elif all(hasattr(value, key) for key in ("num", "den", "unit")):
        raw_num, raw_den, raw_unit = getattr(value, "num"), getattr(value, "den"), getattr(value, "unit")
    else:
        raw_num = raw_den = raw_unit = None
    if raw_num is not None:
        num = _int(f"{name}.num", raw_num, minimum=0)
        den = _int(f"{name}.den", raw_den, minimum=1)
        from math import gcd

        divisor = gcd(num, den)
        num //= divisor
        den //= divisor
        horizon_unit = _text(f"{name}.unit", raw_unit)
        _require(horizon_unit in _LADDER_INTERVAL_UNITS, f"{name} unit is not canonical")
        return MappingProxyType({"num": num, "den": den, "unit": horizon_unit})
    if value is None:
        raise CapacityLadderError(f"{name} is required")
    interval, lower, upper = _ladder_interval(value, name=name, unit="tick")
    _require(lower == upper and lower >= 0.0, f"{name} must be one exact nonnegative horizon")
    from fractions import Fraction

    rational = Fraction(str(lower))
    return MappingProxyType({"num": int(rational.numerator), "den": int(rational.denominator), "unit": str(interval["unit"])})


def _ladder_work_budget(value: Any, *, name: str = "work_budget") -> tuple[Mapping[str, Any], float, float]:
    if isinstance(value, Mapping):
        direct = "lower" in value or "upper" in value or "value" in value
        if direct:
            direct_interval = _ladder_interval(value, name=name, unit=str(value.get("unit", "joule")), sign="nonnegative")
            _require(str(direct_interval[0]["unit"]) in _LADDER_WORK_UNITS, f"{name} unit must be joule or normalized")
            return direct_interval
        known = {
            "incident",
            "source",
            "W_incident",
            "W_source",
            "W_reflected",
            "W_transmitted",
            "W_absorbed",
            "reflected",
            "transmitted",
            "absorbed",
        }
        _require(set(value) <= known and value, f"{name} contains unknown or empty work channels")
        intervals = []
        for key, item in value.items():
            parsed = _ladder_interval(item, name=f"{name}.{key}", unit="joule", sign="nonnegative")
            _require(str(parsed[0]["unit"]) in _LADDER_WORK_UNITS, f"{name}.{key} unit must be joule or normalized")
            intervals.append(parsed)
        unit = str(intervals[0][0]["unit"])
        lower = sum(item[1] for item in intervals)
        upper = sum(item[2] for item in intervals)
        _require(all(str(item[0]["unit"]) == unit for item in intervals), f"{name} units disagree")
        return (
            MappingProxyType({"lower": finite_bits(lower), "upper": finite_bits(upper), "uncertainty_radius": finite_bits(0.0), "unit": unit, "sign": "nonnegative"}),
            lower,
            upper,
        )
    return _ladder_interval(value, name=name, unit="joule", sign="nonnegative")

def _ladder_canonical_state(state: Any, *, state_profile: Any, name: str = "state") -> Any:
    """Return one validated v3 wrapper for the sole adaptive field state."""
    try:
        from cassi_qi_field import QiFieldState, QiFlowStateV3
        from cassi_qi_profile import QiFlowProfile
    except Exception as exc:  # pragma: no cover - import failure is a hard contract failure
        raise CapacityLadderError(f"{name} canonical state imports are unavailable") from exc
    _require(isinstance(state_profile, QiFlowProfile), f"{name} requires an explicit QiFlowProfile")
    if isinstance(state, QiFlowStateV3):
        selected = state
    elif isinstance(state, QiFieldState):
        selected = QiFlowStateV3.from_field(state_profile, state)
    else:
        raise CapacityLadderError(f"{name} must be QiFlowStateV3 or QiFieldState")
    try:
        selected.validate(state_profile)
    except Exception as exc:
        raise CapacityLadderError(f"{name} is not valid for the supplied QiFlowProfile") from exc
    return selected


def _ladder_state_hash(state: Any, *, state_profile: Any = None, name: str = "state") -> str:
    selected = _ladder_canonical_state(state, state_profile=state_profile, name=name)
    try:
        return _ladder_require_sha(selected.state_sha256(state_profile), name=f"{name}.state_sha256")
    except Exception as exc:
        raise CapacityLadderError(f"{name} has no canonical v3 identity") from exc


def _ladder_state_tensor(state: Any, *, state_profile: Any, name: str = "state") -> torch.Tensor:
    selected = _ladder_canonical_state(state, state_profile=state_profile, name=name)
    return selected.field.detach().to(device="cpu", dtype=torch.float64).contiguous()
def _ladder_drive(advance: Any, drive: Any) -> Any:
    _require(hasattr(advance, "execute_advance") and callable(advance.execute_advance), "canonical backend must expose execute_advance")
    if isinstance(drive, Mapping):
        _reject_labels(drive, path="trajectory.drive")
        try:
            from cassi_qi_backend import QiDriveBundle

            allowed = {"delta", "transaction_id", "duration_s", "source", "operator", "geometry_profile", "transport_profile", "profile"}
            unknown = set(str(key) for key in drive) - allowed
            _require(not unknown, "trajectory drive contains unknown fields")
            return QiDriveBundle(**{str(key): value for key, value in drive.items()})
        except Exception as exc:
            raise CapacityLadderError("trajectory drive cannot be converted to the canonical QiDriveBundle") from exc
    if isinstance(drive, (int, float)) and not isinstance(drive, bool):
        from cassi_qi_backend import QiDriveBundle

        return QiDriveBundle(delta=drive)
    raise CapacityLadderError("trajectory drive must be a canonical QiDriveBundle or scalar delta")


def _ladder_advance(advance: Any, state: Any, drive: Any) -> Any:
    _require(hasattr(advance, "execute_advance") and callable(advance.execute_advance), "canonical backend must expose execute_advance")
    return advance.execute_advance(state, _ladder_drive(advance, drive))


def _ladder_step(result: Any) -> tuple[bool, Any, Any]:
    try:
        from cassi_qi_backend import QiFlowStep
    except Exception as exc:  # pragma: no cover - dependency import is a hard failure
        raise CapacityLadderError("canonical backend step type is unavailable") from exc
    _require(isinstance(result, QiFlowStep), "canonical advance must return QiFlowStep")
    _require(isinstance(result.committable, bool), "canonical advance result committable flag is invalid")
    return bool(result.committable), result.candidate, result.predecessor




def _ladder_work_partition(value: Any, *, name: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping) and set(value) == _LADDER_WORK_KEYS, f"{name} must contain exactly the nine canonical work channels")
    rows: dict[str, Any] = {}
    signed = {"closure_residual", "conversion", "residual"}
    for key, item in value.items():
        key_text = _text(f"{name} key", str(key))
        interval_value = item.get("interval", item) if isinstance(item, Mapping) else item
        row = _ladder_canonical_interval(interval_value, name=f"{name}.{key_text}", require_nonnegative=key_text not in signed)
        _require(str(row["unit"]) in _LADDER_WORK_UNITS, f"{name}.{key_text} unit must be joule or normalized")
        rows[key_text] = row
    return MappingProxyType(rows)


def _ladder_work_conservation(
    source: Mapping[str, Any],
    partition: Mapping[str, Any],
    *,
    name: str,
    acquisition: bool,
) -> Mapping[str, Any]:
    """Require one incident charge and a closed interval work ledger."""
    source_unit = str(source["unit"])
    incident = partition["incident"]
    _require(source_unit == str(incident["unit"]), f"{name} source/incident work units disagree")
    source_lower = _ladder_finite(source["lower"], name=f"{name}.source.lower")
    source_upper = _ladder_finite(source["upper"], name=f"{name}.source.upper")
    incident_lower = _ladder_finite(incident["lower"], name=f"{name}.incident.lower")
    incident_upper = _ladder_finite(incident["upper"], name=f"{name}.incident.upper")
    _require(source_lower == incident_lower and source_upper == incident_upper, f"{name} source work is not the incident work")
    if acquisition:
        _require(source_lower > 0.0, f"{name} acquisition source work must be strictly positive")
    rhs_keys = ("admitted", "reflected", "absorbed", "port_reaction", "damping_dissipation", "conversion", "residual")
    rhs_lower = math.fsum(_ladder_finite(partition[key]["lower"], name=f"{name}.{key}.lower") for key in rhs_keys)
    rhs_upper = math.fsum(_ladder_finite(partition[key]["upper"], name=f"{name}.{key}.upper") for key in rhs_keys)
    required_lower = incident_lower - rhs_upper
    required_upper = incident_upper - rhs_lower
    closure = partition["closure_residual"]
    closure_lower = _ladder_finite(closure["lower"], name=f"{name}.closure_residual.lower")
    closure_upper = _ladder_finite(closure["upper"], name=f"{name}.closure_residual.upper")
    _require(closure_lower <= required_lower and closure_upper >= required_upper, f"{name} work ledger is not conserved")
    return MappingProxyType(
        {
            "incident": MappingProxyType({"lower": finite_bits(incident_lower), "upper": finite_bits(incident_upper), "unit": source_unit}),
            "required_closure": MappingProxyType({"lower": finite_bits(required_lower), "upper": finite_bits(required_upper), "unit": source_unit}),
        }
    )



_LADDER_METRIC_NAMES = (
    "impulse_response",
    "coordinate",
    "spatial_mode",
    "fast_to_slow",
    "slow_to_fast",
    "topology_to_fast",
    "delay",
    "growth",
    "retention",
    "discrimination",
)


def _ladder_thresholds(value: Any, *, name: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{name} must declare uncertainty and null thresholds")
    direct = "uncertainty" in value or "uncertainty_radius" in value or "null_threshold" in value
    source = {metric: value for metric in _LADDER_METRIC_NAMES} if direct else dict(value)
    _require(set(source) == set(_LADDER_METRIC_NAMES), f"{name} must cover every W6A metric")
    rows: dict[str, Mapping[str, Any]] = {}
    for metric in _LADDER_METRIC_NAMES:
        item = source[metric]
        _require(isinstance(item, Mapping), f"{name}.{metric} must be a threshold mapping")
        uncertainty = _ladder_finite(item.get("uncertainty_radius", item.get("uncertainty", 0.0)), name=f"{name}.{metric}.uncertainty")
        null_threshold = _ladder_finite(item.get("null_threshold"), name=f"{name}.{metric}.null_threshold")
        _require(uncertainty >= 0.0 and null_threshold >= 0.0, f"{name}.{metric} thresholds must be nonnegative")
        rows[metric] = MappingProxyType(
            {
                "uncertainty_radius": finite_bits(uncertainty),
                "null_threshold": finite_bits(null_threshold),
                "unit": _text(f"{name}.{metric}.unit", item.get("unit", "normalized")),
            }
        )
    return MappingProxyType(rows)


def _ladder_basis(value: Any, *, dimension: int, name: str) -> tuple[torch.Tensor, Mapping[str, Any]]:
    _require(value is not None, f"{name} is required")
    raw = value.get("matrix", value.get("vectors")) if isinstance(value, Mapping) else value
    try:
        matrix = torch.as_tensor(raw, dtype=torch.float64, device="cpu")
    except Exception as exc:
        raise CapacityLadderError(f"{name} is not a finite analytic matrix") from exc
    _require(matrix.ndim == 2 and int(matrix.shape[1]) == dimension and int(matrix.shape[0]) > 0, f"{name} must have shape [K,{dimension}]")
    _require(int(matrix.shape[0]) <= 4096, f"{name} exceeds the bounded metric basis")
    _require(bool(torch.isfinite(matrix).all().item()), f"{name} contains non-finite values")
    values = matrix.tolist()
    descriptor = {
        "basis_sha256": _hash({"name": name, "shape": list(matrix.shape), "values": values}, f"cassi.qi-flow-capacity-{name}.v1"),
        "shape": [int(matrix.shape[0]), int(matrix.shape[1])],
        "kind": "analytic-fixed",
    }
    return matrix, MappingProxyType(descriptor)


def _ladder_metric_interval(value: float, uncertainty: float, *, unit: str = "normalized") -> Mapping[str, Any]:
    magnitude = _ladder_finite(value, name="metric value")
    radius = _ladder_finite(uncertainty, name="metric uncertainty")
    _require(radius >= 0.0, "metric uncertainty must be nonnegative")
    return MappingProxyType(
        {
            "lower": finite_bits(magnitude - radius),
            "upper": finite_bits(magnitude + radius),
            "uncertainty_radius": finite_bits(radius),
            "unit": unit,
        }
    )


def _ladder_matrix_metrics(matrix: torch.Tensor, *, threshold: float, name: str) -> Mapping[str, Any]:
    _require(matrix.ndim == 2 and matrix.shape[0] > 0 and matrix.shape[1] > 0, f"{name} response matrix is empty")
    try:
        singular = torch.linalg.svdvals(matrix)
    except Exception as exc:
        raise CapacityLadderError(f"{name} response matrix is not numerically rankable") from exc
    _require(bool(torch.isfinite(singular).all().item()), f"{name} singular spectrum is non-finite")
    values = [float(item) for item in singular.tolist()]
    rank = sum(value > threshold for value in values)
    null_dimension = max(int(matrix.shape[1]) - rank, 0)
    _, _, vh = torch.linalg.svd(matrix, full_matrices=True)
    null_basis = vh[rank:, :].contiguous() if null_dimension else torch.zeros((0, int(matrix.shape[1])), dtype=torch.float64)
    null_hash = _tensor_hash(
        null_basis,
        f"cassi.qi-flow-capacity-{name}-nullspace.v1",
    )
    response_hash = _tensor_hash(
        matrix,
        f"cassi.qi-flow-capacity-{name}-response.v1",
    )
    return MappingProxyType(
        {
            "response_matrix_sha256": response_hash,
            "rank_interval": _ladder_metric_interval(float(rank), 0.0, unit="item"),
            "singular_spectrum": tuple(_ladder_metric_interval(value, 0.0) for value in values),
            "nullspace": MappingProxyType(
                {
                    "dimension": null_dimension,
                    "basis_sha256": null_hash,
                    "basis_shape": [int(null_basis.shape[0]), int(null_basis.shape[1])],
                }
            ),
            "threshold": finite_bits(threshold),
            "shape": [int(matrix.shape[0]), int(matrix.shape[1])],
        }
    )


def _ladder_metric_measurements(
    *,
    traces: tuple[tuple[torch.Tensor, ...], ...],
    initial_tensor: torch.Tensor,
    source_basis: torch.Tensor,
    readout_basis: torch.Tensor,
    source_descriptor: Mapping[str, Any],
    readout_descriptor: Mapping[str, Any],
    thresholds: Mapping[str, Any],
    horizon: Mapping[str, Any],
    backend_capacity: Any,
) -> Mapping[str, Any]:
    _require(traces, "W6A metric traces are empty")
    final_vectors = torch.stack(tuple(trace[-1].reshape(-1) - initial_tensor.reshape(-1) for trace in traces))
    dimension = int(final_vectors.shape[1])
    _require(int(source_basis.shape[1]) == dimension and int(readout_basis.shape[1]) == dimension, "analytic bases do not match the state dimension")
    threshold = _ladder_finite(thresholds["impulse_response"]["null_threshold"], name="impulse_response null threshold")
    source_response = final_vectors @ source_basis.T
    readout_response = final_vectors @ readout_basis.T
    shape = tuple(int(item) for item in initial_tensor.shape)
    _require(len(shape) == 3, "canonical field state must retain [S,9M,B] shape")
    scales, packed, lanes = shape
    full_by_scale = final_vectors.reshape(len(traces), scales, packed * lanes)
    path_vectors = {
        "coordinate": final_vectors,
        "spatial_mode": full_by_scale.mean(dim=1),
        "fast_to_slow": torch.cat((full_by_scale[:, 0, :], full_by_scale[:, -1, :]), dim=1),
        "slow_to_fast": torch.cat((full_by_scale[:, -1, :], full_by_scale[:, 0, :]), dim=1),
        "topology_to_fast": torch.cat((full_by_scale[:, -1, : min(8, packed * lanes)], full_by_scale[:, 0, : min(8, packed * lanes)]), dim=1),
    }
    impulse: dict[str, Any] = {}
    for path, matrix in path_vectors.items():
        path_threshold = _ladder_finite(thresholds[path]["null_threshold"], name=f"{path} null threshold")
        impulse[path] = _ladder_matrix_metrics(matrix, threshold=path_threshold, name=path)
    coordinate_rows = []
    coordinate_uncertainty = _ladder_finite(thresholds["coordinate"]["uncertainty_radius"], name="coordinate uncertainty")
    coordinate_threshold = _ladder_finite(thresholds["coordinate"]["null_threshold"], name="coordinate null threshold")
    for index in range(dimension):
        magnitude = float(torch.max(torch.abs(final_vectors[:, index])).item())
        reach_interval = _ladder_metric_interval(magnitude, coordinate_uncertainty)
        observable_interval = _ladder_metric_interval(magnitude, coordinate_uncertainty)
        coordinate_rows.append(
            MappingProxyType(
                {
                    "coordinate": index,
                    "D": reach_interval,
                    "C": observable_interval,
                    "V_D": bool(magnitude - coordinate_uncertainty > coordinate_threshold),
                    "V_C": bool(magnitude - coordinate_uncertainty > coordinate_threshold),
                    "epsilon2": _ladder_metric_interval(coordinate_threshold, coordinate_uncertainty),
                    "reachability": reach_interval,
                    "observability": observable_interval,
                    "reachable": bool(magnitude - coordinate_uncertainty > coordinate_threshold),
                    "observable": bool(magnitude - coordinate_uncertainty > coordinate_threshold),
                    "null_threshold": finite_bits(coordinate_threshold),
                }
            )
        )
    horizon_num = int(horizon["num"])
    horizon_den = int(horizon["den"])
    step_delays: list[float] = []
    growth_values: list[float] = []
    retention_values: list[float] = []
    for trace in traces:
        norms = [float(torch.linalg.vector_norm(item.reshape(-1) - initial_tensor.reshape(-1)).item()) for item in trace]
        peak = max(norms, default=0.0)
        first = next((index for index, value in enumerate(norms) if value > threshold), len(norms))
        step_count = max(len(norms) - 1, 1)
        step_delays.append(float(first * horizon_num) / float(step_count * horizon_den))
        baseline = norms[0] if norms[0] > threshold else max(threshold, 1.0)
        growth_values.append(peak / baseline)
        retention_values.append(0.0 if peak <= 0.0 else norms[-1] / peak)
    pairwise = []
    for left in range(len(final_vectors)):
        for right in range(left + 1, len(final_vectors)):
            pairwise.append(float(torch.linalg.vector_norm(final_vectors[left] - final_vectors[right]).item()))
    discrimination_threshold = _ladder_finite(thresholds["discrimination"]["null_threshold"], name="discrimination null threshold")
    delay_uncertainty = _ladder_finite(thresholds["delay"]["uncertainty_radius"], name="delay uncertainty")
    growth_uncertainty = _ladder_finite(thresholds["growth"]["uncertainty_radius"], name="growth uncertainty")
    retention_uncertainty = _ladder_finite(thresholds["retention"]["uncertainty_radius"], name="retention uncertainty")
    discrimination_uncertainty = _ladder_finite(thresholds["discrimination"]["uncertainty_radius"], name="discrimination uncertainty")
    delay_interval = _ladder_metric_interval(max(step_delays, default=0.0), delay_uncertainty, unit=str(horizon["unit"]))
    growth_interval = _ladder_metric_interval(max(growth_values, default=0.0), growth_uncertainty)
    retention_interval = _ladder_metric_interval(max(retention_values, default=0.0), retention_uncertainty)
    discrimination_interval = _ladder_metric_interval(min(pairwise, default=0.0), discrimination_uncertainty)
    state_bytes = int(initial_tensor.numel()) * 8
    workspace_bytes = state_bytes + sum(int(matrix.numel()) * 8 for matrix in path_vectors.values()) + int(source_response.numel() + readout_response.numel()) * 8
    declared_workspace = int(getattr(backend_capacity, "working_memory_budget", workspace_bytes))
    return MappingProxyType(
        {
            "analytic_source_basis": MappingProxyType(dict(source_descriptor)),
            "analytic_readout_basis": MappingProxyType(dict(readout_descriptor)),
            "impulse_responses": MappingProxyType(impulse),
            "coordinate_reachability_observability": tuple(coordinate_rows),
            "delay_growth_retention_discrimination": MappingProxyType(
                {
                    "delay": delay_interval,
                    "growth": growth_interval,
                    "decay": _ladder_metric_interval(1.0 / max(_ladder_finite(growth_interval["upper"], name="growth upper"), 1.0), growth_uncertainty),
                    "retention": retention_interval,
                    "discrimination": discrimination_interval,
                    "discrimination_clears_null": bool(min(pairwise, default=0.0) - discrimination_uncertainty > discrimination_threshold),
                    "retained_claim": False,
                    "reusable_claim": False,
                }
            ),
            "state_workspace_bytes": MappingProxyType(
                {
                    "state_bytes": state_bytes,
                    "workspace_bytes": workspace_bytes,
                    "declared_workspace_budget": declared_workspace,
                }
            ),
            "source_response": _ladder_matrix_metrics(source_response, threshold=threshold, name="source"),
            "readout_response": _ladder_matrix_metrics(readout_response, threshold=threshold, name="readout"),
        }
    )



def _ladder_diagnostics_payload(
    *,
    analytic_source_basis: Mapping[str, Any],
    analytic_readout_basis: Mapping[str, Any],
    impulse_responses: Mapping[str, Any],
    coordinate_reachability_observability: Any,
    delay_growth_retention_discrimination: Mapping[str, Any],
    uncertainty_null_thresholds: Mapping[str, Any],
    state_workspace_bytes: Mapping[str, Any],
) -> Mapping[str, Any]:
    return MappingProxyType(
        {
            "schema": "cassi.qi-flow-capacity-diagnostics.v1",
            "analytic_source_basis": _plain(analytic_source_basis),
            "analytic_readout_basis": _plain(analytic_readout_basis),
            "impulse_responses": _plain(impulse_responses),
            "coordinate_reachability_observability": _plain(coordinate_reachability_observability),
            "delay_growth_retention_discrimination": _plain(delay_growth_retention_discrimination),
            "uncertainty_null_thresholds": _plain(uncertainty_null_thresholds),
            "state_workspace_bytes": _plain(state_workspace_bytes),
        }
    )
def _ladder_trajectory_ids(value: Any) -> tuple[str, ...]:
    _require(isinstance(value, (tuple, list)) and value, "trajectory registry is empty")
    ids = tuple(_ladder_identifier(item, name="trajectory id") for item in value)
    _require(len(ids) == len(set(ids)), "trajectory ids are duplicated")
    return ids


@dataclass(frozen=True)
class QiCapacityLadderReceipt:
    """Immutable W6A capacity ladder from canonical advance trajectories."""

    profile_sha256: str
    state_contract_sha256: str
    backend_capacity_sha256: str
    initial_state_sha256: str
    controller_grammar_sha256: str
    physical_horizon: Mapping[str, Any]
    trajectory_set_sha256: str
    trajectory_ids: tuple[str, ...]
    work_budget: Mapping[str, Any]
    capacity_levels: Mapping[str, int]
    capacity_intervals: Mapping[str, Mapping[str, Any]]
    reachability_witnesses: tuple[Mapping[str, Any], ...]
    reset_control_sha256: str
    saturation_control_sha256: str
    overwrite_control_sha256: str
    washout_recovery_schedule_sha256: str
    consumed_semantic_subhashes: tuple[Mapping[str, str], ...]
    topology_codebook_sha256: str
    topology_witnesses: tuple[Mapping[str, Any], ...]
    ladder_order: tuple[str, ...] = CAPACITY_LADDER_LEVELS
    acquisition_eligibility: Mapping[str, Any] = MappingProxyType({})
    barrier_interval: Mapping[str, Any] = MappingProxyType({})
    closure_residual: Mapping[str, Any] = MappingProxyType({})
    reset_counts_as_acquisition: bool = False
    receipt_id: str = ""
    self_sha256: str = ""
    analytic_source_basis: Mapping[str, Any] = MappingProxyType({})
    analytic_readout_basis: Mapping[str, Any] = MappingProxyType({})
    impulse_responses: Mapping[str, Any] = MappingProxyType({})
    coordinate_reachability_observability: tuple[Mapping[str, Any], ...] = ()
    delay_growth_retention_discrimination: Mapping[str, Any] = MappingProxyType({})
    uncertainty_null_thresholds: Mapping[str, Any] = MappingProxyType({})
    state_workspace_bytes: Mapping[str, Any] = MappingProxyType({})
    trajectory_script_hashes: Mapping[str, str] = MappingProxyType({})
    control_hashes: Mapping[str, str] = MappingProxyType({})

    def __post_init__(self) -> None:
        for name in (
            "profile_sha256",
            "state_contract_sha256",
            "backend_capacity_sha256",
            "initial_state_sha256",
            "controller_grammar_sha256",
            "trajectory_set_sha256",
            "reset_control_sha256",
            "saturation_control_sha256",
            "overwrite_control_sha256",
            "washout_recovery_schedule_sha256",
            "topology_codebook_sha256",
        ):
            _ladder_require_sha(getattr(self, name), name=f"ladder.{name}")
        horizon = _ladder_horizon(self.physical_horizon)
        object.__setattr__(self, "physical_horizon", horizon)
        budget, _, _ = _ladder_work_budget(self.work_budget)
        object.__setattr__(self, "work_budget", _ladder_schema_interval(budget, name="work_budget", kind="work"))
        ids = _ladder_trajectory_ids(self.trajectory_ids)
        object.__setattr__(self, "trajectory_ids", ids)
        scripts = dict(self.trajectory_script_hashes)
        _require(set(scripts) == set(ids), "ladder trajectory script hashes are incomplete")
        canonical_scripts = {str(key): _ladder_require_sha(value, name=f"trajectory script {key}") for key, value in scripts.items()}
        object.__setattr__(self, "trajectory_script_hashes", MappingProxyType(canonical_scripts))
        levels = {}
        for key, value in dict(self.capacity_levels).items():
            level_value = _int(f"capacity level {key}", value, minimum=0)
            _require(level_value <= 1048576, f"capacity level {key} exceeds schema bound")
            levels[str(key)] = level_value
        _require(set(levels) == set(CAPACITY_LADDER_LEVELS), "capacity ladder levels are incomplete")
        _require(all(levels[left] >= levels[right] for left, right in zip(CAPACITY_LADDER_LEVELS, CAPACITY_LADDER_LEVELS[1:])), "capacity ladder levels are not nested")
        object.__setattr__(self, "capacity_levels", MappingProxyType(levels))
        intervals: dict[str, Mapping[str, Any]] = {}
        for level in CAPACITY_LADDER_LEVELS:
            _require(level in self.capacity_intervals, f"capacity interval {level} is missing")
            item, lower, upper = _ladder_interval(self.capacity_intervals[level], name=f"capacity_intervals.{level}", unit="item")
            _require(str(item["unit"]) in {"item", "normalized"}, f"capacity interval {level} unit is invalid")
            _require(lower <= float(levels[level]) <= upper, f"capacity interval {level} does not enclose its level")
            intervals[level] = _ladder_schema_interval(item, name=f"capacity_intervals.{level}", kind="capacity")
        object.__setattr__(self, "capacity_intervals", MappingProxyType(intervals))
        witnesses: list[Mapping[str, Any]] = []
        known_ids = set(ids)
        _require(1 <= len(self.reachability_witnesses) <= 4096, "capacity witness registry exceeds schema bound")
        for item in self.reachability_witnesses:
            _require(isinstance(item, Mapping), "capacity witness is not a mapping")
            witness = dict(item)
            _require(str(witness.get("trajectory_id", "")) in known_ids, "capacity witness references an unknown trajectory")
            for key in ("candidate_head_sha256", "endpoint_head_sha256", "predecessor_head_sha256", "zero_clock_transport_sha256"):
                _ladder_require_sha(witness.get(key), name=f"capacity witness {key}")
            advance_count = _int("capacity witness advance_count", witness.get("advance_count"), minimum=1)
            _require(advance_count <= 1048576, "capacity witness advance_count exceeds schema bound")
            witness["source_work"] = _ladder_schema_interval(witness.get("source_work"), name="capacity witness source_work", kind="work")
            _require(str(witness["source_work"]["unit"]) in _LADDER_WORK_UNITS, "capacity witness source_work unit must be joule or normalized")
            _require(isinstance(witness.get("endpoint_admitted"), bool), "capacity witness endpoint_admitted is invalid")
            _require(isinstance(witness.get("strict_improvement"), bool), "capacity witness strict_improvement is invalid")
            _require(isinstance(witness.get("work_partition"), Mapping) and set(witness["work_partition"]) == _LADDER_WORK_KEYS, "capacity witness work partition is incomplete")
            witness["work_partition"] = MappingProxyType({str(key): _ladder_schema_interval(value, name=f"capacity witness work_partition.{key}", kind="signed" if str(key) in {"closure_residual", "conversion", "residual"} else "work") for key, value in witness["work_partition"].items()})
            _ladder_work_conservation(
                witness["source_work"],
                witness["work_partition"],
                name=f"trajectory {witness['trajectory_id']}",
                acquisition=True,
            )
            witnesses.append(_freeze(witness))
        object.__setattr__(self, "reachability_witnesses", tuple(witnesses))
        for name in ("reset_control_sha256", "saturation_control_sha256", "overwrite_control_sha256", "washout_recovery_schedule_sha256"):
            _ladder_require_sha(getattr(self, name), name=f"ladder.{name}")
        _require(self.reset_counts_as_acquisition is False, "reset cannot count as acquisition")
        object.__setattr__(self, "consumed_semantic_subhashes", tuple(_freeze(item) for item in self.consumed_semantic_subhashes))
        for item in self.consumed_semantic_subhashes:
            _require(isinstance(item, Mapping), "consumed subhash row is not a mapping")
            _require(item.get("name") in _LADDER_SUBHASH_NAMES, "consumed subhash name is not canonical")
            _ladder_require_sha(item.get("sha256"), name="consumed subhash")
        eligibility = dict(self.acquisition_eligibility)
        _require(eligibility, "acquisition eligibility is missing")
        _require(_is_sha256(eligibility.get("eligibility_sha256")), "acquisition eligibility identity is invalid")
        eligibility_without_hash = dict(eligibility)
        eligibility_without_hash.pop("eligibility_sha256", None)
        _require(_hash(eligibility_without_hash, "cassi.qi-flow-capacity-acquisition-eligibility.v1") == eligibility["eligibility_sha256"], "acquisition eligibility identity mismatch")
        _require(eligibility.get("ordinary_step_required") is True and eligibility.get("reset_counted_as_acquisition") is False and eligibility.get("reset_excluded") is True and eligibility.get("successful_reproduction_required") is True and eligibility.get("zero_clock_transition_excluded") is True, "acquisition eligibility is unsafe")
        object.__setattr__(self, "acquisition_eligibility", MappingProxyType(eligibility))
        barrier, _, _ = _ladder_interval(self.barrier_interval, name="barrier_interval", unit="tick")
        object.__setattr__(self, "barrier_interval", _ladder_schema_interval(barrier, name="barrier_interval", kind="barrier"))
        residual, _, _ = _ladder_interval(self.closure_residual, name="closure_residual", unit="joule", sign="signed", require_nonnegative=False)
        _require(str(residual["unit"]) in _LADDER_WORK_UNITS, "closure residual unit must be joule or normalized")
        metric_maps = (
            ("analytic_source_basis", self.analytic_source_basis),
            ("analytic_readout_basis", self.analytic_readout_basis),
            ("impulse_responses", self.impulse_responses),
            ("delay_growth_retention_discrimination", self.delay_growth_retention_discrimination),
            ("uncertainty_null_thresholds", self.uncertainty_null_thresholds),
            ("state_workspace_bytes", self.state_workspace_bytes),
            ("trajectory_script_hashes", self.trajectory_script_hashes),
            ("control_hashes", self.control_hashes),
        )
        for metric_name, metric_value in metric_maps:
            _require(isinstance(metric_value, Mapping) and metric_value, f"ladder.{metric_name} is missing")
            object.__setattr__(self, metric_name, _freeze(metric_value))
        coordinates = tuple(_freeze(item) for item in self.coordinate_reachability_observability)
        _require(coordinates, "ladder.coordinate_reachability_observability is missing")
        _require(len(coordinates) <= 1048576, "ladder coordinate metrics exceed schema bound")
        object.__setattr__(self, "coordinate_reachability_observability", coordinates)
        for name in ("analytic_source_basis", "analytic_readout_basis"):
            descriptor = getattr(self, name)
            _ladder_require_sha(descriptor.get("basis_sha256"), name=f"ladder.{name}.basis_sha256")
            shape = descriptor.get("shape")
            _require(isinstance(shape, (tuple, list)) and len(shape) == 2 and all(_int(f"ladder.{name}.shape", item, minimum=1) <= 4096 for item in shape), f"ladder.{name}.shape is invalid")
        scripts = dict(self.trajectory_script_hashes)
        _require(set(scripts) == set(ids), "ladder trajectory script hashes are incomplete")
        object.__setattr__(self, "trajectory_script_hashes", MappingProxyType({str(key): _ladder_require_sha(value, name=f"trajectory script {key}") for key, value in scripts.items()}))
        controls = dict(self.control_hashes)
        expected_controls = {"reset", "saturation", "overwrite", "washout_recovery"}
        _require(set(controls) == expected_controls, "ladder control hashes are incomplete")
        object.__setattr__(self, "control_hashes", MappingProxyType({key: _ladder_require_sha(controls[key], name=f"control {key}") for key in sorted(expected_controls)}))
        _require(len(set(self.control_hashes.values())) == len(expected_controls), "ladder controls must be independently distinct")
        thresholds = _ladder_thresholds(self.uncertainty_null_thresholds, name="ladder.uncertainty_null_thresholds")
        object.__setattr__(self, "uncertainty_null_thresholds", thresholds)
        _require(bool(self.delay_growth_retention_discrimination.get("retained_claim") is False and self.delay_growth_retention_discrimination.get("reusable_claim") is False), "W6A retention claims must remain false")
        _require(int(self.state_workspace_bytes.get("state_bytes", 0)) > 0 and int(self.state_workspace_bytes.get("workspace_bytes", 0)) > 0, "ladder state/workspace bytes are missing")
        _require(set(self.coordinate_reachability_observability[0]) >= {"coordinate", "reachability", "observability", "reachable", "observable", "null_threshold"}, "ladder coordinate metrics are incomplete")
        _require(set(self.impulse_responses) >= {"coordinate", "spatial_mode", "fast_to_slow", "slow_to_fast", "topology_to_fast"}, "ladder impulse responses are incomplete")
        diagnostics_identity = self.diagnostics_sha256
        expected_trajectory_set = _hash(
            {
                "trajectory_ids": list(ids),
                "trajectory_script_hashes": dict(sorted(self.trajectory_script_hashes.items())),
                "diagnostics_sha256": diagnostics_identity,
            },
            "cassi.qi-flow-capacity-trajectory-set.v1",
        )
        _require(self.trajectory_set_sha256 == expected_trajectory_set, "capacity trajectory-set identity mismatch")
        object.__setattr__(self, "closure_residual", _ladder_schema_interval(residual, name="closure_residual", kind="signed"))
        topology_rows = tuple(_freeze(item) for item in self.topology_witnesses)
        _require(topology_rows, "topology witness registry is empty")
        for index, row in enumerate(topology_rows):
            _require(isinstance(row, Mapping), f"topology witness {index} is not a mapping")
            _require(str(row.get("codebook_sha256", "")) == self.topology_codebook_sha256, f"topology witness {index} codebook mismatch")
            witness_hash = row.get("witness_sha256", row.get("raw_witness_sha256", row.get("self_sha256")))
            _ladder_require_sha(witness_hash, name=f"topology witness {index}")
        object.__setattr__(self, "topology_witnesses", topology_rows)
        _require(self.ladder_order == CAPACITY_LADDER_LEVELS, "capacity ladder order is not canonical")
        expected_id = _hash({"profile_sha256": self.profile_sha256, "trajectory_set_sha256": self.trajectory_set_sha256, "capacity_levels": dict(levels)}, CAPACITY_LADDER_ID_DOMAIN)
        if self.receipt_id:
            _require(self.receipt_id == expected_id, "capacity ladder receipt id mismatch")
        else:
            object.__setattr__(self, "receipt_id", expected_id)
        expected = _hash(self.payload(), CAPACITY_LADDER_DOMAIN)
        if self.self_sha256:
            _require(self.self_sha256 == expected, "capacity ladder receipt identity mismatch")
        else:
            object.__setattr__(self, "self_sha256", expected)

    @property
    def schema(self) -> str:
        return CAPACITY_LADDER_SCHEMA

    @property
    def scope(self) -> str:
        return "W6A-intrinsic-capacity"

    @property
    def ordered_trajectory_ids(self) -> tuple[str, ...]:
        return self.trajectory_ids

    @property
    def capacity_ladder_sha256(self) -> str:
        return self.self_sha256

    def payload(self) -> dict[str, Any]:
        return {
            "schema": CAPACITY_LADDER_SCHEMA,
            "receipt_id": self.receipt_id,
            "profile_sha256": self.profile_sha256,
            "state_contract_sha256": self.state_contract_sha256,
            "backend_capacity_sha256": self.backend_capacity_sha256,
            "initial_state_sha256": self.initial_state_sha256,
            "controller_grammar_sha256": self.controller_grammar_sha256,
            "physical_horizon": _plain(self.physical_horizon),
            "trajectory_set_sha256": self.trajectory_set_sha256,
            "trajectory_ids": list(self.trajectory_ids),
            "work_budget": _plain(self.work_budget),
            "capacity_levels": dict(self.capacity_levels),
            "capacity_intervals": _plain(self.capacity_intervals),
            "reachability_witnesses": _plain(self.reachability_witnesses),
            "reset_control_sha256": self.reset_control_sha256,
            "saturation_control_sha256": self.saturation_control_sha256,
            "overwrite_control_sha256": self.overwrite_control_sha256,
            "washout_recovery_schedule_sha256": self.washout_recovery_schedule_sha256,
            "consumed_semantic_subhashes": _plain(self.consumed_semantic_subhashes),
            "topology_codebook_sha256": self.topology_codebook_sha256,
            "topology_witnesses": _plain(self.topology_witnesses),
            "ladder_order": list(self.ladder_order),
            "acquisition_eligibility": _plain(self.acquisition_eligibility),
            "barrier_interval": _plain(self.barrier_interval),
            "closure_residual": _plain(self.closure_residual),
            "reset_counts_as_acquisition": self.reset_counts_as_acquisition,
        }

    def diagnostics_payload(self) -> Mapping[str, Any]:
        return _ladder_diagnostics_payload(
            analytic_source_basis=self.analytic_source_basis,
            analytic_readout_basis=self.analytic_readout_basis,
            impulse_responses=self.impulse_responses,
            coordinate_reachability_observability=self.coordinate_reachability_observability,
            delay_growth_retention_discrimination=self.delay_growth_retention_discrimination,
            uncertainty_null_thresholds=self.uncertainty_null_thresholds,
            state_workspace_bytes=self.state_workspace_bytes,
        )

    @property
    def diagnostics_sha256(self) -> str:
        return _hash(self.diagnostics_payload(), "cassi.qi-flow-capacity-diagnostics.v1")

    def to_dict(self) -> Mapping[str, Any]:
        return MappingProxyType(self.payload() | {"self_sha256": self.self_sha256})
def _ladder_schema_interval(value: Any, *, name: str, kind: str) -> Mapping[str, Any]:
    signed = kind == "signed"
    item, _, _ = _ladder_interval(value, name=name, unit="item", sign="signed" if signed else "nonnegative", require_nonnegative=not signed)
    keys = ("lower", "sign", "unit", "upper") if kind in {"work", "signed"} else (("lower", "uncertainty_radius", "unit", "upper") if kind == "capacity" else ("lower", "unit", "upper"))
    return MappingProxyType({key: item[key] for key in keys})


def _ladder_live_dependencies(
    *,
    profile: Any,
    backend_capacity: Any,
    topology_profile: Any,
    profile_sha256: str | None,
    state_contract_sha256: str | None,
    backend_capacity_sha256: str | None,
    topology_codebook_sha256: str | None,
) -> tuple[str, str, str, str]:
    try:
        from cassi_qi_backend import QiCapacityProfile
        from cassi_qi_profile import QiFlowProfile
        from cassi_qi_topology import QiTopologyProfile
    except Exception as exc:  # pragma: no cover - dependency import is a hard failure
        raise CapacityLadderError("W6A live dependencies are unavailable") from exc
    _require(isinstance(profile, QiFlowProfile), "W6A requires an explicit QiFlowProfile")
    _require(isinstance(backend_capacity, QiCapacityProfile), "W6A requires an explicit QiCapacityProfile")
    _require(isinstance(topology_profile, QiTopologyProfile), "W6A requires an explicit W4R QiTopologyProfile")
    selected_profile = _ladder_require_sha(profile.profile_sha256, name="profile.profile_sha256")
    selected_state = _ladder_require_sha(profile.state_contract_sha256, name="profile.state_contract_sha256")
    selected_backend = _ladder_require_sha(backend_capacity.capacity_sha256, name="backend_capacity.capacity_sha256")
    selected_topology = _ladder_require_sha(topology_profile.topology_codebook_sha256, name="topology_profile.topology_codebook_sha256")
    for supplied, selected, name in (
        (profile_sha256, selected_profile, "ladder.profile_sha256"),
        (state_contract_sha256, selected_state, "ladder.state_contract_sha256"),
        (backend_capacity_sha256, selected_backend, "ladder.backend_capacity_sha256"),
        (topology_codebook_sha256, selected_topology, "ladder.topology_codebook_sha256"),
    ):
        if supplied is not None:
            _require(_ladder_require_sha(supplied, name=name) == selected, f"{name} does not match its validated dependency")
    return selected_profile, selected_state, selected_backend, selected_topology


def _ladder_control_hash(
    value: Any,
    *,
    supplied: str | None,
    name: str,
) -> str:
    """Hash a frozen control payload, never accept an unbound opaque label."""
    _require(value is not None, f"{name} payload is required for independent replay")
    payload = _source_payload(value, name=f"{name} payload")
    digest = _hash(payload, f"cassi.qi-flow-capacity-{name}.v1")
    if supplied is not None:
        _require(_ladder_require_sha(supplied, name=name) == digest, f"{name} hash does not match its payload")
    return digest

def _ladder_profile_value(profile: Any, name: str, default: Any = None) -> Any:
    value = _attr(profile, name, None)
    if value is not None:
        return value
    payload = _source_payload(profile, name="capacity profile") if profile is not None else {}
    return payload.get(name, default)


def _ladder_profile_hash(profile: Any, name: str) -> str | None:
    value = _ladder_profile_value(profile, name)
    return None if value is None else str(value)


def _ladder_topology_witnesses(profile: Any, topology_witnesses: Any, *, topology_hash: str) -> tuple[Mapping[str, Any], ...]:
    source = topology_witnesses
    if source is None and profile is not None:
        source = _ladder_profile_value(profile, "topology_witnesses")
    _require(isinstance(source, (tuple, list)) and 2 <= len(source) <= 4096, "topology witness registry must contain two to 4096 entries")
    rows = tuple(_ladder_validate_topology_witness(item, index=index, topology_hash=topology_hash) for index, item in enumerate(source))
    _require(len({row["witness_id"] for row in rows}) == len(rows), "topology witness ids are duplicated")
    return rows

_LADDER_TOPOLOGY_REQUIRED = frozenset(
    {
        "witness_id",
        "endpoint_state_sha256",
        "grid_shape",
        "slow_scale",
        "edge_registry_sha256",
        "edge_phase_raw_intervals",
        "endpoint_amplitude_witness",
        "endpoint_branch_witness",
        "cycle_winding_witness",
        "plaquette_witness",
        "sector_vector",
        "torus_algebra_witness",
        "codebook_sha256",
        "sector_transport_sha256",
        "minimum_amplitude_lower_bound",
        "minimum_branch_margin_lower_bound",
        "raw_witness_sha256",
        "pass",
    }
)


def _ladder_raw_interval(value: Any, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CapacityLadderError(f"{name} must be an interval mapping")
    _require(set(value) == {"lower", "upper", "unit"}, f"{name} has noncanonical fields")
    lower = _ladder_finite(value["lower"], name=f"{name}.lower")
    upper = _ladder_finite(value["upper"], name=f"{name}.upper")
    _require(lower <= upper, f"{name} is reversed")
    unit = _text(f"{name}.unit", value["unit"])
    _require(unit in _LADDER_INTERVAL_UNITS, f"{name} unit is not canonical")
    return MappingProxyType({"lower": finite_bits(lower), "unit": unit, "upper": finite_bits(upper)})


def _ladder_validate_topology_witness(item: Any, *, index: int, topology_hash: str) -> Mapping[str, Any]:
    _require(isinstance(item, Mapping), f"topology witness {index} is not a mapping")
    _reject_labels(item, path=f"topology_witnesses[{index}]")
    _require(set(item) == _LADDER_TOPOLOGY_REQUIRED, f"topology witness {index} is incomplete")
    row = dict(item)
    _require(row["codebook_sha256"] == topology_hash, f"topology witness {index} codebook mismatch")
    for key in ("endpoint_state_sha256", "edge_registry_sha256", "codebook_sha256", "sector_transport_sha256", "raw_witness_sha256"):
        _ladder_require_sha(row[key], name=f"topology witness {index}.{key}")
    row["witness_id"] = _ladder_identifier(row["witness_id"], name=f"topology witness {index}.witness_id")
    _require(row["pass"] is True, f"topology witness {index} did not pass")
    _require(isinstance(row["grid_shape"], (tuple, list)) and len(row["grid_shape"]) == 2, f"topology witness {index} grid shape is invalid")
    row["grid_shape"] = tuple(_int(f"topology witness {index}.grid_shape", value, minimum=0) for value in row["grid_shape"])
    _require(all(value <= 1048576 for value in row["grid_shape"]), f"topology witness {index} grid shape exceeds schema bound")
    row["slow_scale"] = finite_bits(_ladder_finite(row["slow_scale"], name=f"topology witness {index}.slow_scale"))
    row["minimum_amplitude_lower_bound"] = finite_bits(_ladder_finite(row["minimum_amplitude_lower_bound"], name=f"topology witness {index}.minimum_amplitude_lower_bound"))
    row["minimum_branch_margin_lower_bound"] = finite_bits(_ladder_finite(row["minimum_branch_margin_lower_bound"], name=f"topology witness {index}.minimum_branch_margin_lower_bound"))
    sector = row["sector_vector"]
    _require(isinstance(sector, Mapping) and set(sector) == {"cycle_x", "cycle_y", "plaquette"}, f"topology witness {index} sector vector is invalid")
    row["sector_vector"] = {
        key: tuple(_int(f"topology witness {index}.{key}", value, minimum=-1048576) for value in sector[key])
        for key in ("cycle_x", "cycle_y", "plaquette")
    }
    _require(all(row["sector_vector"][key] and all(value <= 1048576 for value in row["sector_vector"][key]) for key in row["sector_vector"]), f"topology witness {index} sector vector is empty or out of bounds")
    edge_rows = []
    for edge_index, edge in enumerate(row["edge_phase_raw_intervals"]):
        _require(isinstance(edge, Mapping) and set(edge) == {"edge_id", "raw_phase_interval", "uncertainty_half_width", "branch_margin_lower_bound"}, f"topology witness {index} edge phase row is invalid")
        edge_rows.append(
            {
                "edge_id": _ladder_identifier(edge["edge_id"], name=f"topology witness {index}.edge_id"),
                "raw_phase_interval": _ladder_raw_interval(edge["raw_phase_interval"], name=f"topology witness {index}.raw_phase_interval"),
                "uncertainty_half_width": finite_bits(_ladder_finite(edge["uncertainty_half_width"], name=f"topology witness {index}.uncertainty_half_width")),
                "branch_margin_lower_bound": finite_bits(_ladder_finite(edge["branch_margin_lower_bound"], name=f"topology witness {index}.branch_margin_lower_bound")),
            }
        )
    _require(edge_rows, f"topology witness {index} has no edge phase rows")
    row["edge_phase_raw_intervals"] = tuple(edge_rows)
    amp_rows = []
    for amp in row["endpoint_amplitude_witness"]:
        _require(isinstance(amp, Mapping) and set(amp) == {"site_id", "psi_modulus_interval", "uncertainty_radius", "lower_bound", "threshold", "pass"}, f"topology witness {index} amplitude row is invalid")
        amp_rows.append(
            {
                "site_id": _ladder_identifier(amp["site_id"], name=f"topology witness {index}.site_id"),
                "psi_modulus_interval": _ladder_raw_interval(amp["psi_modulus_interval"], name=f"topology witness {index}.psi_modulus_interval"),
                "uncertainty_radius": finite_bits(_ladder_finite(amp["uncertainty_radius"], name=f"topology witness {index}.uncertainty_radius")),
                "lower_bound": finite_bits(_ladder_finite(amp["lower_bound"], name=f"topology witness {index}.lower_bound")),
                "threshold": finite_bits(_ladder_finite(amp["threshold"], name=f"topology witness {index}.threshold")),
                "pass": amp["pass"],
            }
        )
    _require(amp_rows and all(item["pass"] is True for item in amp_rows), f"topology witness {index} amplitude witness did not pass")
    row["endpoint_amplitude_witness"] = tuple(amp_rows)
    branch_rows = []
    for branch in row["endpoint_branch_witness"]:
        _require(isinstance(branch, Mapping) and set(branch) == {"edge_id", "delta_interval", "uncertainty_half_width", "branch_margin_lower_bound", "pass"}, f"topology witness {index} branch row is invalid")
        branch_rows.append(
            {
                "edge_id": _ladder_identifier(branch["edge_id"], name=f"topology witness {index}.branch edge_id"),
                "delta_interval": _ladder_raw_interval(branch["delta_interval"], name=f"topology witness {index}.delta_interval"),
                "uncertainty_half_width": finite_bits(_ladder_finite(branch["uncertainty_half_width"], name=f"topology witness {index}.branch uncertainty_half_width")),
                "branch_margin_lower_bound": finite_bits(_ladder_finite(branch["branch_margin_lower_bound"], name=f"topology witness {index}.branch margin")),
                "pass": branch["pass"],
            }
        )
    _require(branch_rows and all(item["pass"] is True for item in branch_rows), f"topology witness {index} branch witness did not pass")
    row["endpoint_branch_witness"] = tuple(branch_rows)
    for key, minimum in (("cycle_winding_witness", 2), ("plaquette_witness", 1)):
        witness_rows = []
        for witness in row[key]:
            expected = {"axis", "index", "raw_interval", "rounded_integer", "integer_margin_lower_bound", "pass"} if key == "cycle_winding_witness" else {"origin", "raw_interval", "rounded_integer", "integer_margin_lower_bound", "pass"}
            _require(isinstance(witness, Mapping) and set(witness) == expected, f"topology witness {index} {key} row is invalid")
            witness_row = dict(witness)
            if key == "cycle_winding_witness":
                _require(witness_row["axis"] in {"x", "y"}, f"topology witness {index} winding axis is invalid")
                witness_row["index"] = _int(f"topology witness {index} winding index", witness_row["index"], minimum=0)
                _require(witness_row["index"] <= 1048576, f"topology witness {index} winding index exceeds schema bound")
            else:
                witness_row["origin"] = _ladder_identifier(witness_row["origin"], name=f"topology witness {index}.plaquette origin")
            witness_row["raw_interval"] = _ladder_raw_interval(witness_row["raw_interval"], name=f"topology witness {index}.raw_interval")
            witness_row["rounded_integer"] = _int(f"topology witness {index}.rounded_integer", witness_row["rounded_integer"], minimum=-1048576)
            _require(witness_row["pass"] is True, f"topology witness {index} integer witness is invalid")
            _require(witness_row["rounded_integer"] <= 1048576, f"topology witness {index} rounded integer exceeds schema bound")
            witness_row["integer_margin_lower_bound"] = finite_bits(_ladder_finite(witness_row["integer_margin_lower_bound"], name=f"topology witness {index}.integer_margin_lower_bound"))
            witness_rows.append(witness_row)
        _require(len(witness_rows) >= minimum, f"topology witness {index} {key} is too short")
        row[key] = tuple(witness_rows)
    torus = row["torus_algebra_witness"]
    _require(isinstance(torus, Mapping) and set(torus) == {"x_cycle_residual_intervals", "y_cycle_residual_intervals", "total_plaquette_interval", "integer_closure", "max_residual_upper_bound", "pass"}, f"topology witness {index} torus witness is invalid")
    _require(torus["integer_closure"] is True and torus["pass"] is True, f"topology witness {index} torus closure did not pass")
    row["torus_algebra_witness"] = {
        "x_cycle_residual_intervals": tuple(_ladder_raw_interval(item, name=f"topology witness {index}.x residual") for item in torus["x_cycle_residual_intervals"]),
        "y_cycle_residual_intervals": tuple(_ladder_raw_interval(item, name=f"topology witness {index}.y residual") for item in torus["y_cycle_residual_intervals"]),
        "total_plaquette_interval": _ladder_raw_interval(torus["total_plaquette_interval"], name=f"topology witness {index}.plaquette residual"),
        "integer_closure": True,
        "max_residual_upper_bound": finite_bits(_ladder_finite(torus["max_residual_upper_bound"], name=f"topology witness {index}.max residual")),
        "pass": True,
    }
    _require(row["torus_algebra_witness"]["x_cycle_residual_intervals"] and row["torus_algebra_witness"]["y_cycle_residual_intervals"], f"topology witness {index} torus residual intervals are empty")
    return _freeze(row)

def _ladder_controller_hash(value: Any) -> str:
    if isinstance(value, str) and _is_sha256(value):
        return value
    if isinstance(value, str):
        return _hash({"controller_grammar": value}, CAPACITY_LADDER_CONTROLLER_DOMAIN)
    payload = _source_payload(value, name="controller grammar")
    supplied = payload.get("controller_grammar_sha256", payload.get("self_sha256"))
    if supplied is not None:
        return _ladder_require_sha(supplied, name="controller grammar")
    return _hash(payload, CAPACITY_LADDER_CONTROLLER_DOMAIN)


def _ladder_horizon_seconds(value: Mapping[str, Any]) -> float:
    return float(value["num"]) / float(value["den"])


def _ladder_trajectory_spec(spec: Any, *, index: int) -> Mapping[str, Any]:
    _require(isinstance(spec, Mapping), f"trajectory {index} is not a mapping")
    _reject_labels(spec, path=f"trajectory[{index}]")
    return spec


def _ladder_endpoint_bool(spec: Mapping[str, Any], name: str, *, default: bool = False) -> bool:
    value = spec.get(name, default)
    _require(isinstance(value, bool), f"trajectory {spec.get('trajectory_id', '?')} {name} must be boolean")
    return value


def _ladder_witness_hash(spec: Mapping[str, Any], name: str, *, fallback: Any = None) -> str:
    value = spec.get(name, fallback)
    if value is None:
        raise CapacityLadderError(f"trajectory {spec.get('trajectory_id', '?')} lacks {name}")
    return _ladder_require_sha(value, name=f"trajectory {spec.get('trajectory_id', '?')} {name}")


def _ladder_make_trajectory(
    spec: Mapping[str, Any],
    *,
    index: int,
    advance: Any,
    initial_state: Any,
    initial_state_sha256: str,
    state_profile: Any,
    budget: Mapping[str, Any],
    budget_lower: float,
    budget_upper: float,
) -> tuple[Mapping[str, Any] | None, Mapping[str, Any]]:
    trajectory_id = _ladder_identifier(spec.get("trajectory_id"), name=f"trajectory[{index}].trajectory_id")
    kind = str(spec.get("kind", "ordinary"))
    acquisition = spec.get("acquisition", kind not in {"reset", "startup", "failed", "uncommitted", "control"})
    _require(isinstance(acquisition, bool), f"trajectory {trajectory_id} acquisition flag is invalid")
    _require(not (acquisition and kind in {"reset", "startup", "failed", "uncommitted", "control"}), f"trajectory {trajectory_id} reset/startup/failed step cannot count as acquisition")
    drives = spec.get("drives", spec.get("schedule", spec.get("advance_schedule")))
    if drives is None:
        drives = ()
    _require(isinstance(drives, (tuple, list)), f"trajectory {trajectory_id} advance schedule is incomplete")
    _require(bool(drives) or not acquisition, f"trajectory {trajectory_id} acquisition has no canonical advance steps")
    current = spec.get("initial_state", initial_state)
    derived_predecessor_hash = _ladder_state_hash(current, state_profile=state_profile, name=f"trajectory {trajectory_id} initial_state")
    if "predecessor_head_sha256" in spec:
        predecessor_hash = _ladder_witness_hash(spec, "predecessor_head_sha256")
        _require(derived_predecessor_hash == predecessor_hash, f"trajectory {trajectory_id} predecessor hash does not match initial state")
    else:
        predecessor_hash = derived_predecessor_hash
    trajectory_script_hash = _hash(
        {
            "trajectory_id": trajectory_id,
            "kind": kind,
            "drives": _plain(drives),
            "predecessor_head_sha256": predecessor_hash,
        },
        "cassi.qi-flow-capacity-trajectory-script.v1",
    )
    source_value = spec.get("source_work", spec.get("source_budget_interval", budget))
    source_interval, source_lower, source_upper = _ladder_interval(source_value, name=f"trajectory {trajectory_id} source_work", unit="joule", sign="nonnegative")
    _require(str(source_interval["unit"]) in _LADDER_WORK_UNITS, f"trajectory {trajectory_id} source work unit must be joule or normalized")
    _require(source_lower >= budget_lower and source_upper <= budget_upper, f"trajectory {trajectory_id} source work exceeds the frozen budget")
    work_partition = _ladder_work_partition(spec.get("work_partition", spec.get("work_rows")), name=f"trajectory {trajectory_id} work_partition") if acquisition else MappingProxyType({})
    if acquisition:
        _ladder_work_conservation(source_interval, work_partition, name=f"trajectory {trajectory_id}", acquisition=True)
    zero_clock_hash = _ladder_witness_hash(spec, "zero_clock_transport_sha256") if acquisition else spec.get("zero_clock_transport_sha256", _hash({"trajectory_id": trajectory_id, "zero_clock": True}, "cassi.qi-flow-zero-clock-transport.v1"))
    advance_count = 0
    last_result: Any = None
    state_trace: list[torch.Tensor] = [_ladder_state_tensor(current, state_profile=state_profile, name=f"trajectory {trajectory_id} initial_state")]
    for drive in drives:
        result = _ladder_advance(advance, current, drive)
        committable, candidate, predecessor = _ladder_step(result)
        if predecessor is not None:
            current_hash = _ladder_state_hash(current, state_profile=state_profile, name=f"trajectory {trajectory_id} current")
            _require(_ladder_state_hash(predecessor, state_profile=state_profile, name=f"trajectory {trajectory_id} predecessor") == current_hash, f"trajectory {trajectory_id} predecessor chain diverged")
        _require(committable and candidate is not None, f"trajectory {trajectory_id} contains a failed or uncommittable canonical step")
        current = candidate
        state_trace.append(_ladder_state_tensor(current, state_profile=state_profile, name=f"trajectory {trajectory_id} state"))
        last_result = result
        advance_count += 1
    if not acquisition:
        return None, MappingProxyType(
            {
                "trajectory_id": trajectory_id,
                "acquisition": False,
                "advance_count": advance_count,
                "trajectory_script_sha256": trajectory_script_hash,
                "state_trace": tuple(state_trace),
            }
        )
    derived_candidate_hash = _ladder_state_hash(current, state_profile=state_profile, name=f"trajectory {trajectory_id} candidate")
    if "candidate_head_sha256" in spec:
        candidate_hash = _ladder_witness_hash(spec, "candidate_head_sha256")
        _require(candidate_hash == derived_candidate_hash, f"trajectory {trajectory_id} candidate hash does not match canonical advance output")
    else:
        candidate_hash = derived_candidate_hash
    endpoint_state = spec.get("endpoint_state", current)
    derived_endpoint_hash = _ladder_state_hash(endpoint_state, state_profile=state_profile, name=f"trajectory {trajectory_id} endpoint")
    _require(derived_endpoint_hash == derived_candidate_hash, f"trajectory {trajectory_id} endpoint state is not the canonical advanced state")
    if "endpoint_head_sha256" in spec:
        endpoint_hash = _ladder_witness_hash(spec, "endpoint_head_sha256")
        _require(endpoint_hash == derived_endpoint_hash, f"trajectory {trajectory_id} endpoint hash does not match canonical advance output")
    else:
        endpoint_hash = derived_endpoint_hash
    observable = _ladder_endpoint_bool(spec, "observable")
    usable = _ladder_endpoint_bool(spec, "usable")
    _require(not usable or observable, f"trajectory {trajectory_id} usable endpoint is not observable")
    for key in ("retained", "reusable"):
        _require(spec.get(key, False) is False, f"trajectory {trajectory_id} behavioral {key} claim is outside W6A intrinsic scope")
    witness = MappingProxyType(
        {
            "trajectory_id": trajectory_id,
            "predecessor_head_sha256": predecessor_hash,
            "candidate_head_sha256": candidate_hash,
            "endpoint_head_sha256": endpoint_hash,
            "advance_count": advance_count,
            "source_work": source_interval,
            "zero_clock_transport_sha256": zero_clock_hash,
            "work_partition": work_partition,
            "endpoint_admitted": True,
            "strict_improvement": bool(spec.get("strict_improvement", True)),
        }
    )
    return witness, MappingProxyType(
        {
            "trajectory_id": trajectory_id,
            "acquisition": True,
            "candidate_head_sha256": candidate_hash,
            "endpoint_head_sha256": endpoint_hash,
            "observable": observable,
            "usable": usable,
            "result": last_result,
            "trajectory_script_sha256": trajectory_script_hash,
            "state_trace": tuple(state_trace),
        }
    )


def build_capacity_ladder(
    *,
    advance: Any,
    initial_state: Any,
    trajectories: Any,
    initial_state_sha256: str | None = None,
    profile: Any = None,
    backend_capacity: Any = None,
    topology_profile: Any = None,
    profile_sha256: str | None = None,
    state_contract_sha256: str | None = None,
    backend_capacity_sha256: str | None = None,
    topology_codebook_sha256: str | None = None,
    topology_witnesses: Any = None,
    controller_grammar: Any = None,
    controller_grammar_sha256: str | None = None,
    physical_horizon: Any = None,
    work_budget: Any = None,
    geometric_capacity: int | None = None,
    reset_control_sha256: str | None = None,
    saturation_control_sha256: str | None = None,
    overwrite_control_sha256: str | None = None,
    washout_recovery_schedule_sha256: str | None = None,
    washout_and_recovery_schedule_sha256: str | None = None,
    reset_control: Any = None,
    saturation_control: Any = None,
    overwrite_control: Any = None,
    washout_recovery_schedule: Any = None,
    consumed_semantic_subhashes: Any = None,
    barrier_interval: Any = None,
    closure_residual: Any = None,
    state_profile: Any = None,
    analytic_source_basis: Any = None,
    analytic_readout_basis: Any = None,
    uncertainty_null_thresholds: Any = None,
) -> QiCapacityLadderReceipt:
    """Build the W6A ladder around an explicit canonical ``advance`` dependency."""
    _require(advance is not None, "canonical advance is required")
    _require(initial_state is not None, "initial state is required")
    _require(isinstance(trajectories, (tuple, list)) and trajectories, "trajectory registry is required")
    _require(profile is not None, "W6A profile identity is required")
    _require(backend_capacity is not None, "W6A backend capacity identity is required")
    _require(topology_profile is not None, "W4R topology profile identity is required")
    profile_sha256, state_contract_sha256, backend_capacity_sha256, topology_codebook_sha256 = _ladder_live_dependencies(
        profile=profile,
        backend_capacity=backend_capacity,
        topology_profile=topology_profile,
        profile_sha256=profile_sha256,
        state_contract_sha256=state_contract_sha256,
        backend_capacity_sha256=backend_capacity_sha256,
        topology_codebook_sha256=topology_codebook_sha256,
    )
    advance_identity = getattr(advance, "identity", None)
    _require(advance_identity is not None, "W6A advance must expose canonical backend identity")
    _require(_ladder_require_sha(getattr(advance_identity, "profile_sha256", None), name="advance.identity.profile_sha256") == profile_sha256, "advance backend profile identity mismatch")
    advance_capacity = getattr(advance, "capacity", None)
    _require(advance_capacity is backend_capacity or getattr(advance_capacity, "capacity_sha256", None) == backend_capacity_sha256, "advance backend capacity identity mismatch")
    state_profile = profile if state_profile is None else state_profile
    _require(state_profile is profile or _ladder_profile_hash(state_profile, "profile_sha256") == profile_sha256, "state_profile does not match profile identity")
    physical_horizon = physical_horizon if physical_horizon is not None else _ladder_profile_value(profile, "physical_horizon")
    work_budget = work_budget if work_budget is not None else _ladder_profile_value(profile, "work_budget")
    controller_grammar = controller_grammar if controller_grammar is not None else _ladder_profile_value(profile, "controller_grammar")
    geometric_capacity = geometric_capacity if geometric_capacity is not None else len(tuple(_ladder_profile_value(profile, "topology_codewords", ())))
    topology_rows = _ladder_topology_witnesses(profile, topology_witnesses, topology_hash=topology_codebook_sha256)
    derived_initial_hash = _ladder_state_hash(initial_state, state_profile=state_profile, name="initial_state")
    initial_hash = _ladder_require_sha(initial_state_sha256 or derived_initial_hash, name="ladder.initial_state_sha256")
    _require(initial_hash == derived_initial_hash, "initial state identity does not match supplied initial_state_sha256")
    controller_hash = _ladder_require_sha(controller_grammar_sha256 or _ladder_controller_hash(controller_grammar), name="ladder.controller_grammar_sha256")
    reset_hash = _ladder_control_hash(reset_control, supplied=reset_control_sha256, name="reset-control")
    saturation_hash = _ladder_control_hash(saturation_control, supplied=saturation_control_sha256, name="saturation-control")
    overwrite_hash = _ladder_control_hash(overwrite_control, supplied=overwrite_control_sha256, name="overwrite-control")
    washout_hash = _ladder_control_hash(
        washout_recovery_schedule,
        supplied=washout_recovery_schedule_sha256 or washout_and_recovery_schedule_sha256,
        name="washout-recovery",
    )
    horizon = _ladder_horizon(physical_horizon if physical_horizon is not None else _ladder_profile_value(profile, "physical_horizon"))
    budget, budget_lower, budget_upper = _ladder_work_budget(work_budget if work_budget is not None else _ladder_profile_value(profile, "work_budget"))
    _require(budget_lower >= 0.0 and budget_upper >= budget_lower, "ladder work budget must be finite and nonnegative")
    thresholds = _ladder_thresholds(uncertainty_null_thresholds, name="uncertainty_null_thresholds")
    initial_tensor = _ladder_state_tensor(initial_state, state_profile=state_profile, name="initial_state")
    source_basis, source_descriptor = _ladder_basis(analytic_source_basis, dimension=int(initial_tensor.numel()), name="analytic_source_basis")
    readout_basis, readout_descriptor = _ladder_basis(analytic_readout_basis, dimension=int(initial_tensor.numel()), name="analytic_readout_basis")
    _require(geometric_capacity is not None, "geometric capacity is required")
    geometric = _int("geometric capacity", geometric_capacity, minimum=0)
    _require(geometric <= 1048576, "geometric capacity exceeds schema bound")
    initial_state_hash = initial_hash
    witnesses: list[Mapping[str, Any]] = []
    metadata: list[Mapping[str, Any]] = []
    traces: list[tuple[torch.Tensor, ...]] = []
    trajectory_script_hashes: dict[str, str] = {}
    seen_trajectory_ids: set[str] = set()
    for index, raw_spec in enumerate(trajectories):
        spec = _ladder_trajectory_spec(raw_spec, index=index)
        trajectory_id = _ladder_identifier(spec.get("trajectory_id"), name=f"trajectory[{index}].trajectory_id")
        _require(trajectory_id not in seen_trajectory_ids, f"trajectory id {trajectory_id} is duplicated")
        seen_trajectory_ids.add(trajectory_id)
        witness, meta = _ladder_make_trajectory(
            spec,
            index=index,
            advance=advance,
            initial_state=initial_state,
            initial_state_sha256=initial_state_hash,
            state_profile=state_profile,
            budget=budget,
            budget_lower=budget_lower,
            budget_upper=budget_upper,
        )
        if witness is not None:
            witnesses.append(witness)
        metadata.append(meta)
        trajectory_script_hashes[trajectory_id] = _ladder_require_sha(meta["trajectory_script_sha256"], name=f"trajectory {trajectory_id} script")
        if meta.get("acquisition"):
            traces.append(tuple(meta["state_trace"]))
    _require(witnesses, "no ordinary canonical acquisition trajectory was admitted")
    candidate_hashes: set[str] = set()
    for witness in witnesses:
        candidate = str(witness["candidate_head_sha256"])
        strict = bool(witness["strict_improvement"])
        _require(strict == (candidate not in candidate_hashes), f"trajectory {witness['trajectory_id']} strict-improvement witness is inconsistent")
        candidate_hashes.add(candidate)
    reachable = len(candidate_hashes)
    _require(reachable <= geometric, "reachable capacity exceeds geometric capacity")
    by_candidate: dict[str, list[Mapping[str, Any]]] = {}
    for witness, meta in zip(witnesses, (item for item in metadata if item.get("acquisition"))):
        by_candidate.setdefault(str(meta["candidate_head_sha256"]), []).append(meta)
    endpoint_candidates: dict[str, set[str]] = {}
    for candidate, rows in by_candidate.items():
        for row in rows:
            if bool(row["observable"]):
                endpoint_candidates.setdefault(str(row["endpoint_head_sha256"]), set()).add(candidate)
    observable_candidates = {
        candidate
        for candidate, rows in by_candidate.items()
        if any(bool(row["observable"]) and len(endpoint_candidates.get(str(row["endpoint_head_sha256"]), set())) == 1 for row in rows)
    }
    usable_candidates = {
        candidate
        for candidate, rows in by_candidate.items()
        if candidate in observable_candidates and any(bool(row["usable"]) for row in rows)
    }
    levels = {
        "geometric": geometric,
        "reachable": reachable,
        "observable": len(observable_candidates),
        "usable": len(usable_candidates),
        "retained": 0,
        "reusable": 0,
    }
    interval_map = {
        level: MappingProxyType(
            {
                "lower": finite_bits(float(count)),
                "upper": finite_bits(float(count)),
                "uncertainty_radius": finite_bits(0.0),
                "unit": "item",
            }
        )
        for level, count in levels.items()
    }
    trajectory_ids = tuple(_ladder_identifier(spec.get("trajectory_id"), name="trajectory id") for spec in trajectories)
    _require(set(trajectory_script_hashes) == set(trajectory_ids), "trajectory script registry is incomplete")
    metrics = _ladder_metric_measurements(
        traces=tuple(traces),
        initial_tensor=initial_tensor,
        source_basis=source_basis,
        readout_basis=readout_basis,
        source_descriptor=source_descriptor,
        readout_descriptor=readout_descriptor,
        thresholds=thresholds,
        horizon=horizon,
        backend_capacity=backend_capacity,
    )
    diagnostics_payload = _ladder_diagnostics_payload(
        analytic_source_basis=metrics["analytic_source_basis"],
        analytic_readout_basis=metrics["analytic_readout_basis"],
        impulse_responses=metrics["impulse_responses"],
        coordinate_reachability_observability=metrics["coordinate_reachability_observability"],
        delay_growth_retention_discrimination=metrics["delay_growth_retention_discrimination"],
        uncertainty_null_thresholds=thresholds,
        state_workspace_bytes=metrics["state_workspace_bytes"],
    )
    diagnostics_identity = _hash(diagnostics_payload, "cassi.qi-flow-capacity-diagnostics.v1")
    trajectory_set_hash = _hash(
        {
            "trajectory_ids": list(trajectory_ids),
            "trajectory_script_hashes": dict(sorted(trajectory_script_hashes.items())),
            "diagnostics_sha256": diagnostics_identity,
        },
        "cassi.qi-flow-capacity-trajectory-set.v1",
    )
    minimum_source = min(
        (_ladder_finite(item["source_work"]["lower"], name="source work lower") for item in witnesses),
        default=budget_lower,
    )
    eligibility_without_hash = {
        "minimum_source_work_lower_bound": finite_bits(minimum_source),
        "ordinary_step_required": True,
        "reset_counted_as_acquisition": False,
        "reset_excluded": True,
        "successful_reproduction_required": True,
        "zero_clock_transition_excluded": True,
    }
    eligibility = dict(eligibility_without_hash)
    eligibility["eligibility_sha256"] = _hash(eligibility_without_hash, "cassi.qi-flow-capacity-acquisition-eligibility.v1")
    consumed = consumed_semantic_subhashes
    if consumed is None:
        consumed = (
            {"name": "state_contract_sha256", "sha256": state_contract_sha256},
            {"name": "backend_capacity_sha256", "sha256": backend_capacity_sha256},
        )
    _require(isinstance(consumed, (tuple, list)), "consumed semantic subhashes must be a sequence")
    consumed_rows_list = []
    for item in consumed:
        _require(isinstance(item, Mapping), "consumed subhash row is invalid")
        _require(item.get("name") in _LADDER_SUBHASH_NAMES, "consumed subhash name is not canonical")
        consumed_rows_list.append(MappingProxyType({"name": _text("consumed subhash name", item.get("name")), "sha256": _ladder_require_sha(item.get("sha256"), name="consumed subhash")}))
    consumed_rows = tuple(consumed_rows_list)
    _require(len(consumed_rows) == len(consumed), "consumed semantic subhash row is invalid")
    barrier = _ladder_canonical_interval(barrier_interval if barrier_interval is not None else {"lower": _ladder_horizon_seconds(horizon), "upper": _ladder_horizon_seconds(horizon), "unit": horizon["unit"]}, name="barrier_interval")
    residual = _ladder_canonical_interval(closure_residual if closure_residual is not None else 0.0, name="closure_residual", require_nonnegative=False)
    return QiCapacityLadderReceipt(
        profile_sha256=profile_sha256,
        state_contract_sha256=state_contract_sha256,
        backend_capacity_sha256=backend_capacity_sha256,
        initial_state_sha256=initial_state_hash,
        controller_grammar_sha256=controller_hash,
        physical_horizon=horizon,
        trajectory_set_sha256=trajectory_set_hash,
        trajectory_ids=trajectory_ids,
        work_budget=budget,
        capacity_levels=levels,
        capacity_intervals=interval_map,
        reachability_witnesses=tuple(witnesses),
        reset_control_sha256=reset_hash,
        saturation_control_sha256=saturation_hash,
        overwrite_control_sha256=overwrite_hash,
        washout_recovery_schedule_sha256=washout_hash,
        consumed_semantic_subhashes=consumed_rows,
        topology_codebook_sha256=topology_codebook_sha256,
        topology_witnesses=topology_rows,
        acquisition_eligibility=eligibility,
        barrier_interval=barrier,
        closure_residual=residual,
        analytic_source_basis=metrics["analytic_source_basis"],
        analytic_readout_basis=metrics["analytic_readout_basis"],
        impulse_responses=metrics["impulse_responses"],
        coordinate_reachability_observability=metrics["coordinate_reachability_observability"],
        delay_growth_retention_discrimination=metrics["delay_growth_retention_discrimination"],
        uncertainty_null_thresholds=thresholds,
        state_workspace_bytes=metrics["state_workspace_bytes"],
        trajectory_script_hashes=MappingProxyType(dict(trajectory_script_hashes)),
        control_hashes=MappingProxyType(
            {
                "reset": reset_hash,
                "saturation": saturation_hash,
                "overwrite": overwrite_hash,
                "washout_recovery": washout_hash,
            }
        ),
    )


build_intrinsic_capacity_ladder = build_capacity_ladder
materialize_capacity_ladder = build_capacity_ladder
build_capacity_ladder_receipt = build_capacity_ladder
build_qi_capacity_ladder = build_capacity_ladder
materialize_qi_capacity_ladder = build_capacity_ladder
QiIntrinsicCapacityLadderReceipt = QiCapacityLadderReceipt


def validate_capacity_ladder(receipt: QiCapacityLadderReceipt) -> None:
    _require(isinstance(receipt, QiCapacityLadderReceipt), "not a capacity ladder receipt")
    _require(_hash(receipt.payload(), CAPACITY_LADDER_DOMAIN) == receipt.self_sha256, "capacity ladder receipt hash mismatch")
    _ladder_require_sha(receipt.reset_control_sha256, name="reset_control_sha256")
    _ladder_require_sha(receipt.saturation_control_sha256, name="saturation_control_sha256")
    _ladder_require_sha(receipt.overwrite_control_sha256, name="overwrite_control_sha256")
    _ladder_require_sha(receipt.washout_recovery_schedule_sha256, name="washout_recovery_schedule_sha256")
    expected_controls = {
        "reset": receipt.reset_control_sha256,
        "saturation": receipt.saturation_control_sha256,
        "overwrite": receipt.overwrite_control_sha256,
        "washout_recovery": receipt.washout_recovery_schedule_sha256,
    }
    _require(dict(receipt.control_hashes) == expected_controls, "capacity control hash registry diverged")
    _require(len(set(expected_controls.values())) == len(expected_controls), "capacity controls are not independent")
    _ladder_thresholds(receipt.uncertainty_null_thresholds, name="uncertainty_null_thresholds")
    diagnostics_identity = receipt.diagnostics_sha256
    expected_trajectory_set = _hash(
        {
            "trajectory_ids": list(receipt.trajectory_ids),
            "trajectory_script_hashes": dict(sorted(receipt.trajectory_script_hashes.items())),
            "diagnostics_sha256": diagnostics_identity,
        },
        "cassi.qi-flow-capacity-trajectory-set.v1",
    )
    _require(receipt.trajectory_set_sha256 == expected_trajectory_set, "capacity trajectory-set identity mismatch")
    _require(set(receipt.trajectory_script_hashes) == set(receipt.trajectory_ids), "capacity trajectory script registry is incomplete")
    for witness in receipt.reachability_witnesses:
        _ladder_work_conservation(
            witness["source_work"],
            witness["work_partition"],
            name=f"trajectory {witness['trajectory_id']}",
            acquisition=True,
        )
    _require(receipt.delay_growth_retention_discrimination.get("retained_claim") is False and receipt.delay_growth_retention_discrimination.get("reusable_claim") is False, "W6A behavioral claims are not disabled")


validate_capacity_ladder_receipt = validate_capacity_ladder
validate_qi_capacity_ladder = validate_capacity_ladder


__all__.extend(
    [
        "CAPACITY_LADDER_SCHEMA",
        "CAPACITY_LADDER_LEVELS",
        "CapacityLadderError",
        "QiCapacityLadderError",
        "QiCapacityLadderReceipt",
        "build_qi_capacity_ladder",
        "materialize_qi_capacity_ladder",
        "validate_qi_capacity_ladder",
        "QiIntrinsicCapacityLadderReceipt",
        "build_capacity_ladder",
        "build_intrinsic_capacity_ladder",
        "materialize_capacity_ladder",
        "build_capacity_ladder_receipt",
        "validate_capacity_ladder",
        "validate_capacity_ladder_receipt",
    ]
)
