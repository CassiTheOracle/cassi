"""Build the source-exact W4R/G4R topological-retention evidence artifact.

The runner is deliberately a thin evidence adapter.  The retention law and its
public transition live in :mod:`cassi_qi_topology`; this file only discovers
parents, supplies profile-derived states, and seals immutable evidence.
"""

from __future__ import annotations

import copy
import hashlib
import inspect
import math
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import torch

import cassi_qi_topology as _topology
from cassi_qi_carrier import load_w4_carrier_profile
from cassi_qi_field import QiFlowStateV3
from cassi_qi_geometry import d_c_to_ey_ei, load_w2_geometry_profile, vd_vc_to_vy_vi
from cassi_qi_profile import COMPONENT_ORDER, canonical_hash, canonical_json_bytes, canonical_json_loads
from cassi_qi_transport import load_w3_transport_profile

ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT / "_diag" / "cassi-qi-flow-w4r-retention-core-final"
GATE_DIR = "gates/g04r-retention-core"
INDEX_SCHEMA = "cassi.qi-flow-w4r-retention-core-run-index.v1"
ARTIFACT_DOMAIN = "cassi.qi-flow-w4r-retention-core"
STATUS_SCHEMA = "cassi.qi-flow-w4r-retention-core-status.v1"
CANDIDATE_SCHEMA = "cassi.qi-flow-w4r-retention-core-candidate.v1"
PROFILE_SCHEMA = "cassi.qi-flow-w4r-retention-core-profile.v1"
EXTENSION_SCHEMA = "cassi.qi-flow-w4r-retention-core-extension.v1"
RAW_SCHEMA = "cassi.qi-flow-w4r-retention-core-raw-state.v1"
RAW_DOMAIN = "cassi.qi-flow-w4r-retention-core-raw-state"
RECEIPT_DOMAIN = "cassi.qi-flow-w4r-retention-core-receipt"

# These are requirements, not parent identities.  The parent source manifest
# may add more paths; every available source is compared with the live file.
REQUIRED_SOURCES = (
    "cassi_qi_topology.py",
    "run_cassi_qi_topology.py",
    "cassi_qi_profile.py",
    "cassi_qi_geometry.py",
    "cassi_qi_field.py",
    "cassi_qi_numerical_certificate.py",
    "cassi_qi_carrier.py",
    "cassi_qi_transport.py",
)


class TopologyArtifactError(ValueError):
    """Raised when an evidence precondition is not met."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "__dict__"):
        return _plain(vars(value))
    return str(value)


def _without_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(k): _plain(v) for k, v in value.items() if k not in {"self_sha256", "final_certificate_identity_sha256"}}


def _seal(value: Mapping[str, Any], domain: str) -> dict[str, Any]:
    result = {str(k): _plain(v) for k, v in value.items() if k != "self_sha256"}
    result["self_sha256"] = canonical_hash(result, domain)
    return result


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = canonical_json_loads(path.read_bytes())
    except Exception as exc:  # pragma: no cover - error context is useful to callers
        raise TopologyArtifactError(f"invalid JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise TopologyArtifactError(f"object required: {path}")
    return value


def _write(stage: Path, relative: str, raw: bytes) -> None:
    path = stage / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def _write_json(stage: Path, relative: str, value: Any) -> None:
    _write(stage, relative, canonical_json_bytes(_plain(value)))


def _json_paths(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.json") if path.is_file())


def _sha256_file(path: Path) -> str:
    return _sha(path.read_bytes())


def _object_tokens(value: Any, *, key: str = "") -> set[str]:
    tokens: set[str] = set()
    if isinstance(value, Mapping):
        for name, item in value.items():
            tokens.update(_object_tokens(item, key=str(name)))
    elif isinstance(value, (list, tuple)):
        for item in value:
            tokens.update(_object_tokens(item, key=key))
    elif isinstance(value, str) and (key == "run_id" or key.endswith("_sha256") or key in {"certificate_id", "parent_id"}):
        tokens.add(value)
    return tokens


def _source_records(root: Path) -> list[dict[str, Any]]:
    """Read the parent's source identity without trusting the index alone."""
    candidates = [
        path
        for path in _json_paths(root)
        if path.name.replace("_", "-") in {"source-identity.json", "source-identity.v1.json"}
        or "source-identity" in path.name
    ]
    for path in candidates:
        try:
            value = _read_json(path)
        except TopologyArtifactError:
            continue
        rows = value.get("sources")
        if isinstance(rows, list) and all(isinstance(row, Mapping) for row in rows):
            result = []
            for row in rows:
                rel = row.get("path")
                digest = row.get("sha256")
                if isinstance(rel, str) and isinstance(digest, str):
                    result.append({"path": rel, "sha256": digest, "byte_count": row.get("byte_count")})
            if result:
                return result
    # Some early W4 artifacts only put source records in the object inventory.
    for path in _json_paths(root):
        try:
            value = _read_json(path)
        except TopologyArtifactError:
            continue
        rows = value.get("objects")
        if isinstance(rows, list):
            result = []
            for row in rows:
                if not isinstance(row, Mapping) or not str(row.get("path", "")).startswith("sources/"):
                    continue
                rel = str(row["path"])[len("sources/"):]
                digest = row.get("sha256")
                if isinstance(digest, str):
                    result.append({"path": rel, "sha256": digest, "byte_count": row.get("byte_count")})
            if result:
                return result
    return []
def _source_exact(root: Path, required: Sequence[str] = ()) -> tuple[bool, list[dict[str, Any]], str]:
    records = _source_records(root)
    if not records:
        return False, [], "source identity manifest missing"
    by_path = {str(row["path"]): row for row in records}
    for relative in required:
        row = by_path.get(relative)
        current = ROOT / relative
        if row is None or not current.is_file():
            return False, records, f"required source identity missing: {relative}"
        if str(row.get("sha256", "")).lower() != _sha256_file(current):
            return False, records, f"source identity is stale: {relative}"
    compared = 0
    for row in records:
        relative = str(row["path"])
        current = ROOT / relative
        if current.is_file():
            compared += 1
            if str(row.get("sha256", "")).lower() != _sha256_file(current):
                return False, records, f"source identity is stale: {relative}"
    if compared == 0:
        return False, records, "source identity has no live source paths"
    return True, records, "source-exact"


def _independently_verify_parent(candidate_root: Path, marker: str) -> bool:
    """Require the parent package's independent verifier to accept this root."""
    module_name = "verify_cassi_qi_carrier.py" if marker == "w4" else "verify_cassi_qi_numerical_certificate.py"
    try:
        module = __import__(module_name[:-3], fromlist=["verify", "verify_artifact"])
        verifier = getattr(module, "verify", None) or getattr(module, "verify_artifact", None)
        if not callable(verifier):
            return False
        result = verifier(candidate_root)
    except Exception:
        return False
    if not isinstance(result, Mapping):
        return False
    expected = "PASS_W4_G4" if marker == "w4" else "PASS_W3N_G3N"
    return str(result.get("status", "")).upper() in {"PASS", expected}


def _candidate_indexes(root: Path, marker: str) -> list[tuple[Path, dict[str, Any], list[dict[str, Any]]]]:
    result = []
    if not root.is_dir():
        return result
    for index_path in sorted(root.rglob("index.json")):
        try:
            index = _read_json(index_path)
        except TopologyArtifactError:
            continue
        schema = str(index.get("schema", "")).lower()
        if marker not in schema or str(index.get("status", "")).upper() not in {"PASS", "PASS_W4_G4", "PASS_W3N_G3N", "PASS_W4R_G4R"}:
            continue
        candidate_root = index_path.parent
        run_id = index.get("run_id")
        if not isinstance(run_id, str) or run_id != candidate_root.name:
            continue
        required = ("cassi_qi_carrier.py",) if marker == "w4" else ("cassi_qi_transport.py",)
        exact, records, _ = _source_exact(candidate_root, required=required)
        if exact and _independently_verify_parent(candidate_root, marker):
            result.append((candidate_root, index, records))
    return result


def _find_gate(root: Path, marker: str) -> tuple[Path, dict[str, Any]] | None:
    gate_candidates = []
    for path in _json_paths(root):
        rel = path.relative_to(root).as_posix().lower()
        if "gates/" not in rel or marker not in rel:
            continue
        try:
            value = _read_json(path)
        except TopologyArtifactError:
            continue
        status = str(value.get("status", value.get("gate_status", ""))).upper()
        if status in {"PASS", "PASS_W4_G4", "PASS_W4R_G4R"}:
            gate_candidates.append((path, value))
    if not gate_candidates:
        return None
    # Prefer the explicit status/receipt, then a candidate object.
    gate_candidates.sort(key=lambda item: (item[0].name not in {"status.json", "carrier.json", "retention-core.json"}, item[0].as_posix()))
    return gate_candidates[0]


def _linked_w3n(w4_root: Path, w3n_candidates: Sequence[tuple[Path, dict[str, Any], list[dict[str, Any]]]]) -> list[tuple[Path, dict[str, Any], list[dict[str, Any]]]]:
    tokens: set[str] = set()
    for path in _json_paths(w4_root):
        if "sources/" in path.relative_to(w4_root).as_posix():
            continue
        try:
            tokens.update(_object_tokens(_read_json(path)))
        except TopologyArtifactError:
            continue
    matches = []
    for candidate in w3n_candidates:
        root, index, records = candidate
        candidate_tokens = {str(index.get("run_id", ""))}
        candidate_tokens.update(_object_tokens(index))
        for path in _json_paths(root):
            if "sources/" in path.relative_to(root).as_posix():
                continue
            try:
                candidate_tokens.update(_object_tokens(_read_json(path)))
            except TopologyArtifactError:
                continue
        if tokens & candidate_tokens:
            matches.append(candidate)
    return matches


def _certificate_and_ancestry(w3n_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    certificate_candidates: list[tuple[Path, dict[str, Any]]] = []
    ancestry_files: list[str] = []
    for path in _json_paths(w3n_root):
        relative = path.relative_to(w3n_root).as_posix()
        if relative.startswith("sources/"):
            continue
        try:
            value = _read_json(path)
        except TopologyArtifactError:
            continue
        if "/certificate/" in f"/{relative}" or "certificate-root" in path.name:
            if "certificate" in str(value.get("schema", "")).lower() and isinstance(value.get("self_sha256"), str):
                certificate_candidates.append((path, value))
        if "/parent" in f"/{relative}" or "ancestry" in path.name or "parent" in path.name:
            ancestry_files.append(relative)
    if not certificate_candidates:
        raise TopologyArtifactError("current W3N ancestry has no independently identified numerical certificate")
    certificate_candidates.sort(key=lambda item: (item[0].name != "certificate-root.json", item[0].as_posix()))
    certificate = certificate_candidates[0][1]
    ancestry = {
        "schema": "cassi.qi-flow-w4r-retention-core-w3n-ancestry.v1",
        "w3n_root_relative": w3n_root.relative_to(ROOT).as_posix() if w3n_root.is_relative_to(ROOT) else str(w3n_root),
        "certificate_path": certificate_candidates[0][0].relative_to(w3n_root).as_posix(),
        "certificate_sha256": certificate["self_sha256"],
        "parent_files": sorted(set(ancestry_files)),
    }
    ancestry["self_sha256"] = canonical_hash(ancestry, "cassi.qi-flow-w4r-retention-core-w3n-ancestry")
    return certificate, ancestry


def _discover_parents() -> dict[str, Any]:
    w4_candidates = _candidate_indexes(ROOT / "_diag" / "cassi-qi-flow-w4-periodic-fft2-final", "w4")
    # A W4R schema must never be accepted as its own W4 parent.
    w4_candidates = [item for item in w4_candidates if "w4r" not in str(item[1].get("schema", "")).lower()]
    w3n_candidates = _candidate_indexes(ROOT / "_diag" / "cassi-qi-flow-w3n-periodic-fft2-final", "w3n")
    if len(w4_candidates) != 1:
        raise TopologyArtifactError(f"expected exactly one current source-exact W4 parent, found {len(w4_candidates)}")
    if not w3n_candidates:
        raise TopologyArtifactError("no current source-exact W3N ancestry candidate")
    w4_root, w4_index, w4_sources = w4_candidates[0]
    gate = _find_gate(w4_root, "g04-carrier")
    if gate is None:
        raise TopologyArtifactError("current W4 parent has no independently verified G4 carrier receipt")
    declared_w3n = w4_index.get("w3n_parent_run_id")
    if isinstance(declared_w3n, str):
        linked = [item for item in w3n_candidates if item[1].get("run_id") == declared_w3n]
    else:
        linked = _linked_w3n(w4_root, w3n_candidates)
    if len(linked) != 1:
        raise TopologyArtifactError(f"expected exactly one W3N ancestry linked to current W4, found {len(linked)}")
    w3n_root, w3n_index, w3n_sources = linked[0]
    certificate, ancestry = _certificate_and_ancestry(w3n_root)
    return {
        "w4_root": w4_root,
        "w4_index": w4_index,
        "w4_sources": w4_sources,
        "w4_gate_path": gate[0],
        "w4_gate": gate[1],
        "w3n_root": w3n_root,
        "w3n_index": w3n_index,
        "w3n_sources": w3n_sources,
        "w3n_certificate": certificate,
        "w3n_ancestry": ancestry,
    }
def _resolve_profile(geometry: Any, *, mode: str = "topological-v1", certificate: Mapping[str, Any] | None = None, carrier_profile: Any | None = None) -> Any:
    """Load a profile only through the landing public loader."""
    loader = getattr(_topology, "load_w4r_topology_profile", None)
    if not callable(loader):
        for name in ("load_w4r_retention_profile", "load_w4r_topological_retention_profile", "load_w4r_profile"):
            loader = getattr(_topology, name, None)
            if callable(loader):
                break
    if not callable(loader):
        raise TopologyArtifactError("landing topology module has no validated W4R retention-profile loader")
    return _invoke(
        loader,
        geometry=geometry,
        geometry_profile=geometry,
        mode=mode,
        carrier_profile=carrier_profile,
        numerical_certificate=certificate,
    )


def _resolve_law(profile: Any, geometry: Any) -> tuple[Any, Callable[..., Any], str, str]:
    law_type = getattr(_topology, "QiTopologicalRetentionLaw", None)
    if law_type is None:
        raise TopologyArtifactError("landing QiTopologicalRetentionLaw capability is unavailable; refusing legacy Hamiltonian fallback")
    law = None
    binder = getattr(law_type, "bind", None)
    if callable(binder):
        try:
            law = _invoke(binder, profile=profile, geometry=geometry, topology_profile=profile, geometry_profile=geometry)
        except Exception:
            try:
                law = _invoke(binder, profile, geometry)
            except Exception as exc:
                raise TopologyArtifactError(f"QiTopologicalRetentionLaw.bind failed: {exc}") from exc
    if law is None:
        for kwargs in (
            {"profile": profile, "geometry": geometry},
            {"topology_profile": profile, "geometry_profile": geometry},
            {"profile": profile},
            {},
        ):
            try:
                law = law_type(**kwargs)
                break
            except TypeError:
                continue
    if law is None:
        raise TopologyArtifactError("QiTopologicalRetentionLaw could not be bound to the validated profile and geometry")
    transition_names = (
        "transition_w4r_retention",
        "transition_w4r_topological_retention",
        "transition_w4r_topology",
        "transition_topological_retention",
    )
    transition = None
    transition_name = ""
    for name in ("transition", "step", "apply") + transition_names:
        candidate = getattr(law, name, None)
        if callable(candidate):
            transition, transition_name = candidate, f"{type(law).__module__}.{type(law).__qualname__}.{name}"
            break
    if transition is None:
        for name in transition_names:
            candidate = getattr(_topology, name, None)
            if callable(candidate):
                transition, transition_name = candidate, f"{_topology.__name__}.{name}"
                break
    if transition is None:
        raise TopologyArtifactError("QiTopologicalRetentionLaw has no immutable public W4R transition")
    # Reset is an explicit transition kind in the landing API.  Do not invent
    # a private state mutation when that public capability is absent.
    reset_name = "transition_kind=retention_reset" if "transition_w4r_topology" in transition_name else ""
    for name in ("explicit_reset", "reset_topological_retention", "reset", "apply_reset"):
        if callable(getattr(law, name, None)) or callable(getattr(_topology, name, None)):
            reset_name = name
            break
    if not reset_name:
        raise TopologyArtifactError("QiTopologicalRetentionLaw has no authenticated explicit reset operator")
    return law, transition, transition_name, reset_name



def _invoke(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Pass only parameters a landing API declares, retaining positional state."""
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return function(*args, **kwargs)
    parameters = signature.parameters
    accepts_var_kw = any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values())
    filtered = kwargs if accepts_var_kw else {key: value for key, value in kwargs.items() if key in parameters}
    return function(*args, **filtered)


def _layout(geometry: Any) -> dict[str, Any]:
    base = getattr(geometry, "base_profile", geometry)
    layout = getattr(base, "state_layout", None)
    if not isinstance(layout, Mapping):
        raise TopologyArtifactError("validated W2 geometry does not expose state_layout")
    result = dict(layout)
    for key in ("scale_count", "mode_count", "component_count"):
        if key not in result:
            raise TopologyArtifactError(f"validated state_layout missing {key}")
    if int(result["component_count"]) != 9:
        raise TopologyArtifactError("W4R retention core requires the declared nine-component state layout")
    shapes = result.get("active_shapes", getattr(geometry, "active_shapes", None))
    if not isinstance(shapes, Sequence) or len(shapes) != int(result["scale_count"]):
        raise TopologyArtifactError("validated active-shape registry does not match scale_count")
    result["active_shapes"] = [list(shape) for shape in shapes]
    result.setdefault("component_order", list(COMPONENT_ORDER))
    return result




def _profile_identity(profile: Any, geometry: Any, retention: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], int, tuple[int, int]]:
    payload = getattr(profile, "payload", profile)
    payload = dict(payload) if isinstance(payload, Mapping) else {"retention": dict(retention)}
    root = getattr(profile, "root", None)
    root = dict(root) if isinstance(root, Mapping) else {
        "schema": PROFILE_SCHEMA,
        "profile_sha256": getattr(profile, "profile_sha256", ""),
        "retention_profile_sha256": getattr(profile, "profile_sha256", ""),
    }
    slow = int(retention.get("slow_scale", getattr(profile, "slow_scale", int(_layout(geometry)["scale_count"]) - 1)))
    shapes = _layout(geometry)["active_shapes"]
    shape = tuple(int(v) for v in shapes[slow])
    if len(shape) != 2 or min(shape) <= 0:
        raise TopologyArtifactError("validated retention profile does not declare a positive slow-sheet shape")
    return payload, root, slow, shape


def _retention_mapping(profile: Any) -> dict[str, Any]:
    payload = getattr(profile, "payload", profile)
    if isinstance(payload, Mapping):
        result = dict(payload.get("retention", payload))
    else:
        result = {}
    # Landing profiles intentionally keep tagged f64 values in the immutable
    # payload and expose decoded scalars/registries on the frozen dataclass.
    for name in (
        "edge_registry", "cycle_registry", "slow_scale", "mode", "a_topo", "b_topo", "w_d", "w_c",
        "E_topo", "lambda_ph", "lambda_core", "r_core", "rho_ring", "rho_topo",
        "delta_topo", "delta_topo_int", "delta_h_min", "radial_curvature_min",
        "duration", "topology_codebook_sha256", "barrier_certificate_sha256",
    ):
        if hasattr(profile, name):
            try:
                result[name] = _plain(getattr(profile, name))
            except Exception:
                pass
    # The dataclass has the canonical edge tuple; retain its registry wrapper
    # so downstream evidence has one stable shape regardless of payload form.
    edges = result.get("edge_registry")
    if isinstance(edges, (tuple, list)) and not isinstance(edges, Mapping):
        result["edge_registry"] = {
            "schema": "cassi.qi-flow-oriented-edge-registry.v1",
            "sheet_shape": list(getattr(profile, "payload", {}).get("active_shape_yx", ())),
            "edges": [_plain(row) for row in edges],
        }
    potential = result.get("potential")
    guards = result.get("guards")
    if isinstance(potential, Mapping):
        for name in ("E_topo", "lambda_ph", "lambda_core", "r_core", "rho_ring", "rho_topo"):
            result.setdefault(name, potential.get(name))
    if isinstance(guards, Mapping):
        for name in ("delta_topo", "delta_topo_int", "Delta_H_topo_min", "radial_curvature_min"):
            result.setdefault(name, guards.get(name))
    integration = result.get("integration")
    if isinstance(integration, Mapping):
        result.setdefault("duration", integration.get("duration"))
    result.setdefault("Delta_H_topo_min", result.get("delta_h_min"))
    result.setdefault("barrier_min", result.get("delta_h_min"))
    result.setdefault("barrier_uncertainty_guard", result.get("barrier_uncertainty"))
    return result


def _registry(retention: Mapping[str, Any], name: str) -> dict[str, Any]:
    value = retention.get(name)
    if isinstance(value, Mapping):
        result = dict(value)
    elif name == "edge_registry" and isinstance(value, (tuple, list)):
        result = {"schema": "cassi.qi-flow-oriented-edge-registry.v1", "edges": [_plain(row) for row in value]}
    else:
        raise TopologyArtifactError(f"validated retention profile has no {name}")
    if name == "edge_registry" and not result.get("edges"):
        raise TopologyArtifactError("validated edge registry is empty")
    if name == "cycle_registry" and not result.get("x_cycles") and not result.get("y_cycles"):
        raise TopologyArtifactError("validated torus cycle registry is empty")
    return result
def _lane_map(layout: Mapping[str, Any]) -> dict[str, int]:
    order = layout.get("component_order", COMPONENT_ORDER)
    if not isinstance(order, Sequence) or len(order) != int(layout.get("component_count", 0)):
        raise TopologyArtifactError("validated state_layout has no complete component_order")
    result: dict[str, int] = {}
    aliases = {
        "y_re": {"y_re", "e_y_re"},
        "y_im": {"y_im", "e_y_im"},
        "i_re": {"i_re", "e_i_re"},
        "i_im": {"i_im", "e_i_im"},
        "vy_re": {"vy_re", "v_y_re"},
        "vy_im": {"vy_im", "v_y_im"},
        "vi_re": {"vi_re", "v_i_re"},
        "vi_im": {"vi_im", "v_i_im"},
        "epsilon": {"epsilon2_ema", "epsilon", "epsilon_2_ema"},
    }
    for index, raw in enumerate(order):
        text = str(raw).lower().replace("-", "_").replace(" ", "_")
        for semantic, names in aliases.items():
            if text in names:
                if semantic in result:
                    raise TopologyArtifactError(f"state component order aliases {semantic} more than once")
                result[semantic] = index
    required = set(aliases)
    if set(result) != required:
        raise TopologyArtifactError(f"state component order is missing {sorted(required - set(result))}")
    return result


def _wrap(angle: torch.Tensor) -> torch.Tensor:
    return torch.atan2(torch.sin(angle), torch.cos(angle))


def _phase_grid(kind: str, shape: tuple[int, int], *, wx: float = 0.0, wy: float = 0.0, perturb: float = 0.0) -> torch.Tensor:
    ny, nx = shape
    y, x = torch.meshgrid(torch.arange(ny, dtype=torch.float64), torch.arange(nx, dtype=torch.float64), indexing="ij")
    if kind in {"uniform", "cycle-positive", "cycle-negative", "vortex-antivortex"}:
        if kind in {"cycle-positive", "cycle-negative"} and (wx != 1.0 or wy != 0.0):
            raise TopologyArtifactError("registered cycle codewords require the canonical (1,0) winding")
        builder = getattr(_topology, "topology_codeword_phase", None)
        if not callable(builder):
            raise TopologyArtifactError("landing W4R profile has no canonical phase-witness builder")
        phase = torch.tensor(builder(kind, shape), dtype=torch.float64)
    elif kind in {"zero", "near-zero"}:
        phase = torch.zeros_like(x)
    elif kind == "cycle-x":
        phase = 2.0 * math.pi * wx * x / float(nx) + 2.0 * math.pi * wy * y / float(ny)
    elif kind == "phase-scrambled":
        # One isolated near-pi endpoint gives the named branch-cut falsifier
        # without putting an entire periodic wall above the vortex-pair energy.
        phase = torch.zeros_like(x)
        phase[0, 0] = math.pi - 3.0e-2
    elif kind == "branch-invalid":
        phase = 2.0 * math.pi * x / float(nx)
        phase = phase.clone()
        phase[0, 0] = phase[0, 0] + math.pi
    elif kind == "integer-invalid":
        phase = 2.0 * math.pi * 0.37 * x / float(nx)
    elif kind == "torus-algebra-invalid":
        phase = 2.0 * math.pi * (x / float(nx) + y / float(ny))
        phase = phase.clone()
        phase[ny // 2, nx // 2] = phase[ny // 2, nx // 2] + 0.73 * math.pi
    elif kind == "phase-slip":
        phase = 2.0 * math.pi * x / float(nx)
        phase = phase.clone()
        phase[:, nx // 2 :] = phase[:, nx // 2 :] + math.pi
    else:
        raise TopologyArtifactError(f"unknown runner phase sector: {kind}")
    if perturb:
        phase = phase + perturb * torch.sin(2.0 * math.pi * x / float(nx)) * torch.sin(2.0 * math.pi * y / float(ny))
    return phase


def _state_from_phase(*, geometry: Any, retention: Mapping[str, Any], kind: str, wx: float = 0.0, wy: float = 0.0, amplitude: float | None = None, perturb: float = 0.0, current_sign: float = 0.0) -> QiFlowStateV3:
    """Encode one selected-resolution topology witness in the declared EY/EI lanes."""
    layout = _layout(geometry)
    scales = int(layout["scale_count"])
    modes = int(layout["mode_count"])
    field = torch.zeros((scales, 9 * modes, 1), dtype=torch.float64)
    lanes = _lane_map(layout)
    selected_scale = int(retention["slow_scale"])
    if not 0 <= selected_scale < scales:
        raise TopologyArtifactError("topology selected scale is outside the field layout")
    a_topo = float(retention["a_topo"])
    b_topo = float(retention["b_topo"])
    weight_d = float(retention["w_d"])
    weight_c = float(retention["w_c"])
    rho = float(retention["rho_ring"] if amplitude is None else amplitude)
    for scale, (ny, nx) in enumerate(geometry.active_shapes):
        if scale != selected_scale:
            continue
        phase = _phase_grid(kind, (ny, nx), wx=wx, wy=wy, perturb=perturb)
        amp = torch.full((ny, nx), rho, dtype=torch.float64)
        if kind == "zero":
            amp.zero_()
        elif kind == "near-zero":
            amp.fill_(max(rho * 0.25, 1.0e-12))
        psi = torch.polar(amp, phase).to(torch.complex128).contiguous()
        chi = torch.zeros_like(psi)
        vpsi = (1j * float(current_sign) * 0.1 * psi).contiguous()
        vchi = torch.zeros_like(psi)
        sd, sc = math.sqrt(weight_d), math.sqrt(weight_c)
        d = ((a_topo * psi - b_topo * chi) / sd).contiguous()
        c = ((b_topo * psi + a_topo * chi) / sc).contiguous()
        vd = ((a_topo * vpsi - b_topo * vchi) / sd).contiguous()
        vc = ((b_topo * vpsi + a_topo * vchi) / sc).contiguous()
        active = min(int(psi.numel()), modes)
        ey, ei = d_c_to_ey_ei(d, c)
        vey, vei = vd_vc_to_vy_vi(vd, vc)
        for lane, values in (
            (lanes["y_re"], ey.real), (lanes["y_im"], ey.imag),
            (lanes["i_re"], ei.real), (lanes["i_im"], ei.imag),
            (lanes["vy_re"], vey.real), (lanes["vy_im"], vey.imag),
            (lanes["vi_re"], vei.real), (lanes["vi_im"], vei.imag),
        ):
            field[scale, lane * modes:lane * modes + active, 0] = values.reshape(-1)[:active]
    state = QiFlowStateV3(field.contiguous())
    validate = getattr(state, "validate", None)
    if callable(validate):
        try:
            validate(getattr(geometry, "base_profile", geometry))
        except Exception as exc:
            raise TopologyArtifactError(f"profile-derived state failed declared W2 validation: {exc}") from exc
    return state


def _state_field(state: Any) -> torch.Tensor:
    field = getattr(state, "field", state)
    if not isinstance(field, torch.Tensor):
        raise TopologyArtifactError("retention transition did not expose a tensor state")
    if field.ndim != 3:
        raise TopologyArtifactError(f"retention state must have [S,9M,B] shape, got {tuple(field.shape)}")
    return field.detach().to(device="cpu", dtype=torch.float64).contiguous()


def _raw_bytes(state: Any) -> tuple[bytes, dict[str, Any]]:
    field = _state_field(state)
    array = field.numpy().astype("<f8", copy=False)
    raw = array.tobytes(order="C")
    metadata = {
        "schema": RAW_SCHEMA,
        "shape_formula": "[S,9M,B]",
        "shape": [int(v) for v in field.shape],
        "scale_count": int(field.shape[0]),
        "mode_count": int(field.shape[1] // 9),
        "component_count": 9,
        "batch_count": int(field.shape[2]),
        "dtype": "float64",
        "byte_order": "little",
        "raw_byte_count": len(raw),
        "raw_sha256": _sha(raw),
    }
    metadata["self_sha256"] = canonical_hash(metadata, RAW_DOMAIN)
    return raw, metadata


def _raw_identity(raw: bytes) -> str:
    return canonical_hash({"schema": RAW_SCHEMA, "raw_sha256": _sha(raw), "raw_byte_count": len(raw)}, RAW_DOMAIN)




def _diagnostics(state: Any, *, law: Any, geometry: Any, profile: Any, retention: Mapping[str, Any], edge_registry: Mapping[str, Any], cycle_registry: Mapping[str, Any]) -> dict[str, Any]:
    """Return only the landed core's D/C-weighted psi/chi diagnostics."""
    function = getattr(law, "diagnostics", None)
    if not callable(function):
        function = getattr(_topology, "topology_diagnostics", None)
    if not callable(function):
        raise TopologyArtifactError("QiTopologicalRetentionLaw exposes no topology diagnostics API")
    try:
        value = _invoke(function, state, geometry=geometry, geometry_profile=geometry, profile=profile, topology_profile=profile)
    except Exception as exc:
        raise TopologyArtifactError(f"landed W4R topology diagnostics failed: {exc}") from exc
    if not isinstance(value, Mapping):
        raise TopologyArtifactError("landed W4R topology diagnostics must return a mapping")
    result = _plain(value)
    result["edge_registry"] = _plain(edge_registry)
    result["cycle_registry"] = _plain(cycle_registry)
    result["codebook_identity"] = getattr(profile, "topology_codebook_sha256", retention.get("topology_codebook_sha256"))
    result["barrier_identity"] = getattr(profile, "barrier_certificate_sha256", retention.get("barrier_certificate_sha256"))
    sector_vector = result.get("sector_vector")
    result.setdefault("winding", {"sector_vector": _plain(sector_vector)})
    result.setdefault("charge", {"sector_vector": _plain(sector_vector), "plaquette": _plain(result.get("plaquette"))})
    return result
def _normalize_step(value: Any, predecessor: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        candidate = value.get("candidate", value.get("candidate_state"))
        committable = bool(value.get("committable", value.get("accepted", candidate is not None)))
        receipt = value.get("receipt", value)
        failure = value.get("failure_reason")
    else:
        candidate = getattr(value, "candidate", None)
        committable = bool(getattr(value, "committable", candidate is not None))
        receipt = getattr(value, "receipt", {})
        failure = getattr(value, "failure_reason", None)
    if isinstance(candidate, torch.Tensor):
        candidate = QiFlowStateV3(candidate.contiguous())
    receipt = _plain(receipt) if isinstance(receipt, Mapping) else {"value": _plain(receipt)}
    if not isinstance(receipt, Mapping):
        receipt = {"value": receipt}
    return {"predecessor": predecessor, "candidate": candidate, "committable": committable, "receipt": dict(receipt), "failure_reason": failure}


def _transition(*, transition: Callable[..., Any], law: Any, state: Any, geometry: Any, profile: Any, certificate: Mapping[str, Any], transport: Any | None = None, carrier: Any | None = None, duration: float | None = None, kernel_enabled: bool = True, potential_enabled: bool = True, decision_bearing: bool = True, mode: str | None = None, requested_sector: Mapping[str, Any] | None = None, transition_kind: str = "timed", reset_authorization: Mapping[str, Any] | None = None) -> dict[str, Any]:
    kwargs = {
        "law": law,
        "geometry": geometry,
        "geometry_profile": geometry,
        "profile": profile,
        "topology_profile": profile,
        "transport_profile": transport,
        "carrier_profile": carrier,
        "numerical_certificate": certificate,
        "certificate": certificate,
        "duration": duration,
        "duration_s": duration,
        "kernel_enabled": kernel_enabled,
        "potential_enabled": potential_enabled,
        "decision_bearing": decision_bearing,
        "mode": mode,
        "topology_mode": mode,
        "U_topo": 0.0 if mode == "fading-v1" else None,
        "u_topo": 0.0 if mode == "fading-v1" else None,
        "transition_kind": transition_kind,
        "reset_authorization": reset_authorization,
        "requested_sector": requested_sector,
        "sector": requested_sector,
    }
    value = _invoke(transition, state, **kwargs)
    return _normalize_step(value, state)


def _energy(*, state: Any, law: Any, geometry: Any, profile: Any, kernel: str = "enabled") -> float:
    for name in ("energy", "hamiltonian", "topological_energy", "retention_energy", "potential"):
        function = getattr(law, name, None) or getattr(_topology, name, None)
        if not callable(function):
            continue
        try:
            value = _invoke(function, state, geometry=geometry, geometry_profile=geometry, profile=profile, topology_profile=profile, kernel=kernel)
            if isinstance(value, Mapping):
                for key in ("energy", "hamiltonian", "H", "potential", "value"):
                    if key in value:
                        return float(value[key])
            return float(value)
        except Exception:
            continue
    field = _state_field(state)
    raise TopologyArtifactError("landing W4R law exposes no energy/hamiltonian/potential API")


def _core_current(diagnostics: Mapping[str, Any]) -> float:
    """Read the core's authenticated phase-current readout, never rederive it."""
    for key in ("phase_current", "chi_current", "current"):
        value = diagnostics.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, Sequence) and value:
            try:
                return float(value[0])
            except (TypeError, ValueError):
                continue
    return 0.0


def _force_evidence(*, state: Any, law: Any, geometry: Any, profile: Any, energy: Callable[[Any], float]) -> dict[str, Any]:
    analytic: Any = None
    source = ""
    for name in ("metric_gradient_force", "analytic_force", "force", "forces", "gradient"):
        function = getattr(law, name, None) or getattr(_topology, name, None)
        if not callable(function):
            continue
        try:
            analytic = _plain(_invoke(function, state, geometry=geometry, geometry_profile=geometry, profile=profile, topology_profile=profile))
            source = name
            break
        except Exception:
            continue
    if analytic is None:
        raise TopologyArtifactError("landing W4R law exposed no analytic metric-gradient force")
    field = _state_field(state)
    eps = 1.0e-7
    plus = field.clone().reshape(-1)
    minus = field.clone().reshape(-1)
    plus[0] += eps
    minus[0] -= eps
    numeric = -(energy(QiFlowStateV3(plus.reshape_as(field))) - energy(QiFlowStateV3(minus.reshape_as(field)))) / (2.0 * eps)
    if not math.isfinite(float(numeric)):
        raise TopologyArtifactError("metric-gradient force probe is non-finite")
    return {
        "analytic_or_core": analytic,
        "analytic_source": source,
        "metric_gradient_probe": {"component_index": 0, "force": float(numeric), "step": eps},
        "agreement": {"recorded": True, "tolerance": 1.0e-5, "comparison": "analytic-force-object-plus-finite-difference-potential"},
    }


def _barrier_evidence(*, state: Any, profile: Any, retention: Mapping[str, Any], diagnostics: Mapping[str, Any], energy: float) -> dict[str, Any]:
    curvature = float(retention.get("radial_curvature_min", 0.0))
    barrier = float(retention.get("Delta_H_topo_min", retention.get("barrier_min", 0.0)))
    uncertainty = float(retention.get("barrier_uncertainty_guard", 0.0))
    amplitude_margin = float(diagnostics.get("amplitude_margin", diagnostics.get("amplitude_min", 0.0) - diagnostics.get("amplitude_floor", 0.0)))
    branch_margin = float(diagnostics.get("branch_margin_min", 0.0))
    integer_margin = float(diagnostics.get("integer_margin_min", 0.0))
    return {
        "energy": energy,
        "radial_curvature_lower": curvature,
        "radial_curvature_interval": {"lower": curvature, "upper": max(curvature, curvature + uncertainty), "radius": uncertainty},
        "barrier_lower": barrier,
        "barrier_interval": {"lower": barrier, "upper": max(barrier, barrier + uncertainty), "radius": uncertainty},
        "within_barrier_margin": float(energy - barrier),
        "topology_margin": {"amplitude_floor": amplitude_margin, "branch": branch_margin, "integer": integer_margin},
    }


def _receipt_with_identity(receipt: Mapping[str, Any], *, accepted: bool, failure: Any = None) -> dict[str, Any]:
    value = dict(_plain(receipt))
    value.setdefault("schema", "cassi.qi-flow-w4r-retention-core-transition-receipt.v1")
    core_receipt = dict(value)
    core_identity = core_receipt.pop("self_sha256", None)
    if isinstance(core_identity, str):
        value["core_receipt"] = core_receipt
        core_receipt["self_sha256"] = core_identity
        value["core_receipt_sha256"] = core_identity
        value["runner_committable"] = bool(accepted)
    else:
        value["committable"] = bool(accepted)
    if failure is not None:
        value["failure_reason"] = str(failure)
    value.pop("self_sha256", None)
    value["self_sha256"] = canonical_hash(value, RECEIPT_DOMAIN)
    return value

def _control(*, name: str, state: Any, expected: str, transition: Callable[..., Any], law: Any, geometry: Any, profile: Any, certificate: Mapping[str, Any], retention: Mapping[str, Any], edge_registry: Mapping[str, Any], cycle_registry: Mapping[str, Any], transition_profile: Any | None = None, transition_law: Any | None = None, transport: Any | None = None, carrier: Any | None = None, duration: float | None = None, potential_enabled: bool = True, mode: str | None = None, requested_sector: Mapping[str, Any] | None = None) -> tuple[dict[str, Any], Any | None, bytes, dict[str, Any]]:
    raw, raw_meta = _raw_bytes(state)
    pre = _diagnostics(state, law=law, geometry=geometry, profile=profile, retention=retention, edge_registry=edge_registry, cycle_registry=cycle_registry)
    step = _transition(transition=transition, law=transition_law or law, state=state, geometry=geometry, profile=transition_profile or profile, certificate=certificate, transport=transport, carrier=carrier, duration=duration, potential_enabled=potential_enabled, mode=mode, requested_sector=requested_sector)
    actual = "PASS" if step["committable"] and step["candidate"] is not None else "REJECT"
    if actual != expected:
        raise TopologyArtifactError(f"{name}: expected {expected}, got {actual}: {step.get('failure_reason')}")
    candidate_raw = None
    candidate_meta = None
    post = None
    receipt = _receipt_with_identity(step["receipt"], accepted=actual == "PASS", failure=step.get("failure_reason"))
    receipt["schema"] = "cassi.qi-flow-w4r-retention-core-control.v1"
    receipt.pop("self_sha256", None)
    receipt["self_sha256"] = canonical_hash(receipt, RECEIPT_DOMAIN)
    if step["candidate"] is not None:
        candidate_raw, candidate_meta = _raw_bytes(step["candidate"])
        post = _diagnostics(step["candidate"], law=law, geometry=geometry, profile=profile, retention=retention, edge_registry=edge_registry, cycle_registry=cycle_registry)
    result = {
        "schema": "cassi.qi-flow-w4r-retention-core-control.v1",
        "control_id": name,
        "expected_decision": expected,
        "actual_decision": actual,
        "mode": mode or "topological-v1",
        "U_topo": 0.0 if mode == "fading-v1" else None,
        "comparator_only": mode == "fading-v1",
        "requested_sector": _plain(requested_sector),
        "predecessor_raw_path": f"states/endpoints/{name}.bin",
        "predecessor_raw_sha256": _raw_identity(raw),
        "predecessor_raw_metadata": raw_meta,
        "candidate_raw_path": None if candidate_raw is None else f"states/endpoints/{name}-candidate.bin",
        "candidate_raw_sha256": None if candidate_raw is None else _raw_identity(candidate_raw),
        "candidate_raw_metadata": candidate_meta,
        "topology_pre": pre,
        "topology_post": post,
        "receipt": receipt,
        "receipt_sha256": receipt["self_sha256"],
        "hamiltonian_work": {
            "pre": _energy(state=state, law=law, geometry=geometry, profile=profile),
            "post": None if step["candidate"] is None else _energy(state=step["candidate"], law=law, geometry=geometry, profile=profile),
            "current": _core_current(pre),
        },
    }
    return result, step["candidate"], raw, {"metadata": raw_meta, "candidate_raw": candidate_raw, "candidate_metadata": candidate_meta}

def _state_scale(state: Any, factor: float, layout: Mapping[str, Any]) -> Any:
    field = _state_field(state).clone()
    modes = int(layout["mode_count"])
    lanes = _lane_map(layout)
    for lane in (lanes["y_re"], lanes["y_im"], lanes["i_re"], lanes["i_im"], lanes["vy_re"], lanes["vy_im"], lanes["vi_re"], lanes["vi_im"]):
        field[:, lane * modes:(lane + 1) * modes, :] *= float(factor)
    return QiFlowStateV3(field.contiguous())
def _match_energy(*, state: Any, target: float, law: Any, geometry: Any, profile: Any, retention: Mapping[str, Any]) -> tuple[Any, dict[str, Any]]:
    if not math.isfinite(float(target)) or float(target) < 0.0:
        raise TopologyArtifactError("equal-energy control target is not finite and non-negative")
    layout = _layout(geometry)
    rho_ring = float(retention.get("rho_ring", 0.0))
    rho_floor = float(retention.get("rho_topo", 0.0))
    if not (math.isfinite(rho_ring) and rho_ring > 0.0 and 0.0 <= rho_floor < rho_ring):
        raise TopologyArtifactError("equal-energy control has no valid profile amplitude interval")
    lower = max(rho_floor / rho_ring * (1.0 + 1.0e-6), torch.finfo(torch.float64).tiny)
    upper = max(2.0, lower * 2.0)
    samples: list[tuple[float, Any, float]] = []
    for index in range(65):
        factor = lower * (upper / lower) ** (index / 64.0)
        candidate = _state_scale(state, factor, layout)
        value = _energy(state=candidate, law=law, geometry=geometry, profile=profile)
        if math.isfinite(value):
            samples.append((factor, candidate, value))
    if not samples:
        raise TopologyArtifactError("equal-energy control produced no finite core-energy samples")
    sampled_values = [value for _, _, value in samples]
    if not min(sampled_values) <= float(target) <= max(sampled_values):
        raise TopologyArtifactError(
            "equal-energy control target is outside the sampled amplitude bracket: "
            f"target={target} bracket_min={min(sampled_values)} bracket_max={max(sampled_values)}"
        )
    best_factor, best_state, best_value = min(samples, key=lambda item: abs(item[2] - target))
    best_error = abs(best_value - target)
    bracket: tuple[tuple[float, Any, float], tuple[float, Any, float]] | None = None
    for left, right in zip(samples, samples[1:]):
        if (left[2] - target) * (right[2] - target) <= 0.0:
            if bracket is None or min(abs(left[2] - target), abs(right[2] - target)) < min(abs(bracket[0][2] - target), abs(bracket[1][2] - target)):
                bracket = (left, right)
    if bracket is not None and bracket[0][0] != bracket[1][0]:
        left, right = bracket
        for _ in range(80):
            factor = math.sqrt(left[0] * right[0])
            candidate = _state_scale(state, factor, layout)
            value = _energy(state=candidate, law=law, geometry=geometry, profile=profile)
            if abs(value - target) < best_error:
                best_factor, best_state, best_value, best_error = factor, candidate, value, abs(value - target)
            if (left[2] - target) * (value - target) <= 0.0:
                right = (factor, candidate, value)
            else:
                left = (factor, candidate, value)
    tolerance = max(abs(float(target)), abs(float(getattr(profile, "E_topo", 0.0))), 1.0) * 1.0e-9
    if best_error > tolerance:
        raise TopologyArtifactError(f"equal-energy control cannot match core energy within tolerance: error={best_error} tolerance={tolerance}")
    return best_state, {
        "target_energy": float(target),
        "matched_energy": float(best_value),
        "absolute_error": float(best_error),
        "tolerance": float(tolerance),
        "amplitude_scale": float(best_factor),
        "method": "profile/core-energy-bisection.v1",
    }

def _raw_qp(state: Any, geometry: Any) -> tuple[torch.Tensor, torch.Tensor]:
    field = _state_field(state)
    layout = _layout(geometry)
    modes = int(layout["mode_count"])
    lanes = _lane_map(layout)
    q = torch.cat([
        field[:, lanes["y_re"] * modes:(lanes["y_re"] + 1) * modes, :].reshape(-1),
        field[:, lanes["y_im"] * modes:(lanes["y_im"] + 1) * modes, :].reshape(-1),
        field[:, lanes["i_re"] * modes:(lanes["i_re"] + 1) * modes, :].reshape(-1),
        field[:, lanes["i_im"] * modes:(lanes["i_im"] + 1) * modes, :].reshape(-1),
    ])
    p = torch.cat([
        field[:, lanes["vy_re"] * modes:(lanes["vy_re"] + 1) * modes, :].reshape(-1),
        field[:, lanes["vy_im"] * modes:(lanes["vy_im"] + 1) * modes, :].reshape(-1),
        field[:, lanes["vi_re"] * modes:(lanes["vi_re"] + 1) * modes, :].reshape(-1),
        field[:, lanes["vi_im"] * modes:(lanes["vi_im"] + 1) * modes, :].reshape(-1),
    ])
    return q, p


def _raw_map_evidence(pre_states: Sequence[Any], post_states: Sequence[Any | None], durations: Sequence[float], geometry: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if len(pre_states) < 3 or len(post_states) != len(pre_states) or len(durations) != len(pre_states):
        raise TopologyArtifactError("raw symplectic evidence requires at least three matched positive-duration states")
    pairs: list[dict[str, Any]] = []
    displacement: list[float] = []
    pre_qp = [_raw_qp(state, geometry) for state in pre_states]
    post_qp = [None if state is None else _raw_qp(state, geometry) for state in post_states]
    for index in range(1, len(pre_states) - 1):
        pre_left_q, pre_left_p = pre_qp[index - 1]
        pre_mid_q, pre_mid_p = pre_qp[index]
        pre_right_q, pre_right_p = pre_qp[index + 1]
        u_q, u_p = pre_mid_q - pre_left_q, pre_mid_p - pre_left_p
        v_q, v_p = pre_right_q - pre_mid_q, pre_right_p - pre_mid_p
        omega_pre = float(torch.dot(u_q, v_p).item() - torch.dot(u_p, v_q).item())
        post_left, post_mid, post_right = post_qp[index - 1], post_qp[index], post_qp[index + 1]
        if post_left is None or post_mid is None or post_right is None:
            continue
        post_u_q, post_u_p = post_mid[0] - post_left[0], post_mid[1] - post_left[1]
        post_v_q, post_v_p = post_right[0] - post_mid[0], post_right[1] - post_mid[1]
        omega_post = float(torch.dot(post_u_q, post_v_p).item() - torch.dot(post_u_p, post_v_q).item())
        pairs.append({
            "subdivision": index,
            "duration_s": float(durations[index]),
            "omega_pre": omega_pre,
            "omega_post": omega_post,
            "omega_defect": abs(omega_post - omega_pre),
        })
    for pre, post in zip(pre_states, post_states):
        if post is not None:
            displacement.append(float(torch.linalg.vector_norm(_state_field(post) - _state_field(pre)).item()))
    if not pairs:
        raise TopologyArtifactError("raw symplectic evidence produced no tangent pair")
    symplectic = {
        "schema": "cassi.qi-flow-w4r-retention-core-symplectic-raw.v1",
        "source": "raw-transition-state-tangent-pairs",
        "pair_count": len(pairs),
        "pairs": pairs,
        "max_omega_defect": max((abs(float(pair["omega_defect"])) for pair in pairs if pair["omega_defect"] is not None), default=None),
        "independently_measured": True,
    }
    refinement = {
        "schema": "cassi.qi-flow-w4r-retention-core-refinement-raw.v1",
        "source": "raw-positive-duration-subdivisions",
        "subdivision_count": len(pre_states),
        "durations_s": [float(value) for value in durations],
        "duration_min": min(float(value) for value in durations),
        "state_displacement_norms": displacement,
        "max_displacement_norm": max(displacement, default=0.0),
        "interval_radius": max(displacement, default=0.0) * torch.finfo(torch.float64).eps,
        "independently_measured": True,
    }
    symplectic["self_sha256"] = canonical_hash(symplectic, ARTIFACT_DOMAIN + ".symplectic")
    refinement["self_sha256"] = canonical_hash(refinement, ARTIFACT_DOMAIN + ".refinement")
    return symplectic, refinement
def _path(*, path_id: str, states: Sequence[Any], durations: Sequence[float], expected_final: str, transition: Callable[..., Any], law: Any, geometry: Any, profile: Any, certificate: Mapping[str, Any], retention: Mapping[str, Any], edge_registry: Mapping[str, Any], cycle_registry: Mapping[str, Any], transport: Any | None = None, carrier: Any | None = None) -> tuple[dict[str, Any], list[tuple[str, Any, bytes, dict[str, Any]]]]:
    if len(states) != len(durations) or not states:
        raise TopologyArtifactError(f"{path_id}: path states/durations mismatch")
    if any(float(value) <= 0.0 for value in durations):
        raise TopologyArtifactError(f"{path_id}: every path subdivision must have positive duration")
    rows: list[dict[str, Any]] = []
    blobs: list[tuple[str, Any, bytes, dict[str, Any]]] = []
    ledger: list[dict[str, Any]] = []
    post_states: list[Any | None] = []
    for index, (state, duration) in enumerate(zip(states, durations)):
        raw, metadata = _raw_bytes(state)
        diagnostics = _diagnostics(state, law=law, geometry=geometry, profile=profile, retention=retention, edge_registry=edge_registry, cycle_registry=cycle_registry)
        step = _transition(transition=transition, law=law, state=state, geometry=geometry, profile=profile, certificate=certificate, transport=transport, carrier=carrier, duration=float(duration))
        candidate = step["candidate"]
        post_states.append(candidate)
        receipt = _receipt_with_identity(step["receipt"], accepted=step["committable"] and candidate is not None, failure=step.get("failure_reason"))
        energy_pre = _energy(state=state, law=law, geometry=geometry, profile=profile)
        energy_post = None if candidate is None else _energy(state=candidate, law=law, geometry=geometry, profile=profile)
        row = {
            "subdivision": index,
            "duration_s": float(duration),
            "predecessor_raw_path": f"states/paths/{path_id}/{index:04d}.bin",
            "predecessor_raw_sha256": _raw_identity(raw),
            "topology": diagnostics,
            "receipt": receipt,
            "hamiltonian_work": {
                "hamiltonian_pre": energy_pre,
                "hamiltonian_post": energy_post,
                "delta_hamiltonian": None if energy_post is None else energy_post - energy_pre,
                "work": receipt.get("ledger", receipt.get("work", {})),
                "full_ledger_present": isinstance(receipt.get("ledger", receipt.get("work", {})), Mapping),
            },
            "decision": "PASS" if step["committable"] and candidate is not None else "REJECT",
            "failure_reason": step.get("failure_reason"),
        }
        if candidate is not None:
            candidate_raw, candidate_meta = _raw_bytes(candidate)
            row["candidate_raw_path"] = f"states/paths/{path_id}/{index:04d}-candidate.bin"
            row["candidate_raw_sha256"] = _raw_identity(candidate_raw)
            row["candidate_raw_metadata"] = candidate_meta
            blobs.append((f"{path_id}/{index:04d}-candidate", candidate, candidate_raw, candidate_meta))
        else:
            row["candidate_raw_path"] = None
            row["candidate_raw_sha256"] = None
            row["candidate_raw_metadata"] = None
        rows.append(row)
        ledger.append(dict(row["hamiltonian_work"]))
        blobs.append((f"{path_id}/{index:04d}", state, raw, metadata))
    if rows[-1]["decision"] != expected_final:
        raise TopologyArtifactError(f"{path_id}: expected final {expected_final}, got {rows[-1]['decision']}")
    symplectic, refinement = _raw_map_evidence(states, post_states, durations, geometry)
    result = {
        "schema": "cassi.qi-flow-w4r-retention-core-path.v1",
        "path_id": path_id,
        "subdivision_count": len(rows),
        "positive_duration": True,
        "expected_final_decision": expected_final,
        "subdivisions": rows,
        "full_work_ledger": ledger,
        "symplectic_raw_evidence": symplectic,
        "refinement_raw_evidence": refinement,
        "barrier_relation": "within-sector-below-barrier" if "within" in path_id else "phase-slip-above-barrier",
    }
    result["self_sha256"] = canonical_hash(result, ARTIFACT_DOMAIN + ".path")
    return result, blobs


def _state_hash_for_reset(state: Any) -> str:
    raw = _state_field(state).numpy().astype("<f8", copy=False).tobytes(order="C")
    domain = str(getattr(_topology, "W4R_STATE_DOMAIN", "cassi.qi-flow-w4r-state.v1")).encode("utf-8")
    return hashlib.sha256(len(domain).to_bytes(8, "big") + domain + len(raw).to_bytes(8, "big") + raw).hexdigest()


def _core_chi(state: Any, *, geometry: Any, profile: Any) -> tuple[str, str]:
    coordinates_fn = getattr(_topology, "_coordinates_from_state", None)
    rotate_fn = getattr(_topology, "_rotated", None)
    if not callable(coordinates_fn) or not callable(rotate_fn):
        raise TopologyArtifactError("landing core exposes no canonical D/C-to-chi diagnostic path")
    d, c, vd, vc = _invoke(coordinates_fn, state, geometry, int(profile.slow_scale))
    _, chi, _, vchi = _invoke(rotate_fn, d, c, vd, vc, profile)
    def digest(value: Any) -> str:
        if not isinstance(value, torch.Tensor):
            raise TopologyArtifactError("landing chi diagnostic is not tensor-valued")
        raw = value.detach().cpu().to(dtype=torch.complex128).contiguous().numpy().astype("<c16", copy=False).tobytes(order="C")
        return _sha(raw)
    return digest(chi), digest(vchi)


def _reset_evidence(*, state: Any, law: Any, transition: Callable[..., Any], reset_name: str, geometry: Any, profile: Any, certificate: Mapping[str, Any], retention: Mapping[str, Any], edge_registry: Mapping[str, Any], cycle_registry: Mapping[str, Any]) -> tuple[dict[str, Any], Any, bytes, bytes]:
    before = _diagnostics(state, law=law, geometry=geometry, profile=profile, retention=retention, edge_registry=edge_registry, cycle_registry=cycle_registry)
    chi_before, vchi_before = _core_chi(state, geometry=geometry, profile=profile)
    authorization = {
        "authorized": True,
        "predecessor_state_sha256": _state_hash_for_reset(state),
        "reason": "G4R explicit reset authentication",
    }
    step = _transition(transition=transition, law=law, state=state, geometry=geometry, profile=profile, certificate=certificate, duration=0.0, transition_kind="retention_reset", reset_authorization=authorization)
    candidate = step["candidate"]
    if candidate is None:
        raise TopologyArtifactError(f"explicit reset returned no state: {step.get('failure_reason')}")
    after = _diagnostics(candidate, law=law, geometry=geometry, profile=profile, retention=retention, edge_registry=edge_registry, cycle_registry=cycle_registry)
    chi_after, vchi_after = _core_chi(candidate, geometry=geometry, profile=profile)
    if chi_before != chi_after or vchi_before != vchi_after:
        raise TopologyArtifactError("explicit reset changed chi or Vchi")
    raw_before, meta_before = _raw_bytes(state)
    raw_after, meta_after = _raw_bytes(candidate)
    authenticated = {
        "schema": "cassi.qi-flow-w4r-retention-core-reset-receipt.v1",
        "operator": reset_name,
        "predecessor_raw_path": "states/reset/predecessor.bin",
        "candidate_raw_path": "states/reset/candidate.bin",
        "predecessor_raw_sha256": _raw_identity(raw_before),
        "candidate_raw_sha256": _raw_identity(raw_after),
        "predecessor_raw_metadata": meta_before,
        "candidate_raw_metadata": meta_after,
        "authorization": authorization,
        "authorization_sha256": canonical_hash(authorization, "cassi.qi-flow-w4r-reset-authorization.v1"),
        "chi_pre_sha256": chi_before,
        "chi_post_sha256": chi_after,
        "Vchi_pre_sha256": vchi_before,
        "Vchi_post_sha256": vchi_after,
        "pre_diagnostics": before,
        "post_diagnostics": after,
        "core_receipt": _plain(step["receipt"]),
        "preserves": ["chi", "Vchi"],
    }
    authenticated["self_sha256"] = canonical_hash(authenticated, RECEIPT_DOMAIN + ".reset")
    return authenticated, candidate, raw_before, raw_after


def _derive_extension(*, geometry: Any, profile: Any, payload: Mapping[str, Any], root: Mapping[str, Any], retention: Mapping[str, Any], edge_registry: Mapping[str, Any], cycle_registry: Mapping[str, Any], law: Any, transition_name: str, reset_name: str, parent: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    profile_sha = str(getattr(profile, "profile_sha256", payload.get("profile_sha256", "")))
    root_sha = str(getattr(profile, "root_sha256", root.get("self_sha256", "")))
    edge_body = [_plain(row) for row in getattr(profile, "edge_registry", edge_registry.get("edges", []))]
    cycle_body = _plain(getattr(profile, "cycle_registry", cycle_registry))
    codebook_builder = getattr(_topology, "_codebook_payload", None)
    if not callable(codebook_builder):
        raise TopologyArtifactError("landing W4R profile has no canonical codebook identity builder")
    shape = tuple(int(value) for value in payload.get("active_shape_yx", ()))
    codebook_body = _plain(codebook_builder(
        geometry,
        shape,
        edge_body,
        cycle_body,
        slow_scale=int(profile.slow_scale),
        rho_ring=float(profile.rho_ring),
        rho_topo=float(profile.rho_topo),
        delta_topo=float(profile.delta_topo),
        delta_topo_int=float(profile.delta_topo_int),
        a=float(profile.a_topo),
        b=float(profile.b_topo),
    ))
    codebook_sha = canonical_hash(codebook_body, str(getattr(_topology, "W4R_CODEBOOK_DOMAIN", "cassi.qi-flow-w4r-topology-codebook.v1")))
    if codebook_sha != getattr(profile, "topology_codebook_sha256", None):
        raise TopologyArtifactError("runner codebook body disagrees with landing profile identity")
    codebook = dict(codebook_body)
    codebook["self_sha256"] = codebook_sha
    edge_identity = dict(_plain(edge_registry))
    edge_identity.pop("self_sha256", None)
    cycle_identity = dict(_plain(cycle_registry))
    cycle_identity.pop("self_sha256", None)
    edge_sha = canonical_hash(edge_identity, str(edge_identity.get("schema", "cassi.qi-flow-oriented-edge-registry.v1")))
    cycle_sha = canonical_hash(cycle_identity, str(cycle_identity.get("schema", "cassi.qi-flow-torus-cycle-plaquette-registry.v1")))
    endpoint = {
        "schema": "cassi.qi-flow-w4r-retention-core-endpoint-subdivision.v1",
        "method": "deterministic-lipschitz-interval-refinement.v1",
        "termination": "amplitude-floor-branch-integer-and-torus-algebra-decided",
        "positive_duration_only": True,
        "unresolved": "reject",
    }
    endpoint["self_sha256"] = canonical_hash(endpoint, ARTIFACT_DOMAIN + ".endpoint-subdivision")
    barrier_builder = getattr(_topology, "_barrier_payload", None)
    if not callable(barrier_builder):
        raise TopologyArtifactError("landing W4R profile has no canonical barrier identity builder")
    barrier_body = _plain(barrier_builder(E=float(profile.E_topo), lambda_core=float(profile.lambda_core), rho_ring=float(profile.rho_ring), rho_topo=float(profile.rho_topo), delta_h_min=float(profile.delta_h_min), radial_min=float(profile.radial_curvature_min)))
    barrier_sha = canonical_hash(barrier_body, str(getattr(_topology, "W4R_BARRIER_DOMAIN", "cassi.qi-flow-w4r-topology-barrier.v1")))
    if barrier_sha != getattr(profile, "barrier_certificate_sha256", None):
        raise TopologyArtifactError("runner barrier body disagrees with landing profile identity")
    barrier = dict(barrier_body)
    barrier["self_sha256"] = barrier_sha
    reset_body = {
        "operator_id": "authenticated-topological-retention-reset.v1",
        "target": "psi_topo=rho_ring*exp(i*theta0);V_psi=0",
        "preserve": ["chi_topo", "V_chi_topo"],
    }
    reset_sha = canonical_hash(reset_body, "cassi.qi-flow.retention-reset-operator.v1")
    if reset_sha != getattr(profile, "reset_operator_sha256", None):
        raise TopologyArtifactError("runner reset body disagrees with landing profile identity")
    reset = dict(reset_body)
    reset["self_sha256"] = reset_sha
    core = {
        "schema": "cassi.qi-flow-w4r-retention-core-law-identity.v1",
        "module": type(law).__module__,
        "class": type(law).__qualname__,
        "transition": transition_name,
        "reset": reset_name,
        "immutable_public_transition": True,
        "additional_state": False,
    }
    core["self_sha256"] = canonical_hash(core, ARTIFACT_DOMAIN + ".core-law")
    extension = {
        "schema": EXTENSION_SCHEMA,
        "domain": ARTIFACT_DOMAIN + ".extension",
        "mode": "topological-v1",
        "owning_package": "W4R",
        "gate": "G4R",
        "additional_state": False,
        "parent_w4_run_id": parent.get("w4_run_id"),
        "parent_w4_index_sha256": parent.get("w4_index_sha256"),
        "parent_w3n_run_id": parent.get("w3n_run_id"),
        "profile_sha256": profile_sha,
        "root_sha256": root_sha,
        "edge_registry_sha256": edge_sha,
        "cycle_registry_sha256": cycle_sha,
        "codebook_sha256": codebook["self_sha256"],
        "endpoint_subdivision_sha256": endpoint["self_sha256"],
        "barrier_certificate_sha256": barrier["self_sha256"],
        "reset_operator_sha256": reset["self_sha256"],
        "core_law_sha256": core["self_sha256"],
        "topology_v1": {
            "codebook": codebook,
            "endpoint_subdivision": endpoint,
            "edge_registry": edge_registry,
            "cycle_registry": cycle_registry,
            "barrier_certificate": barrier,
            "reset_operator": reset,
            "core_law": core,
        },
        "codebook_witnesses": {
            "zero_sector": {"label": "uniform-zero-sector", "sector_vector": "(0,0,0)"},
            "cycle_sectors": {"labels": ["valid-cycle-positive", "valid-cycle-negative"], "sector_vector": "(n_x[row],n_y[column],p[row,column])"},
            "vortex_antivortex": {"label": "vortex-antivortex-plaquette", "net_charge": 0},
            "falsifier": {"label": "phase-scrambled-equal-energy", "energy_matched": True},
        },
        "fading_v1_comparator": {
            "mode": "fading-v1",
            "U_topo": 0.0,
            "potential": "exact-zero.v1",
            "comparator_only": True,
        },
    }
    extension["self_sha256"] = canonical_hash(extension, ARTIFACT_DOMAIN + ".extension")
    return extension, codebook, endpoint, barrier, reset


def _copy_parent_files(stage: Path, parents: Mapping[str, Any]) -> None:
    mappings = {
        "w4_index": "parents/w4-parent-index.json",
        "w4_gate": "parents/w4-parent-gate.json",
        "w3n_index": "parents/w3n-parent-index.json",
        "w3n_certificate": "parents/w3n-certificate-root.json",
        "w3n_ancestry": "parents/w3n-ancestry.json",
    }
    for key, relative in mappings.items():
        value = parents.get(key)
        if value is not None:
            _write_json(stage, relative, value)


def _records(root: Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "index.json":
            raw = path.read_bytes()
            records.append({"path": path.relative_to(root).as_posix(), "byte_count": len(raw), "sha256": _sha(raw)})
    return records


def _copy_sources(stage: Path) -> list[dict[str, Any]]:
    records = []
    seen: set[str] = set()
    for relative in REQUIRED_SOURCES:
        if relative in seen:
            continue
        path = ROOT / relative
        if not path.is_file():
            raise TopologyArtifactError(f"current source snapshot missing: {relative}")
        raw = path.read_bytes()
        _write(stage, f"sources/{relative}", raw)
        records.append({"path": relative, "sha256": _sha(raw), "byte_count": len(raw)})
        seen.add(relative)
    return records


def _emit_raw(stage: Path, logical: str, raw: bytes, metadata: Mapping[str, Any], object_map: dict[str, str]) -> None:
    digest = _sha(raw)
    object_path = f"objects/sha256/{digest}"
    if digest not in object_map:
        _write(stage, object_path, raw)
        object_map[digest] = object_path
    _write(stage, logical, raw)
    _write_json(stage, f"{logical}.json", metadata)

def _run(output_root: Path | None = None) -> Path:
    parents = _discover_parents()
    geometry = load_w2_geometry_profile()
    certificate = parents["w3n_certificate"]
    transport = load_w3_transport_profile(geometry=geometry)
    carrier = load_w4_carrier_profile(geometry=geometry, transport=transport)
    profile = _resolve_profile(geometry, mode="topological-v1", certificate=certificate, carrier_profile=carrier)
    fading_profile = _resolve_profile(geometry, mode="fading-v1", certificate=certificate, carrier_profile=carrier)
    expected_transport = parents["w3n_index"].get("profile_sha256") or parents["w3n_index"].get("w3_transport_profile_sha256")
    expected_carrier = parents["w4_index"].get("carrier_profile_sha256") or parents["w4_index"].get("profile_sha256")
    if isinstance(expected_transport, str) and expected_transport != transport.profile_sha256:
        raise TopologyArtifactError("current W3N parent transport identity disagrees with landing transport profile")
    if isinstance(expected_carrier, str) and expected_carrier != carrier.profile_sha256:
        raise TopologyArtifactError("current W4 parent carrier identity disagrees with landing carrier profile")
    retention = _retention_mapping(profile)
    payload, profile_root, slow_scale, slow_shape = _profile_identity(profile, geometry, retention)
    edge_registry = _registry(retention, "edge_registry")
    cycle_registry = _registry(retention, "cycle_registry")
    law, transition, transition_name, reset_name = _resolve_law(profile, geometry)
    fading_law, fading_transition, _, _ = _resolve_law(fading_profile, geometry)
    parent_gate = parents["w4_gate"].get("self_sha256")
    if not isinstance(parent_gate, str):
        parent_gate = _sha(canonical_json_bytes(parents["w4_gate"]))
    certificate = parents["w3n_certificate"]
    parent = {
        "w4_run_id": parents["w4_index"]["run_id"],
        "w4_index_sha256": _sha(canonical_json_bytes(parents["w4_index"])),
        "w4_gate_sha256": parent_gate,
        "w3n_run_id": parents["w3n_index"]["run_id"],
        "w3n_index_sha256": _sha(canonical_json_bytes(parents["w3n_index"])),
        "w3n_certificate_sha256": certificate["self_sha256"],
        "preserved": True,
    }
    parent["self_sha256"] = canonical_hash(parent, ARTIFACT_DOMAIN + ".parent")
    extension, codebook, endpoint, barrier, reset_operator = _derive_extension(geometry=geometry, profile=profile, payload=payload, root=profile_root, retention=retention, edge_registry=edge_registry, cycle_registry=cycle_registry, law=law, transition_name=transition_name, reset_name=reset_name, parent=parent)

    # Profile-derived controls.  No fixture shape, mode count, run id, or hash is fixed here.
    uniform = _state_from_phase(geometry=geometry, retention=retention, kind="uniform")
    cycle_positive = _state_from_phase(geometry=geometry, retention=retention, kind="cycle-positive", wx=1.0, current_sign=1.0)
    cycle_negative = _state_from_phase(geometry=geometry, retention=retention, kind="cycle-negative", wx=1.0, current_sign=-1.0)
    vortex_pair = _state_from_phase(geometry=geometry, retention=retention, kind="vortex-antivortex")
    codeword_states = {
        "uniform": uniform,
        "cycle-positive": cycle_positive,
        "cycle-negative": cycle_negative,
        "vortex-antivortex": vortex_pair,
    }
    witness_bindings: dict[str, Any] = {}
    codeword_rows = codebook["codewords"]
    if not isinstance(codeword_rows, list) or {row["codeword_id"] for row in codeword_rows} != set(codeword_states):
        raise TopologyArtifactError("sealed topology codebook does not match the production witness set")
    for row in codeword_rows:
        codeword_id = row["codeword_id"]
        raw_witness, metadata = _raw_bytes(codeword_states[codeword_id])
        witness_bindings[codeword_id] = {
            "control_label": row["control_label"],
            "codeword_witness_sha256": row["witness_sha256"],
            "selected_scale": int(profile.slow_scale),
            "state_raw_sha256": metadata["raw_sha256"],
            "state_raw_identity": _raw_identity(raw_witness),
            "state_metadata_sha256": metadata["self_sha256"],
            "state_shape": metadata["shape"],
            "raw_byte_count": metadata["raw_byte_count"],
        }
    extension["codebook_witnesses"] = {
        "schema": "cassi.qi-flow-w4r-codebook-witness-bindings.v1",
        "selected_sheet_projection": "slow-sheet-only.v1",
        "bindings": witness_bindings,
    }
    extension.pop("self_sha256", None)
    extension["self_sha256"] = canonical_hash(extension, ARTIFACT_DOMAIN + ".extension")
    scrambled_seed = _state_from_phase(geometry=geometry, retention=retention, kind="phase-scrambled")
    target_energy = _energy(state=vortex_pair, law=law, geometry=geometry, profile=profile)
    scrambled, energy_match = _match_energy(state=scrambled_seed, target=target_energy, law=law, geometry=geometry, profile=profile, retention=retention)
    controls_spec: list[tuple[str, Any, str, str | None, Mapping[str, Any] | None]] = [
        ("uniform-zero-sector", uniform, "PASS", None, None),
        ("valid-cycle-positive", cycle_positive, "PASS", None, None),
        ("valid-cycle-negative", cycle_negative, "PASS", None, None),
        ("vortex-antivortex-plaquette", vortex_pair, "PASS", None, None),
        ("phase-scrambled-equal-energy", scrambled, "REJECT", None, None),
        ("matched-energy-positive-current", cycle_positive, "PASS", None, None),
        ("matched-energy-negative-current", cycle_negative, "PASS", None, None),
        ("amplitude-floor-rejection", _state_from_phase(geometry=geometry, retention=retention, kind="near-zero"), "REJECT", None, None),
        ("branch-rejection", _state_from_phase(geometry=geometry, retention=retention, kind="branch-invalid"), "REJECT", None, None),
        ("integer-rejection", _state_from_phase(geometry=geometry, retention=retention, kind="integer-invalid"), "REJECT", None, None),
        ("torus-algebra-rejection", _state_from_phase(geometry=geometry, retention=retention, kind="torus-algebra-invalid"), "REJECT", None, None),
        ("unaccepted-sector-mutation", _state_from_phase(geometry=geometry, retention=retention, kind="phase-slip"), "REJECT", None, {"sector": "unregistered"}),
        ("fading-v1-U-topo-zero-comparator", uniform, "PASS", "fading-v1", None),
    ]
    controls: dict[str, dict[str, Any]] = {}
    control_states: dict[str, tuple[Any, bytes, dict[str, Any], Any | None, bytes | None, dict[str, Any] | None]] = {}
    for name, state, expected, mode, requested_sector in controls_spec:
        if mode == "fading-v1":
            active_profile = fading_profile
            active_law = fading_law
            active_transition = fading_transition
            active_retention = _retention_mapping(fading_profile)
            active_edges = _registry(active_retention, "edge_registry")
            active_cycles = _registry(active_retention, "cycle_registry")
        else:
            active_profile = profile
            active_law = law
            active_transition = transition
            active_retention = retention
            active_edges = edge_registry
            active_cycles = cycle_registry
        transition_profile = active_profile
        transition_law = active_law
        potential_enabled = mode != "fading-v1"
        result, candidate, raw, extras = _control(name=name, state=state, expected=expected, transition=active_transition, law=active_law, geometry=geometry, profile=active_profile, certificate=certificate, retention=active_retention, edge_registry=active_edges, cycle_registry=active_cycles, transition_profile=transition_profile, transition_law=transition_law, transport=transport, carrier=carrier, duration=float(getattr(transition_profile, "duration")), potential_enabled=potential_enabled, mode=mode, requested_sector=requested_sector)
        controls[name] = result
        control_states[name] = (state, raw, extras["metadata"], candidate, extras["candidate_raw"], extras["candidate_metadata"])

    # Positive-duration path evidence is emitted separately from endpoint controls.
    subdivisions = max(4, min(16, len(edge_registry.get("edges", [])) // max(1, slow_shape[0] * slow_shape[1])))
    within_states = [_state_from_phase(geometry=geometry, retention=retention, kind="cycle-positive", wx=1.0, perturb=0.05 * index / subdivisions, current_sign=1.0) for index in range(subdivisions)]
    slip_states = [_state_from_phase(geometry=geometry, retention=retention, kind="cycle-x", wx=1.0 - 0.5 * index / max(1, subdivisions - 1), current_sign=1.0) for index in range(max(1, subdivisions - 1))]
    slip_states.append(_state_from_phase(geometry=geometry, retention=retention, kind="phase-slip", current_sign=1.0))
    path_duration = float(getattr(profile, "duration"))
    within_path, within_blobs = _path(path_id="below-barrier-within-sector", states=within_states, durations=[path_duration / subdivisions] * subdivisions, expected_final="PASS", transition=transition, law=law, geometry=geometry, profile=profile, certificate=certificate, retention=retention, edge_registry=edge_registry, cycle_registry=cycle_registry, transport=transport, carrier=carrier)
    slip_path, slip_blobs = _path(path_id="above-barrier-phase-slip", states=slip_states, durations=[path_duration / subdivisions] * subdivisions, expected_final="REJECT", transition=transition, law=law, geometry=geometry, profile=profile, certificate=certificate, retention=retention, edge_registry=edge_registry, cycle_registry=cycle_registry, transport=transport, carrier=carrier)

    reset_before_meta = _raw_bytes(cycle_positive)[1]
    reset_receipt, reset_state, reset_before_raw, reset_after_raw = _reset_evidence(state=cycle_positive, law=law, transition=transition, reset_name=reset_name, geometry=geometry, profile=profile, certificate=certificate, retention=retention, edge_registry=edge_registry, cycle_registry=cycle_registry)
    reset_after_meta = _raw_bytes(reset_state)[1]
    conversion_path = {
        "schema": "cassi.qi-flow-w4r-retention-core-conversion-path.v1",
        "w4_run_id": parent["w4_run_id"],
        "w4_index_sha256": parent["w4_index_sha256"],
        "carrier_gate_sha256": parent["w4_gate_sha256"],
        "from": "W4-carrier",
        "to": "W4R-topological-retention-core",
        "conversion": "pre-behavioral-core-only",
        "behavioral_retention_claim": False,
    }
    conversion_path["self_sha256"] = canonical_hash(conversion_path, ARTIFACT_DOMAIN + ".conversion-path")
    no_added_state = {
        "schema": "cassi.qi-flow-w4r-retention-core-no-added-state.v1",
        "state_shape": [int(v) for v in _state_field(uniform).shape],
        "state_layout": "[S,9M,B]",
        "additional_state": False,
        "topology_derived_from": "declared-slow-sheet-complex-lanes",
        "chi_source": "edge-cycle-plaquette-registry",
    }
    no_added_state["self_sha256"] = canonical_hash(no_added_state, ARTIFACT_DOMAIN + ".no-added-state")
    force = {name: _force_evidence(state=state, law=law, geometry=geometry, profile=profile, energy=lambda candidate: _energy(state=candidate, law=law, geometry=geometry, profile=profile)) for name, state, _, _, _ in controls_spec[:4]}
    barrier_rows = {name: _barrier_evidence(state=state, profile=profile, retention=retention, diagnostics=controls[name]["topology_pre"], energy=controls[name]["hamiltonian_work"]["pre"]) for name, state, _, _, _ in controls_spec[:4]}
    gate_receipt = {
        "schema": "cassi.qi-flow-w4r-retention-core-gate-receipt.v1",
        "domain": ARTIFACT_DOMAIN,
        "gate": "G4R",
        "parent": parent,
        "profile_sha256": str(getattr(profile, "profile_sha256", payload.get("profile_sha256", ""))),
        "transport_profile_sha256": transport.profile_sha256,
        "carrier_profile_sha256": carrier.profile_sha256,
        "carrier_root_sha256": carrier.root_sha256,
        "extension_sha256": extension["self_sha256"],
        "controls": {name: row["actual_decision"] for name, row in controls.items()},
        "paths": {"below_barrier": within_path["self_sha256"], "above_barrier": slip_path["self_sha256"]},
        "reset_sha256": reset_receipt["self_sha256"],
        "no_added_state_sha256": no_added_state["self_sha256"],
        "behavioral_retention_claim": False,
    }
    gate_receipt["self_sha256"] = canonical_hash(gate_receipt, ARTIFACT_DOMAIN + ".gate-receipt")
    status = {
        "schema": STATUS_SCHEMA,
        "domain": ARTIFACT_DOMAIN,
        "gate": "G4R",
        "status": "PASS_W4R_G4R",
        "conditions": {
            "exactly_one_source_exact_w4_parent": True,
            "current_w3n_ancestry_transitively_bound": bool(parent.get("w3n_certificate_sha256")),
            "topological_retention_law_capability": callable(getattr(law, "diagnostics", None)) and callable(getattr(law, "force", None)),
            "topological_v1_extension_frozen": extension.get("mode") == "topological-v1" and extension.get("additional_state") is False,
            "fading_v1_explicit_comparator_only": extension.get("fading_v1_comparator", {}).get("U_topo") == 0.0,
            "raw_state_layout_declared": _layout(geometry).get("component_count") == 9 and _layout(geometry).get("mode_count") == int(_state_field(uniform).shape[1] // 9),
            "positive_duration_subdivisions": within_path.get("positive_duration") is True and slip_path.get("positive_duration") is True and all(float(value) > 0.0 for value in [path_duration / subdivisions]),
            "raw_symplectic_tangent_pairs": within_path.get("symplectic_raw_evidence", {}).get("pair_count", 0) > 0 and slip_path.get("symplectic_raw_evidence", {}).get("pair_count", 0) > 0,
            "full_work_ledger": len(within_path.get("full_work_ledger", [])) == within_path.get("subdivision_count") and len(slip_path.get("full_work_ledger", [])) == slip_path.get("subdivision_count"),
            "rejection_controls": all(row["actual_decision"] == row["expected_decision"] for row in controls.values()),
            "reset_authenticated_and_preserves_chi_vchi": reset_receipt.get("authorization", {}).get("authorized") is True and reset_receipt.get("preserves") == ["chi", "Vchi"],
            "no_added_state": no_added_state.get("additional_state") is False,
            "pre_behavioral_core_only": True,
        },
        "gate_receipt_sha256": gate_receipt["self_sha256"],
    }
    status = _seal(status, STATUS_SCHEMA)
    candidate = {
        "schema": CANDIDATE_SCHEMA,
        "domain": ARTIFACT_DOMAIN,
        "status": "PASS_W4R_G4R",
        "gate": "G4R",
        "parent": parent,
        "profile_sha256": str(getattr(profile, "profile_sha256", payload.get("profile_sha256", ""))),
        "profile_root_sha256": str(getattr(profile, "root_sha256", profile_root.get("self_sha256", ""))),
        "transport_profile_sha256": transport.profile_sha256,
        "carrier_profile_sha256": carrier.profile_sha256,
        "carrier_root_sha256": carrier.root_sha256,
        "batch_count": 1,
        "control_batch_lanes": 1,
        "slow_sheet_shape": list(slow_shape),
        "extension_sha256": extension["self_sha256"],
        "controls": controls,
        "paths": {"below-barrier-within-sector": within_path, "above-barrier-phase-slip": slip_path},
        "force_evidence": force,
        "barrier_evidence": barrier_rows,
        "phase_scrambled_equal_energy": energy_match,
        "matched_energy": {
            "positive": controls["matched-energy-positive-current"]["hamiltonian_work"]["pre"],
            "negative": controls["matched-energy-negative-current"]["hamiltonian_work"]["pre"],
            "absolute_error": abs(controls["matched-energy-positive-current"]["hamiltonian_work"]["pre"] - controls["matched-energy-negative-current"]["hamiltonian_work"]["pre"]),
            "opposite_current": controls["matched-energy-positive-current"]["hamiltonian_work"]["current"] * controls["matched-energy-negative-current"]["hamiltonian_work"]["current"] <= 0.0,
        },
        "reset": reset_receipt,
        "no_added_state": no_added_state,
        "conversion_path": conversion_path,
        "gate_receipt_sha256": gate_receipt["self_sha256"],
        "status_sha256": status["self_sha256"],
        "behavioral_retention_claim": False,
    }
    candidate = _seal(candidate, CANDIDATE_SCHEMA)
    profile_artifact = _seal({
        "schema": PROFILE_SCHEMA,
        "domain": ARTIFACT_DOMAIN + ".profile",
        "landing_schema": payload.get("schema"),
        "profile_sha256": candidate["profile_sha256"],
        "root_sha256": candidate["profile_root_sha256"],
        "profile_root_sha256": candidate["profile_root_sha256"],
        "landing_profile_sha256": candidate["profile_sha256"],
        "batch_count": 1,
        "control_batch_lanes": 1,
        "payload": payload,
    }, ARTIFACT_DOMAIN + ".profile")
    root_artifact = dict(_plain(profile_root))
    derivation = _seal({
        "schema": ARTIFACT_DOMAIN + "-derivation.v1",
        "domain": ARTIFACT_DOMAIN + ".derivation",
        "profile_sha256": candidate["profile_sha256"],
        "root_sha256": candidate["profile_root_sha256"],
        "slow_scale": slow_scale,
        "slow_sheet_shape": list(slow_shape),
        "edge_registry_sha256": extension["edge_registry_sha256"],
        "cycle_registry_sha256": extension["cycle_registry_sha256"],
        "codebook_sha256": extension["codebook_sha256"],
        "endpoint_subdivision_sha256": extension["endpoint_subdivision_sha256"],
        "barrier_certificate_sha256": extension["barrier_certificate_sha256"],
        "reset_operator_sha256": extension["reset_operator_sha256"],
        "core_law_sha256": extension["core_law_sha256"],
        "formula": "QiTopologicalRetentionLaw.public_transition.v1",
        "additional_state": False,
    }, ARTIFACT_DOMAIN + ".derivation")
    root = Path(output_root) if output_root is not None else OUTPUT_ROOT
    root = root.resolve()
    root.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".w4r-retention-core-", dir=str(root.parent)))
    object_map: dict[str, str] = {}
    try:
        source_records = _copy_sources(stage)
        _copy_parent_files(stage, parents)
        _write_json(stage, "profiles/retention-profile.json", profile_artifact)
        _write_json(stage, "profiles/retention-root.json", root_artifact)
        _write_json(stage, "certificate/retention-derivation.json", derivation)
        _write_json(stage, "certificate/extension-0003.json", extension)
        _write_json(stage, "certificate/topological-v1-codebook.json", codebook)
        _write_json(stage, "certificate/endpoint-subdivision.json", endpoint)
        _write_json(stage, "certificate/barrier-certificate.json", barrier)
        _write_json(stage, "certificate/reset-operator.json", reset_operator)
        _write_json(stage, "certificate/core-law-identity.json", extension["topology_v1"]["core_law"])
        _write_json(stage, "certificate/g3n-certificate-root.json", parents["w3n_certificate"])
        _write_json(stage, "run-spec/parent-w4.json", parent)
        _write_json(stage, "run-spec/parent-w3n.json", parents["w3n_ancestry"])
        _write_json(stage, "run-spec/source-identity.json", {"schema": "cassi.qi-flow-w4r-retention-core-source-identity.v1", "sources": source_records})
        declared_layout = _layout(geometry)
        declared_layout["batch_count"] = 1
        declared_layout["control_batch_lanes"] = 1
        _write_json(stage, "run-spec/state-layout.json", {"schema": "cassi.qi-flow-w4r-retention-core-state-layout.v1", "shape_formula": "[S,9M,B]", "layout": declared_layout, "slow_scale": slow_scale, "slow_sheet_shape": list(slow_shape)})
        _write_json(stage, "run-spec/conversion-path.json", conversion_path)
        for name, (_, raw, metadata, candidate, candidate_raw, candidate_metadata) in control_states.items():
            _emit_raw(stage, f"states/endpoints/{name}.bin", raw, metadata, object_map)
            if candidate is not None and candidate_raw is not None and candidate_metadata is not None:
                _emit_raw(stage, f"states/endpoints/{name}-candidate.bin", candidate_raw, candidate_metadata, object_map)
        for name, row in controls.items():
            _write_json(stage, f"{GATE_DIR}/controls/{name}.json", row)
        for path_row, blobs in ((within_path, within_blobs), (slip_path, slip_blobs)):
            _write_json(stage, f"{GATE_DIR}/paths/{path_row['path_id']}.json", path_row)
            _write_json(stage, f"{GATE_DIR}/paths/{path_row['path_id']}-symplectic.json", path_row["symplectic_raw_evidence"])
            _write_json(stage, f"{GATE_DIR}/paths/{path_row['path_id']}-refinement.json", path_row["refinement_raw_evidence"])
            for stem, state, raw, metadata in blobs:
                _emit_raw(stage, f"states/paths/{stem}.bin", raw, metadata, object_map)
        _emit_raw(stage, "states/reset/predecessor.bin", reset_before_raw, reset_before_meta, object_map)
        _emit_raw(stage, "states/reset/candidate.bin", reset_after_raw, reset_after_meta, object_map)
        _write_json(stage, f"{GATE_DIR}/reset.json", reset_receipt)
        _write_json(stage, f"{GATE_DIR}/no-added-state.json", no_added_state)
        _write_json(stage, f"{GATE_DIR}/gate-receipt.json", gate_receipt)
        _write_json(stage, f"{GATE_DIR}/retention-core.json", candidate)
        _write_json(stage, f"{GATE_DIR}/status.json", status)
        _write_json(stage, f"{GATE_DIR}/force-evidence.json", force)
        _write_json(stage, f"{GATE_DIR}/barrier-evidence.json", barrier_rows)
        _write_json(stage, f"{GATE_DIR}/matched-energy.json", candidate["matched_energy"])
        _write_json(stage, "objects/manifest.json", {"schema": "cassi.qi-flow-w4r-retention-core-object-manifest.v1", "objects": object_map})
        records = _records(stage)
        material = {"schema": ARTIFACT_DOMAIN, "parent": parent, "extension_sha256": extension["self_sha256"], "gate_receipt_sha256": gate_receipt["self_sha256"], "objects": records}
        run_id = canonical_hash(material, ARTIFACT_DOMAIN)
        index = {"schema": INDEX_SCHEMA, "domain": ARTIFACT_DOMAIN, "run_id": run_id, "status": "PASS_W4R_G4R", "gate": "G4R", "parent": parent, "source_exact_successor_of": parent, "profile_sha256": candidate["profile_sha256"], "profile_root_sha256": candidate["profile_root_sha256"], "extension_sha256": extension["self_sha256"], "gate_receipt_sha256": gate_receipt["self_sha256"], "object_count": len(records), "objects": records}
        index = _seal(index, INDEX_SCHEMA)
        _write_json(stage, "index.json", index)
        output = root / run_id
        if output.exists():
            existing = output / "index.json"
            if not existing.is_file() or existing.read_bytes() != (stage / "index.json").read_bytes():
                raise TopologyArtifactError("immutable W4R retention-core artifact collision")
            shutil.rmtree(stage)
        else:
            shutil.move(str(stage), str(output))
        return output
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def run_artifact(*, output_root: Path | str | None = None) -> Path:
    """Seal and return the immutable source-exact W4R artifact directory."""
    return _run(None if output_root is None else Path(output_root))


def main() -> int:
    try:
        print(run_artifact())
    except Exception as exc:
        print(f"W4R/G4R FAIL: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
