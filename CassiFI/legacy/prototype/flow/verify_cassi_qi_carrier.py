"""Independent W4/G4 verifier for the periodic-FFT2 carrier artifact.

This module intentionally does not import the W4 carrier implementation or its
runner.  It authenticates the artifact first, then decodes every raw state and
replays the seven-stage D/C split with local FFT2 and Wirtinger calculations.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch

from cassi_qi_geometry import PeriodicSheetGeometry, load_w2_geometry_profile
from cassi_qi_profile import canonical_hash, canonical_json_bytes, canonical_json_loads
from cassi_qi_transport import load_w3_transport_profile, w3_stage_schedule

ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT / "_diag" / "cassi-qi-flow-w4-periodic-fft2-final"
PARENT_ROOT = ROOT / "_diag" / "cassi-qi-flow-w3n-periodic-fft2-final"
STATUS = "PASS_W4_G4"
INDEX_SCHEMA = "cassi.qi-flow-w4-periodic-fft2-index.v1"
ARTIFACT_DOMAIN = "cassi.qi-flow-w4-periodic-fft2-artifact.v1"
RAW_DOMAIN = "cassi.qi-flow-w4-raw-state.v1"
RAW_FIXTURE_DOMAIN = "cassi.qi-flow-w4-periodic-fft2.raw-fixture.v1"
RECEIPT_DOMAIN = "cassi.qi-flow-w4-carrier-receipt.v1"
PROFILE_DOMAIN = "cassi.qi-flow-w4-carrier-profile.v1"
ROOT_DOMAIN = "cassi.qi-flow-w4-carrier-root.v1"
DERIVATION_DOMAIN = "cassi.qi-flow-w4-composition-derivation.v1"
SECTION_DOMAIN = "cassi.qi-flow-w4-composition-section.v1"
EXTENSION_DOMAIN = "cassi.qi-flow-w3n-extension.v1"
GUARD_DOMAIN = "cassi.qi-flow-w3n-guard.v1"

CONTROL_IDS = (
    "D-only", "C-only", "D+C", "zero", "uniform", "structured", "scale-local",
    "potential-off", "imbalance-plus", "imbalance-minus", "coordinate-negation",
    "phase-current-reversal", "yang-yin-exchange", "phase-shuffled-equal-energy",
)
SOURCE_PATHS = tuple(sorted((
    "cassi_qi_carrier.py", "run_cassi_qi_carrier.py", "verify_cassi_qi_carrier.py",
    "cassi_qi_numerical_certificate.py", "cassi_qi_field.py", "cassi_qi_geometry.py",
    "cassi_qi_transport.py", "cassi_qi_profile.py",
), key=lambda value: value.encode("utf-8")))


class CarrierVerificationError(ValueError):
    """Raised for any missing, stale, malformed, or physically inconsistent object."""


def _fail(message: str) -> None:
    raise CarrierVerificationError(message)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = canonical_json_loads(path.read_bytes())
    except Exception as exc:
        _fail(f"{path}: non-canonical JSON ({exc})")
    if not isinstance(value, dict):
        _fail(f"{path}: object required")
    return value


def _f64(value: Any, *, name: str) -> float:
    if isinstance(value, bool):
        _fail(f"{name}: boolean is not a finite scalar")
    if isinstance(value, str) and value.startswith("f64:") and len(value) == 20:
        try:
            value = struct.unpack(">d", bytes.fromhex(value[4:]))[0]
        except (ValueError, struct.error):
            _fail(f"{name}: malformed f64 tag")
    try:
        number = float(value)
    except (TypeError, ValueError):
        _fail(f"{name}: scalar required")
    if not math.isfinite(number) or (number == 0.0 and math.copysign(1.0, number) < 0.0):
        _fail(f"{name}: non-finite or negative zero")
    return number


def _sha256(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        _fail(f"{name}: lowercase SHA-256 required")
    return value


def _canonical_hash_body(value: Mapping[str, Any], domain: str, *, self_field: str = "self_sha256") -> str:
    body = dict(value)
    body.pop(self_field, None)
    return canonical_hash(body, domain)


def _check_self(value: Mapping[str, Any], *, path: str, domains: Sequence[str]) -> None:
    actual = value.get("self_sha256")
    _sha256(actual, name=f"{path}.self_sha256")
    if not any(actual == _canonical_hash_body(value, domain) for domain in domains):
        _fail(f"{path}: self hash mismatch")

def _check_content_hash(value: Mapping[str, Any], *, field: str, path: str, domain: str) -> None:
    actual = _sha256(value.get(field), name=f"{path}.{field}")
    body = {key: item for key, item in value.items() if key != field}
    if actual != canonical_hash(body, domain):
        _fail(f"{path}: {field} mismatch")


def _strict_file_inventory(root: Path, index: Mapping[str, Any]) -> None:
    objects = index.get("objects")
    if not isinstance(objects, list) or not objects:
        _fail("index.objects is missing")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in objects:
        if not isinstance(row, Mapping) or set(row) != {"path", "bytes", "sha256"}:
            _fail("index.objects contains a malformed record")
        path = row["path"]
        if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
            _fail("index.objects contains an unsafe path")
        if path in {"index.json", "manifest.json"} or path in seen:
            _fail("index.objects contains an excluded file or duplicate path")
        seen.add(path)
        _sha256(row["sha256"], name=f"index.objects[{path}].sha256")
        if isinstance(row["bytes"], bool) or not isinstance(row["bytes"], int) or row["bytes"] < 0:
            _fail(f"index.objects[{path}].bytes is invalid")
        target = root / path
        if not target.is_file():
            _fail(f"index.objects is missing {path}")
        raw = target.read_bytes()
        if len(raw) != row["bytes"] or _sha(raw) != row["sha256"]:
            _fail(f"index.objects record mismatch for {path}")
        records.append(dict(row))
    actual = {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and p.relative_to(root).as_posix() not in {"index.json", "manifest.json"}
    }
    if actual != seen:
        _fail("artifact has missing or extra unindexed objects")
    if index.get("object_count") not in (None, len(records)):
        _fail("index.object_count mismatch")
    if records != sorted(records, key=lambda row: row["path"].encode("utf-8")):
        _fail("index.objects must be path sorted")


def _manifest_inventory(root: Path, manifest: Mapping[str, Any], index: Mapping[str, Any]) -> None:
    rows = manifest.get("objects")
    if not isinstance(rows, list):
        _fail("manifest.objects is missing")
    if manifest.get("artifact_schema") != INDEX_SCHEMA or manifest.get("inventory_excludes") != ["index.json", "manifest.json"]:
        _fail("manifest inventory contract is stale")
    index_rows = index.get("objects")
    if rows != index_rows:
        _fail("manifest and index inventories differ")
    if manifest.get("object_count") != len(rows):
        _fail("manifest.object_count mismatch")


def _source_body_hash(identity: Mapping[str, Any]) -> str:
    body = {key: value for key, value in identity.items() if key != "source_identity_sha256"}
    return canonical_hash(body, str(identity.get("schema", "")))


def _check_source_identity_hash(identity: Mapping[str, Any]) -> None:
    claimed = _sha256(identity.get("source_identity_sha256"), name="source_identity_sha256")
    if claimed != _source_body_hash(identity):
        _fail("source identity hash mismatch")


def _source_exact(root: Path, identity: Mapping[str, Any], *, expected: Sequence[str]) -> None:
    _check_source_identity_hash(identity)
    sources = identity.get("sources")
    if not isinstance(sources, list):
        _fail("source identity omits sources")
    paths: list[str] = []
    for row in sources:
        if not isinstance(row, Mapping) or set(row) != {"path", "bytes", "sha256"}:
            _fail("malformed source identity row")
        path = row["path"]
        if not isinstance(path, str) or Path(path).is_absolute() or ".." in Path(path).parts:
            _fail("unsafe source identity path")
        paths.append(path)
        _sha256(row["sha256"], name=f"source {path}")
        live = ROOT / path
        snap = root / "sources" / path
        if not live.is_file() or not snap.is_file():
            _fail(f"source identity is missing {path}")
        raw_live, raw_snap = live.read_bytes(), snap.read_bytes()
        if len(raw_live) != row["bytes"] or len(raw_snap) != row["bytes"]:
            _fail(f"source byte count mismatch for {path}")
        if raw_live != raw_snap or _sha(raw_live) != row["sha256"]:
            _fail(f"source snapshot is stale or tampered: {path}")
    if len(paths) != len(set(paths)) or set(paths) != set(expected):
        _fail("source identity has missing or extra sources")
    if paths != sorted(paths, key=lambda value: value.encode("utf-8")):
        _fail("source identity rows must be path sorted")



def _load_w3n_verifier() -> Any:
    try:
        return importlib.import_module("verify_cassi_qi_numerical_certificate")
    except Exception as exc:
        _fail(f"independent W3N verifier unavailable: {exc}")


def _parent_source_exact(parent: Path) -> bool:
    try:
        identity = _read_json(parent / "run-spec" / "source-identity.json")
        _check_source_identity_hash(identity)
        rows = identity.get("sources")
        if not isinstance(rows, list):
            return False
        for row in rows:
            if not isinstance(row, Mapping):
                return False
            path = row.get("path")
            if not isinstance(path, str) or Path(path).is_absolute() or ".." in Path(path).parts:
                return False
            live, snap = ROOT / path, parent / "sources" / path
            if not live.is_file() or not snap.is_file():
                return False
            raw = live.read_bytes()
            expected_bytes = row.get("bytes", row.get("byte_count"))
            if raw != snap.read_bytes() or len(raw) != expected_bytes or _sha(raw) != row.get("sha256"):
                return False
        return True
    except Exception:
        return False


def _w3n_verification_passed(result: Any) -> bool:
    return isinstance(result, Mapping) and result.get("status") == "PASS_W3N_G3N"


def _discover_parent() -> tuple[Path, dict[str, Any], dict[str, Any]]:
    if not PARENT_ROOT.is_dir():
        _fail("W3N periodic-FFT2 parent root is missing")
    verifier = _load_w3n_verifier()
    valid: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []
    for candidate in sorted(p for p in PARENT_ROOT.iterdir() if p.is_dir()):
        try:
            index = _read_json(candidate / "index.json")
            if index.get("status") != "PASS_W3N_G3N" or not _source_exact_parent_index(index, candidate):
                continue
            if candidate.name != index.get("run_id") or not _parent_source_exact(candidate):
                continue
            result = verifier.verify(candidate)
            if not _w3n_verification_passed(result):
                continue
            valid.append((candidate, index, _read_json(candidate / "run-spec" / "source-identity.json")))
        except Exception:
            continue
    if len(valid) != 1:
        _fail(f"expected one current independently verified W3N parent, found {len(valid)}")
    return valid[0]


def _source_exact_parent_index(index: Mapping[str, Any], root: Path) -> bool:
    objects = index.get("objects")
    if not isinstance(objects, list):
        return False
    for row in objects:
        if not isinstance(row, Mapping):
            return False
        path = row.get("path")
        if not isinstance(path, str) or path in {"index.json", "manifest.json"}:
            continue
        target = root / path
        expected_bytes = row.get("bytes", row.get("byte_count"))
        if not target.is_file() or len(target.read_bytes()) != expected_bytes or _sha(target.read_bytes()) != row.get("sha256"):
            return False
    return True

def _decode_raw(path: Path, metadata: Mapping[str, Any], *, shape: tuple[int, int, int]) -> tuple[bytes, torch.Tensor]:
    raw = path.read_bytes()
    dtype = metadata.get("dtype", metadata.get("scalar_dtype", "float64"))
    endian = metadata.get("endianness", metadata.get("byte_order", "little"))
    if dtype not in ("float64", "f64", "torch.float64") or endian not in ("little", "little-endian", "LE"):
        _fail(f"{path}: raw state must be little-endian float64")
    expected_bytes = math.prod(shape) * 8
    if len(raw) != expected_bytes:
        _fail(f"{path}: raw byte count does not match {shape}")
    if len(raw) % 8:
        _fail(f"{path}: raw state is not float64 aligned")
    values = torch.frombuffer(memoryview(raw), dtype=torch.float64).clone().reshape(shape).contiguous()
    if not bool(torch.isfinite(values).all().item()):
        _fail(f"{path}: raw state contains non-finite values")
    if bool(((values == 0.0) & torch.signbit(values)).any().item()):
        _fail(f"{path}: raw state contains negative zero")
    declared_shape = metadata.get("shape")
    if declared_shape not in (list(shape), tuple(shape), f"[S,9M,B]", f"[{shape[0]},{shape[1]},{shape[2]}]"):
        _fail(f"{path}: declared shape mismatch")
    declared_bytes = metadata.get("bytes", metadata.get("byte_count"))
    if declared_bytes is not None and declared_bytes != len(raw):
        _fail(f"{path}: declared byte count mismatch")
    direct = _sha(raw)
    framed = _framed_raw_hash(raw)
    fixture = _raw_fixture_hash(raw)
    raw_sha = metadata.get("sha256", metadata.get("raw_sha256"))
    if raw_sha != direct:
        _fail(f"{path}: raw sha256 mismatch")
    state_sha = metadata.get("state_sha256")
    if state_sha != framed:
        _fail(f"{path}: state hash mismatch")
    fixture_sha = metadata.get("raw_fixture_sha256")
    if fixture_sha is not None and fixture_sha != fixture:
        _fail(f"{path}: raw fixture hash mismatch")
    return raw, values


def _framed_raw_hash(raw: bytes) -> str:
    domain = RAW_DOMAIN.encode("utf-8")
    digest = hashlib.sha256()
    digest.update(len(domain).to_bytes(8, "big")); digest.update(domain)
    digest.update(len(raw).to_bytes(8, "big")); digest.update(raw)
    return digest.hexdigest()


def _raw_fixture_hash(raw: bytes) -> str:
    return canonical_hash({"schema": RAW_FIXTURE_DOMAIN, "raw_sha256": _sha(raw), "raw_byte_count": len(raw)}, RAW_FIXTURE_DOMAIN)


def _active_shapes(geometry: PeriodicSheetGeometry, scales: int) -> tuple[tuple[int, int], ...]:
    shapes = tuple(tuple(int(v) for v in geometry.sheet_shape(s)) for s in range(scales))
    if any(len(shape) != 2 or any(v < 1 for v in shape) for shape in shapes):
        _fail("validated geometry contains an invalid active sheet")
    return shapes


def _coords(state: torch.Tensor, geometry: PeriodicSheetGeometry, *, phi: float, mode_count: int) -> dict[str, tuple[torch.Tensor, ...]]:
    scales, width, batch = state.shape
    if width != 9 * mode_count:
        _fail("raw state width does not match [S,9M,B]")
    result: dict[str, list[torch.Tensor]] = {k: [] for k in ("ey", "ei", "vy", "vi", "d", "c", "vd", "vc")}
    for scale in range(scales):
        ny, nx = geometry.sheet_shape(scale)
        active = geometry.active_site_count(scale)
        if active != ny * nx or active > mode_count:
            _fail(f"scale {scale} active sheet is inconsistent with mode count")
        def grid(component: int) -> torch.Tensor:
            start = component * mode_count
            packed = state[scale, start:start + mode_count]
            if bool(torch.count_nonzero(packed[active:]).item()):
                _fail(f"scale {scale} component {component} has a nonzero inactive tail")
            return packed[:active].reshape(ny, nx, batch).contiguous()
        ey = torch.complex(grid(0), grid(1)); ei = torch.complex(grid(2), grid(3))
        vy = torch.complex(grid(4), grid(5)); vi = torch.complex(grid(6), grid(7))
        d = ey - phi * ei; c = (phi * ey + ei) / (1.0 + phi * phi)
        vd = vy - phi * vi; vc = (phi * vy + vi) / (1.0 + phi * phi)
        for key, value in (("ey", ey), ("ei", ei), ("vy", vy), ("vi", vi), ("d", d), ("c", c), ("vd", vd), ("vc", vc)):
            if not bool(torch.isfinite(value).all().item()):
                _fail(f"scale {scale} coordinate {key} is non-finite")
            result[key].append(value)
    return {key: tuple(value) for key, value in result.items()}


def _pack_coords(state: torch.Tensor, coords: Mapping[str, Sequence[torch.Tensor]], geometry: PeriodicSheetGeometry, *, phi: float, mode_count: int) -> torch.Tensor:
    output = state.clone()
    scales, _, batch = state.shape
    for scale in range(scales):
        d, c, vd, vc = (coords[name][scale] for name in ("d", "c", "vd", "vc"))
        ey = d / (1.0 + phi * phi) + phi * c
        ei = c - phi * d / (1.0 + phi * phi)
        vy = vd / (1.0 + phi * phi) + phi * vc
        vi = vc - phi * vd / (1.0 + phi * phi)
        for component, value in enumerate((ey.real, ey.imag, ei.real, ei.imag, vy.real, vy.imag, vi.real, vi.imag)):
            ny, nx = geometry.sheet_shape(scale); active = geometry.active_site_count(scale)
            if tuple(value.shape) != (ny, nx, batch):
                _fail(f"scale {scale} inverse coordinate shape mismatch")
            start = component * mode_count
            output[scale, start:start + mode_count].zero_()
            output[scale, start:start + active] = value.reshape(active, batch)
    if not bool(torch.isfinite(output).all().item()):
        _fail("inverse coordinate write produced non-finite state")
    return output.contiguous()


def _spectral_half(value: torch.Tensor, velocity: torch.Tensor, geometry: PeriodicSheetGeometry, scale: int, *, duration: float, speed: float, omega: float, gamma: float) -> tuple[torch.Tensor, torch.Tensor, dict[str, int]]:
    ny, nx = geometry.sheet_shape(scale)
    q0 = torch.fft.fft2(value, dim=(-3, -2), norm="ortho").reshape(ny * nx, value.shape[-1])
    v0 = torch.fft.fft2(velocity, dim=(-3, -2), norm="ortho").reshape(ny * nx, velocity.shape[-1])
    ky, kx = geometry.angular_wavenumber_axes(scale)
    k2 = (ky[:, None].square() + kx[None, :].square()).reshape(-1, 1).to(dtype=q0.real.dtype)
    lam = speed * speed * k2 + omega * omega
    alpha = 0.5 * gamma
    discriminant = lam - alpha * alpha
    tolerance = 64.0 * torch.finfo(q0.real.dtype).eps * torch.maximum(lam.abs(), torch.full_like(lam, max(1.0, alpha * alpha)))
    under, over = (discriminant > tolerance).reshape(-1), (discriminant < -tolerance).reshape(-1)
    critical = ~(under | over)
    q1, v1 = torch.empty_like(q0), torch.empty_like(v0)
    decay = math.exp(-alpha * duration)
    if bool(under.any().item()):
        d = discriminant[under].sqrt(); so = torch.sin(d * duration) / d; co = torch.cos(d * duration)
        q, v, l = q0[under], v0[under], lam[under]
        q1[under] = decay * (co * q + so * (v + alpha * q))
        v1[under] = decay * (co * v - so * (alpha * v + l * q))
    if bool(over.any().item()):
        d = (-discriminant[over]).sqrt(); so = torch.sinh(d * duration) / d; co = torch.cosh(d * duration)
        q, v, l = q0[over], v0[over], lam[over]
        q1[over] = decay * (co * q + so * (v + alpha * q))
        v1[over] = decay * (co * v - so * (alpha * v + l * q))
    if bool(critical.any().item()):
        q, v, l = q0[critical], v0[critical], lam[critical]
        q1[critical] = decay * (q + duration * (v + alpha * q))
        v1[critical] = decay * (v - duration * (alpha * v + l * q))
    q = torch.fft.ifft2(q1.reshape(ny, nx, value.shape[-1]), dim=(-3, -2), norm="ortho").contiguous()
    v = torch.fft.ifft2(v1.reshape(ny, nx, velocity.shape[-1]), dim=(-3, -2), norm="ortho").contiguous()
    return q, v, {"underdamped": int(under.sum().item()), "critical": int(critical.sum().item()), "overdamped": int(over.sum().item())}


def _refinement_inject(value: torch.Tensor, geometry: PeriodicSheetGeometry, scale: int, factors: tuple[int, int]) -> torch.Tensor:
    ny, nx = geometry.sheet_shape(scale); fy, fx = ny * factors[0], nx * factors[1]
    coarse = torch.fft.fft2(value, dim=(-3, -2), norm="ortho")
    fine = torch.zeros((fy, fx, value.shape[-1]), dtype=torch.complex128)
    sy, sx = geometry.frequency_axes(scale)
    for y, signed_y in enumerate(sy.tolist()):
        for x, signed_x in enumerate(sx.tolist()):
            fine[signed_y % fy, signed_x % fx] = coarse[y, x]
    return (torch.fft.ifft2(fine, dim=(-3, -2), norm="ortho") * math.sqrt(float(factors[0] * factors[1]))).contiguous()


def _refinement_restrict(value: torch.Tensor, geometry: PeriodicSheetGeometry, scale: int, factors: tuple[int, int]) -> torch.Tensor:
    ny, nx = geometry.sheet_shape(scale); fy, fx = ny * factors[0], nx * factors[1]
    fine = torch.fft.fft2(value, dim=(-3, -2), norm="ortho")
    coarse = torch.empty((ny, nx, value.shape[-1]), dtype=torch.complex128)
    sy, sx = geometry.frequency_axes(scale)
    for y, signed_y in enumerate(sy.tolist()):
        for x, signed_x in enumerate(sx.tolist()):
            coarse[y, x] = fine[signed_y % fy, signed_x % fx]
    return (torch.fft.ifft2(coarse, dim=(-3, -2), norm="ortho") / math.sqrt(float(factors[0] * factors[1]))).contiguous()



def _nonlinear(value: torch.Tensor, geometry: PeriodicSheetGeometry, scale: int, kappa: float) -> torch.Tensor:
    if kappa == 0.0:
        return torch.zeros_like(value)
    sheet = geometry.profile.payload["geometry_contract"]["per_scale_sheets"][scale]
    factors = tuple(int(v) for v in sheet["oversampling"]["factors_yx"])
    fine = _refinement_inject(value, geometry, scale, factors)
    return (-kappa * _refinement_restrict(fine.abs().square() * fine, geometry, scale, factors)).contiguous()


def _force_summary(force: torch.Tensor, area: float, scale: int) -> dict[str, Any]:
    return {"scale": scale, "shape": list(force.shape), "max_abs": float(force.abs().amax().item()), "l2_metric": float((force.abs().square().sum() * area).sqrt().item()), "sum_re": float(force.real.sum().item() * area)}


def _composition(values: Mapping[str, Sequence[torch.Tensor]], geometry: PeriodicSheetGeometry, scale: int, *, phi: float, beta: float, epsilon_ref: float, omega: float, w_d: float, w_c: float, enabled: bool) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, float]:
    ey, ei, c = values["ey"][scale], values["ei"][scale], values["c"][scale]
    epsilon = ey.abs().square() - phi * ei.abs().square()
    if not enabled:
        return torch.zeros_like(c), torch.zeros_like(c), epsilon, 0.0
    tanh = torch.tanh(epsilon / epsilon_ref)
    prime = (1.0 - tanh.square()) / epsilon_ref
    c2 = c.abs().square(); omega2 = omega * omega
    d_eps = w_d * (ey + phi * phi * ei)
    c_eps = phi * (ey - ei)
    force_d = (-(w_c / w_d) * omega2 * beta * prime * c2 * d_eps).contiguous()
    force_c = (-omega2 * beta * (tanh * c + prime * c2 * c_eps)).contiguous()
    area = float(geometry.cell_area_m2(scale))
    potential = float((0.5 * w_c * omega2 * beta * tanh * c2).real.sum().item() * area)
    return force_d, force_c, epsilon, potential


def _energy(values: Mapping[str, Sequence[torch.Tensor]], geometry: PeriodicSheetGeometry, scale: int, *, c_d: float, omega_d: float, gamma_d: float, kappa_d: float, c_c: float, omega_c: float, gamma_c: float, kappa_c: float, w_d: float, w_c: float) -> tuple[dict[str, Any], float]:
    del gamma_d, gamma_c
    area = float(geometry.cell_area_m2(scale))
    rows: dict[str, Any] = {}
    total = 0.0
    for key, pos, vel, speed, omega, kappa, weight in (("D", values["d"][scale], values["vd"][scale], c_d, omega_d, kappa_d, w_d), ("C", values["c"][scale], values["vc"][scale], c_c, omega_c, kappa_c, w_c)):
        grad_y = torch.fft.ifft2(torch.fft.fft2(pos, dim=(-3, -2), norm="ortho") * (1j * geometry.angular_wavenumber_axes(scale)[0][:, None, None]), dim=(-3, -2), norm="ortho")
        grad_x = torch.fft.ifft2(torch.fft.fft2(pos, dim=(-3, -2), norm="ortho") * (1j * geometry.angular_wavenumber_axes(scale)[1][None, :, None]), dim=(-3, -2), norm="ortho")
        density = weight * (0.5 * vel.abs().square() + 0.5 * speed * speed * (grad_x.abs().square() + grad_y.abs().square()) + 0.5 * omega * omega * pos.abs().square() + 0.25 * kappa * pos.abs().square().square())
        current = -weight * speed * speed * torch.imag(torch.conj(pos).unsqueeze(0) * torch.stack((grad_x, grad_y)))
        phase = weight * torch.imag(torch.conj(pos) * vel)
        rows[key] = {"energy": float(density.real.sum().item() * area), "phase_charge": float(phase.real.sum().item() * area), "current_max": float(current.abs().amax().item()), "current_integral_x": float(current[0].sum().item() * area), "current_integral_y": float(current[1].sum().item() * area), "amplitude_max": float(pos.abs().amax().item())}
        total += rows[key]["energy"]
    rows["energy"] = rows["D"]["energy"] + rows["C"]["energy"]
    rows["phase_charge"] = rows["D"]["phase_charge"] + rows["C"]["phase_charge"]
    rows["current_max"] = max(rows["D"]["current_max"], rows["C"]["current_max"])
    rows["current_integral_x"] = rows["D"]["current_integral_x"] + rows["C"]["current_integral_x"]
    rows["current_integral_y"] = rows["D"]["current_integral_y"] + rows["C"]["current_integral_y"]
    return rows, total


def _carrier_energy(values: Mapping[str, Sequence[torch.Tensor]], geometry: PeriodicSheetGeometry, params: Mapping[str, Any], *, coupled: bool = True) -> float:
    total = 0.0
    for scale in range(params["scale_count"]):
        _, base = _energy(values, geometry, scale, c_d=params["c_d"][scale], omega_d=params["omega_d"][scale], gamma_d=params["gamma_d"][scale], kappa_d=params["kappa_d"][scale], c_c=params["c_c"][scale], omega_c=params["omega_c"][scale], gamma_c=params["gamma_c"][scale], kappa_c=params["kappa_c"][scale], w_d=params["w_d"], w_c=params["w_c"])
        potential = _composition(values, geometry, scale, phi=params["phi"], beta=params["beta"][scale], epsilon_ref=params["epsilon_ref"][scale], omega=params["omega_c"][scale], w_d=params["w_d"], w_c=params["w_c"], enabled=coupled)[3]
        total += base + potential
    return total
def _energy_parts(values: Mapping[str, Sequence[torch.Tensor]], geometry: PeriodicSheetGeometry, params: Mapping[str, Any], *, enabled: bool) -> tuple[float, float, tuple[float, ...]]:
    base_total = 0.0
    potential_by_scale: list[float] = []
    for scale in range(params["scale_count"]):
        _, base = _energy(
            values,
            geometry,
            scale,
            c_d=params["c_d"][scale],
            omega_d=params["omega_d"][scale],
            gamma_d=params["gamma_d"][scale],
            kappa_d=params["kappa_d"][scale],
            c_c=params["c_c"][scale],
            omega_c=params["omega_c"][scale],
            gamma_c=params["gamma_c"][scale],
            kappa_c=params["kappa_c"][scale],
            w_d=params["w_d"],
            w_c=params["w_c"],
        )
        base_total += base
        potential_by_scale.append(_composition(
            values,
            geometry,
            scale,
            phi=params["phi"],
            beta=params["beta"][scale],
            epsilon_ref=params["epsilon_ref"][scale],
            omega=params["omega_c"][scale],
            w_d=params["w_d"],
            w_c=params["w_c"],
            enabled=enabled,
        )[3])
    return base_total, sum(potential_by_scale), tuple(potential_by_scale)
def _verify_epsilon_summary(actual: Any, values: Mapping[str, Sequence[torch.Tensor]], geometry: PeriodicSheetGeometry, params: Mapping[str, Any], *, name: str) -> None:
    if not isinstance(actual, Mapping) or set(actual) != {"per_scale"} or not isinstance(actual.get("per_scale"), list) or len(actual["per_scale"]) != params["scale_count"]:
        _fail(f"{name} epsilon summary is malformed")
    for scale, row in enumerate(actual["per_scale"]):
        epsilon = values["ey"][scale].abs().square() - params["phi"] * values["ei"][scale].abs().square()
        expected = {
            "scale": scale,
            "batch_lanes": int(epsilon.shape[-1]),
            "epsilon_min": float(epsilon.min().item()),
            "epsilon_max": float(epsilon.max().item()),
            "epsilon_sum": float(epsilon.sum().item()),
            "potential": _composition(
                values,
                geometry,
                scale,
                phi=params["phi"],
                beta=params["beta"][scale],
                epsilon_ref=params["epsilon_ref"][scale],
                omega=params["omega_c"][scale],
                w_d=params["w_d"],
                w_c=params["w_c"],
                enabled=True,
            )[3],
        }
        if not isinstance(row, Mapping) or set(row) != set(expected):
            _fail(f"{name} epsilon summary scale {scale} is malformed")
        for key, value in expected.items():
            if key in {"scale", "batch_lanes"}:
                if row.get(key) != value:
                    _fail(f"{name} epsilon summary {key} drifted at scale {scale}")
            else:
                _close(row.get(key), value, name=f"{name} epsilon summary {key}[{scale}]")





def _replay(initial: torch.Tensor, *, geometry: PeriodicSheetGeometry, params: Mapping[str, Any], duration: float, enabled: bool) -> tuple[torch.Tensor, dict[str, Any]]:
    scales, _, _ = initial.shape
    phi, w_d, w_c = params["phi"], params["w_d"], params["w_c"]
    values = _coords(initial, geometry, phi=phi, mode_count=params["mode_count"])

    def kick(current: Mapping[str, Sequence[torch.Tensor]]) -> tuple[dict[str, tuple[torch.Tensor, ...]], dict[str, Any]]:
        d_forces: list[torch.Tensor] = []
        c_forces: list[torch.Tensor] = []
        nonlinear_d: list[torch.Tensor] = []
        nonlinear_c: list[torch.Tensor] = []
        eps: list[torch.Tensor] = []
        potentials: list[float] = []
        for s in range(scales):
            comp_d, comp_c, epsilon, potential = _composition(
                current, geometry, s, phi=phi, beta=params["beta"][s],
                epsilon_ref=params["epsilon_ref"][s], omega=params["omega_c"][s],
                w_d=w_d, w_c=w_c, enabled=enabled,
            )
            nd = _nonlinear(current["d"][s], geometry, s, params["kappa_d"][s])
            nc = _nonlinear(current["c"][s], geometry, s, params["kappa_c"][s])
            d_forces.append((nd + comp_d).contiguous())
            c_forces.append((nc + comp_c).contiguous())
            nonlinear_d.append(nd); nonlinear_c.append(nc)
            eps.append(epsilon); potentials.append(potential)
        updated = dict(current)
        updated["vd"] = tuple((current["vd"][s] + 0.5 * duration * d_forces[s]).contiguous() for s in range(scales))
        updated["vc"] = tuple((current["vc"][s] + 0.5 * duration * c_forces[s]).contiguous() for s in range(scales))
        return updated, {
            "force_D": tuple(_force_summary(v, float(geometry.cell_area_m2(s)), s) for s, v in enumerate(d_forces)),
            "force_C": tuple(_force_summary(v, float(geometry.cell_area_m2(s)), s) for s, v in enumerate(c_forces)),
            "nonlinear_D": tuple(_force_summary(v, float(geometry.cell_area_m2(s)), s) for s, v in enumerate(nonlinear_d)),
            "nonlinear_C": tuple(_force_summary(v, float(geometry.cell_area_m2(s)), s) for s, v in enumerate(nonlinear_c)),
            "epsilon": tuple({"scale": s, "min": float(v.real.amin().item()), "max": float(v.real.amax().item())} for s, v in enumerate(eps)),
            "U_per_scale": tuple(potentials),
            "force_D_sum_re": sum(v["sum_re"] for v in (_force_summary(f, float(geometry.cell_area_m2(s)), s) for s, f in enumerate(d_forces))),
            "force_C_sum_re": sum(v["sum_re"] for v in (_force_summary(f, float(geometry.cell_area_m2(s)), s) for s, f in enumerate(c_forces))),
        }

    state = _pack_coords(initial, values, geometry, phi=phi, mode_count=params["mode_count"])
    values, first_force = kick(values)
    state = _pack_coords(state, values, geometry, phi=phi, mode_count=params["mode_count"])
    state_first_kick = state
    values = _coords(state, geometry, phi=phi, mode_count=params["mode_count"])

    branches_first: list[dict[str, Any]] = []
    d: list[torch.Tensor] = []; c: list[torch.Tensor] = []; vd: list[torch.Tensor] = []; vc: list[torch.Tensor] = []
    for s in range(scales):
        dd, vv, bd = _spectral_half(values["d"][s], values["vd"][s], geometry, s, duration=0.5 * duration, speed=params["c_d"][s], omega=params["omega_d"][s], gamma=params["gamma_d"][s])
        cc, ww, bc = _spectral_half(values["c"][s], values["vc"][s], geometry, s, duration=0.5 * duration, speed=params["c_c"][s], omega=params["omega_c"][s], gamma=params["gamma_c"][s])
        d.append(dd); c.append(cc); vd.append(vv); vc.append(ww); branches_first.append({"D": bd, "C": bc})
    values = {**values, "d": tuple(d), "c": tuple(c), "vd": tuple(vd), "vc": tuple(vc)}
    state = _pack_coords(state, values, geometry, phi=phi, mode_count=params["mode_count"])
    state_first_spectral = state
    values = _coords(state, geometry, phi=phi, mode_count=params["mode_count"])

    branches_second: list[dict[str, Any]] = []
    d = []; c = []; vd = []; vc = []
    for s in range(scales):
        dd, vv, bd = _spectral_half(values["d"][s], values["vd"][s], geometry, s, duration=0.5 * duration, speed=params["c_d"][s], omega=params["omega_d"][s], gamma=params["gamma_d"][s])
        cc, ww, bc = _spectral_half(values["c"][s], values["vc"][s], geometry, s, duration=0.5 * duration, speed=params["c_c"][s], omega=params["omega_c"][s], gamma=params["gamma_c"][s])
        d.append(dd); c.append(cc); vd.append(vv); vc.append(ww); branches_second.append({"D": bd, "C": bc})
    values = {**values, "d": tuple(d), "c": tuple(c), "vd": tuple(vd), "vc": tuple(vc)}
    state = _pack_coords(state, values, geometry, phi=phi, mode_count=params["mode_count"])
    state_second_spectral = state
    values = _coords(state, geometry, phi=phi, mode_count=params["mode_count"])
    values, second_force = kick(values)
    state = _pack_coords(state, values, geometry, phi=phi, mode_count=params["mode_count"])
    if bool(torch.count_nonzero(state[:, 8 * params["mode_count"]:9 * params["mode_count"]]).item()):
        _fail("replay altered epsilon2_ema component")
    return state, {
        "first_force": first_force,
        "second_force": second_force,
        "branches_first": branches_first,
        "branches_second": branches_second,
        "values": values,
        "states": {
            "predecessor": initial,
            "post_first_kick": state_first_kick,
            "post_first_spectral": state_first_spectral,
            "post_second_spectral": state_second_spectral,
            "candidate": state,
        },
    }


def _find_state_rows(node: Any, *, control: str = "", out: dict[str, dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    if out is None: out = {}
    if isinstance(node, Mapping):
        current = node.get("control_id", node.get("control", node.get("name", control)))
        if not isinstance(current, str) or current not in CONTROL_IDS:
            current = control
        if current in CONTROL_IDS:
            row = out.setdefault(current, {})
            for role in ("predecessor", "candidate"):
                for key in (role, f"{role}_state", f"{role}_raw", f"{role}_fixture"):
                    if key in node:
                        row[role] = node[key]
                for key in (f"{role}_path", f"{role}_raw_path", f"{role}_fixture_path"):
                    if key in node:
                        row[role] = {"path": node[key], **({"sha256": node.get(f"{role}_sha256")} if node.get(f"{role}_sha256") is not None else {})}
            for key, value in node.items():
                if isinstance(key, str) and key.endswith("_path") and isinstance(value, str) and value.endswith((".f64le", ".bin")):
                    if "predecessor" in key: row["predecessor"] = {"path": value}
                    elif "candidate" in key: row["candidate"] = {"path": value}
        for value in node.values(): _find_state_rows(value, control=current if isinstance(current, str) and current in CONTROL_IDS else control, out=out)
    elif isinstance(node, list):
        for value in node: _find_state_rows(value, control=control, out=out)
    return out


def _path_ref(value: Any) -> tuple[str, dict[str, Any]]:
    if isinstance(value, str): return value, {}
    if isinstance(value, Mapping):
        path = value.get("path", value.get("file", value.get("object")))
        if isinstance(path, str): return path, dict(value)
    _fail("state row omits a raw path")


def _close(actual: Any, expected: Any, *, name: str, rtol: float = 2e-11, atol: float = 2e-12) -> None:
    actual = _numeric_tree(actual)
    expected = _numeric_tree(expected)
    if isinstance(actual, list) or isinstance(expected, list):
        if not (isinstance(actual, list) and isinstance(expected, list) and len(actual) == len(expected)):
            _fail(f"{name}: value mismatch")
        for index, (item_actual, item_expected) in enumerate(zip(actual, expected)):
            _close(item_actual, item_expected, name=f"{name}[{index}]", rtol=rtol, atol=atol)
        return
    try:
        a, e = float(actual), float(expected)
    except (TypeError, ValueError):
        if actual != expected: _fail(f"{name}: value mismatch")
        return
    if not math.isfinite(a) or abs(a - e) > atol + rtol * max(1.0, abs(e)):
        _fail(f"{name}: value mismatch")

def _numeric_tree(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("f64:"):
        return _f64(value, name="numeric tree")
    if isinstance(value, Mapping):
        return {key: _numeric_tree(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_numeric_tree(item) for item in value]
    return value



def _match_summaries(receipt: Mapping[str, Any], replay: Mapping[str, Any], *, name: str) -> None:
    for force_key in ("force_D", "force_C", "nonlinear_D", "nonlinear_C"):
        actual = receipt.get(force_key); expected = replay.get(force_key)
        if not isinstance(actual, list) or not isinstance(expected, Sequence) or len(actual) != len(expected):
            _fail(f"{name}: missing {force_key} evidence")
        for s, (a, e) in enumerate(zip(actual, expected, strict=True)):
            if not isinstance(a, Mapping): _fail(f"{name}: malformed {force_key}[{s}]")
            for key in ("scale", "shape", "max_abs", "l2_metric", "sum_re"):
                if key not in a: _fail(f"{name}: missing {force_key}[{s}].{key}")
                if key in ("scale", "shape"):
                    if a[key] != e[key]: _fail(f"{name}: {force_key}[{s}] {key} mismatch")
                else: _close(a[key], e[key], name=f"{name}.{force_key}[{s}].{key}")
    for key in ("force_D_sum_re", "force_C_sum_re"):
        _close(receipt.get(key), replay[key], name=f"{name}.{key}")


def _verify_energy_and_ledger(
    result: Mapping[str, Any],
    receipt: Mapping[str, Any],
    evidence: Mapping[str, Any],
    *,
    predecessor: torch.Tensor,
    candidate: torch.Tensor,
    geometry: PeriodicSheetGeometry,
    params: Mapping[str, Any],
    enabled: bool,
    registered_bound: float,
) -> None:
    state_map = evidence.get("states")
    if not isinstance(state_map, Mapping) or set(state_map) != {"predecessor", "post_first_kick", "post_first_spectral", "post_second_spectral", "candidate"}:
        _fail("replay omitted independently checked stage states")
    if state_map["predecessor"] is not predecessor or (not torch.equal(state_map["candidate"], candidate) and not bool(torch.allclose(state_map["candidate"], candidate, rtol=0.0, atol=2.0e-13))):
        _fail("replay stage state identities drifted")
    values_by_stage: dict[str, dict[str, tuple[torch.Tensor, ...]]] = {}
    for name, state in state_map.items():
        if not isinstance(state, torch.Tensor) or tuple(state.shape) != tuple(predecessor.shape):
            _fail(f"replay stage {name} has an invalid state")
        values_by_stage[name] = _coords(state, geometry, phi=params["phi"], mode_count=params["mode_count"])
    full_parts: dict[str, tuple[float, float, tuple[float, ...]]] = {
        name: _energy_parts(values, geometry, params, enabled=True)
        for name, values in values_by_stage.items()
    }
    ledger_parts: dict[str, tuple[float, float, tuple[float, ...]]] = {
        name: _energy_parts(values, geometry, params, enabled=enabled)
        for name, values in values_by_stage.items()
    }
    stage_energy = {
        name: full_parts[name][0] + full_parts[name][1]
        for name in full_parts
    }
    expected_stage_energy = (
        (stage_energy["predecessor"], stage_energy["predecessor"], 0.0),
        (stage_energy["predecessor"], stage_energy["post_first_kick"], stage_energy["post_first_kick"] - stage_energy["predecessor"]),
        (stage_energy["post_first_kick"], stage_energy["post_first_spectral"], stage_energy["post_first_spectral"] - stage_energy["post_first_kick"]),
        (stage_energy["post_first_spectral"], stage_energy["post_first_spectral"], 0.0),
        (stage_energy["post_first_spectral"], stage_energy["post_second_spectral"], stage_energy["post_second_spectral"] - stage_energy["post_first_spectral"]),
        (stage_energy["post_second_spectral"], stage_energy["candidate"], stage_energy["candidate"] - stage_energy["post_second_spectral"]),
        (stage_energy["candidate"], stage_energy["candidate"], 0.0),
    )
    stage_evidence = receipt.get("stage_evidence")
    if not isinstance(stage_evidence, list) or len(stage_evidence) != len(expected_stage_energy):
        _fail("receipt stage energy evidence is missing")
    expected_modes = ("active", "active", "active", "inactive-w3-placeholder", "active", "active", "active")
    for ordinal, (row, expected) in enumerate(zip(stage_evidence, expected_stage_energy, strict=True), 1):
        if not isinstance(row, Mapping) or row.get("mode") != expected_modes[ordinal - 1]:
            _fail(f"receipt stage {ordinal} mode drifted")
        for key, value in zip(("energy_before", "energy_after", "work"), expected, strict=True):
            _close(row.get(key), value, name=f"receipt stage {ordinal} {key}")
    predecessor_base, predecessor_full_u, _ = full_parts["predecessor"]
    first_full_base, first_full_u, _ = full_parts["post_first_spectral"]
    second_full_base, second_full_u, _ = full_parts["post_second_spectral"]
    candidate_base, candidate_full_u, _ = full_parts["candidate"]
    _, predecessor_u, predecessor_per_scale = ledger_parts["predecessor"]
    _, first_u, first_per_scale = ledger_parts["post_first_spectral"]
    _, second_u, second_per_scale = ledger_parts["post_second_spectral"]
    _, candidate_u, candidate_per_scale = ledger_parts["candidate"]
    composition = receipt.get("composition")
    if not isinstance(composition, Mapping):
        _fail("receipt composition ledger is missing")
    composition_keys = {
        "base_energy_pre", "base_energy_post", "U_pre", "U_D_path", "U_center", "U_C_path",
        "U_post", "Delta_U", "W_D", "W_center", "W_C", "coordinate_work_closure",
        "registered_coordinate_work_bound", "wave_energy_delta", "total_coupled_closure",
        "registered_total_coupled_integrator_bound", "force_D_sum_re", "force_C_sum_re",
        "slow_carrier_bias_re", "per_scale_U_pre", "per_scale_U_post",
    }
    if set(composition) != composition_keys:
        _fail("receipt composition ledger has missing or extra fields")
    composition_expected = {
        "base_energy_pre": predecessor_base,
        "base_energy_post": candidate_base,
        "U_pre": predecessor_u,
        "U_D_path": first_u,
        "U_center": first_u,
        "U_C_path": second_u,
        "U_post": candidate_u,
        "Delta_U": second_u - predecessor_u,
        "W_D": -(first_u - predecessor_u),
        "W_center": -(first_u - first_u),
        "W_C": -(second_u - first_u),
        "coordinate_work_closure": -(first_u - predecessor_u) - (second_u - first_u) + (second_u - predecessor_u),
        "registered_coordinate_work_bound": registered_bound,
        "wave_energy_delta": candidate_base - predecessor_base,
        "total_coupled_closure": (candidate_base + candidate_full_u) - (predecessor_base + predecessor_full_u) - (candidate_base - predecessor_base),
        "registered_total_coupled_integrator_bound": registered_bound,
    }
    second_force = evidence["second_force"]
    composition_expected["force_D_sum_re"] = second_force["force_D_sum_re"]
    composition_expected["force_C_sum_re"] = second_force["force_C_sum_re"]
    composition_expected["slow_carrier_bias_re"] = second_force["force_C"][-1]["sum_re"]
    for key, expected in composition_expected.items():
        _close(composition.get(key), expected, name=f"receipt.composition.{key}")
    for key, expected in (("per_scale_U_pre", predecessor_per_scale), ("per_scale_U_post", second_per_scale)):
        actual = composition.get(key)
        if not isinstance(actual, list) or len(actual) != len(expected):
            _fail(f"receipt.composition.{key} is malformed")
        for scale, (actual_value, expected_value) in enumerate(zip(actual, expected, strict=True)):
            _close(actual_value, expected_value, name=f"receipt.composition.{key}[{scale}]")

    diagnostics = receipt.get("diagnostics")
    if not isinstance(diagnostics, Mapping):
        _fail("receipt diagnostics are missing")
    diagnostics_expected = {
        "energy_pre": predecessor_base + predecessor_full_u,
        "energy_post": candidate_base + candidate_full_u,
        "damping_work": candidate_base - predecessor_base,
        "energy_closure": (candidate_base + candidate_full_u) - (predecessor_base + predecessor_full_u) - (candidate_base - predecessor_base),
    }
    for key, expected in diagnostics_expected.items():
        _close(diagnostics.get(key), expected, name=f"receipt.diagnostics.{key}")
    _close(result.get("candidate_energy"), candidate_base + candidate_full_u, name="control candidate_energy")

    ledger = result.get("ledger")
    if not isinstance(ledger, Mapping) or ledger.get("schema") != "cassi.qi-flow-w4-periodic-fft2-ledger.v1":
        _fail("control ledger is missing or stale")
    ledger_keys = {
        "schema", "U_D", "U_C", "U_comp", "U_total", "U_comp_pre", "U_comp_post",
        "metric_gradient_work", "per_scale_U_pre", "per_scale_U_post",
    }
    if set(ledger) != ledger_keys:
        _fail("control ledger has missing or extra fields")
    ledger_expected = {
        "U_D": composition_expected["U_D_path"],
        "U_C": composition_expected["U_C_path"],
        "U_comp": composition_expected["U_post"],
        "U_total": composition_expected["base_energy_post"] + composition_expected["U_post"],
        "U_comp_pre": composition_expected["U_pre"],
        "U_comp_post": composition_expected["U_post"],
        "per_scale_U_pre": predecessor_per_scale,
        "per_scale_U_post": second_per_scale,
    }
    for key, expected in ledger_expected.items():
        actual = ledger.get(key)
        if isinstance(expected, tuple):
            if not isinstance(actual, list) or len(actual) != len(expected):
                _fail(f"control ledger {key} is malformed")
            for scale, (actual_value, expected_value) in enumerate(zip(actual, expected, strict=True)):
                _close(actual_value, expected_value, name=f"control.ledger.{key}[{scale}]")
        else:
            _close(actual, expected, name=f"control.ledger.{key}")
    metric = ledger.get("metric_gradient_work")
    metric_keys = {
        "W_D", "W_center", "W_C", "Delta_U_comp", "coordinate_work_closure",
        "registered_coordinate_work_bound", "total_coupled_closure",
        "registered_total_coupled_integrator_bound", "force_D_sum_re", "force_C_sum_re",
    }
    if not isinstance(metric, Mapping) or set(metric) != metric_keys:
        _fail("control metric-gradient ledger is incomplete")
    metric_expected = {
        "W_D": composition_expected["W_D"],
        "W_center": composition_expected["W_center"],
        "W_C": composition_expected["W_C"],
        "Delta_U_comp": composition_expected["Delta_U"],
        "coordinate_work_closure": composition_expected["coordinate_work_closure"],
        "registered_coordinate_work_bound": registered_bound,
        "total_coupled_closure": composition_expected["total_coupled_closure"],
        "registered_total_coupled_integrator_bound": registered_bound,
        "force_D_sum_re": composition_expected["force_D_sum_re"],
        "force_C_sum_re": composition_expected["force_C_sum_re"],
    }
    for key, expected in metric_expected.items():
        _close(metric.get(key), expected, name=f"control.ledger.metric_gradient_work.{key}")


def _verify_schedule(schedule: Mapping[str, Any], *, duration: float, geometry: PeriodicSheetGeometry) -> None:
    stages = schedule.get("stages")
    if not isinstance(stages, list) or len(stages) != 7 or schedule.get("substeps", 7) != 7:
        _fail("W4 schedule must contain exactly seven stages")
    expected_names = ("preflight", "first_local_force_velocity_half_kick", "first_analytic_damped_spectral_half_propagation", "centered_conversion_placeholder", "second_analytic_damped_spectral_half_propagation", "second_local_force_velocity_half_kick", "precommit")
    expected_modes = ("active", "active", "active", "inactive-w3", "active", "active", "active")
    for ordinal, row in enumerate(stages, 1):
        if not isinstance(row, Mapping) or row.get("ordinal") != ordinal or row.get("name") != expected_names[ordinal - 1] or row.get("mode") != expected_modes[ordinal - 1]:
            _fail(f"W4 schedule stage {ordinal} drifted")
        expected_duration = 0.0 if ordinal in (1, 7) else duration if ordinal == 4 else 0.5 * duration
        _close(row.get("duration_s"), expected_duration, name=f"schedule stage {ordinal} duration", rtol=0.0, atol=0.0)
    if schedule.get("h_s") is not None:
        _close(schedule["h_s"], duration, name="schedule h_s", rtol=0.0, atol=0.0)
    if schedule.get("scale_count") is not None and schedule["scale_count"] != int(geometry.profile.base_profile.state_layout["scale_count"]):
        _fail("schedule scale count drifted")
    if schedule.get("active_sheet") != int(geometry.profile.base_profile.payload["retention"]["slow_scale"]):
        _fail("schedule active sheet drifted")
def _control_result_path(name: str, batch: int) -> str:
    safe = name.replace("+", "-plus-").replace("/", "-").replace(" ", "-")
    return f"gates/g04-carrier/controls/{safe}/batch-{batch}.json"


def _load_indexed_control_result(root: Path, name: str, batch: int, index_row: Any) -> tuple[dict[str, Any], str]:
    if not isinstance(index_row, Mapping) or set(index_row) != {"path", "sha256"}:
        _fail(f"control {name} batch {batch} index row is malformed")
    expected_path = _control_result_path(name, batch)
    path = index_row.get("path")
    if not isinstance(path, str) or path != expected_path or Path(path).is_absolute() or ".." in Path(path).parts:
        _fail(f"control {name} batch {batch} index path is invalid")
    digest = _sha256(index_row.get("sha256"), name=f"control {name} batch {batch} index sha256")
    target = root / path
    if not target.is_file():
        _fail(f"control {name} batch {batch} indexed result is missing")
    raw = target.read_bytes()
    if _sha(raw) != digest:
        _fail(f"control {name} batch {batch} indexed result hash mismatch")
    result = _read_json(target)
    try:
        canonical = canonical_json_bytes(result)
    except Exception as exc:
        _fail(f"control {name} batch {batch} indexed result is not canonical ({exc})")
    if raw != canonical or _sha(canonical) != digest:
        _fail(f"control {name} batch {batch} indexed result is not canonical JSON bytes")
    return result, path


def _load_state_metadata(root: Path, runtime: Mapping[str, Any], controls: Mapping[str, Any], candidate: Mapping[str, Any], *, shape_prefix: tuple[int, int], batch_limit: int) -> dict[str, dict[str, dict[str, Any]]]:
    del candidate
    runtime_controls = runtime.get("controls")
    if not isinstance(runtime_controls, Mapping) or set(runtime_controls) != set(CONTROL_IDS):
        _fail("runtime controls are missing or contain extras")
    if runtime_controls != controls:
        _fail("runtime controls differ from compact control index")
    refs: dict[str, dict[str, dict[str, Any]]] = {}
    raw_files = {p.relative_to(root).as_posix() for p in root.rglob("*.f64le") if p.is_file()}
    referenced: set[str] = set()
    for control in CONTROL_IDS:
        control_row = controls[control]
        if not isinstance(control_row, Mapping) or set(control_row) != {"schema", "name", "batch_lanes", "potential_enabled", "batch_index"} or control_row.get("schema") != "cassi.qi-flow-w4-periodic-fft2-control.v1" or control_row.get("name") != control or control_row.get("potential_enabled") is not (control != "potential-off") or control_row.get("batch_lanes") != list(range(1, batch_limit + 1)):
            _fail(f"runtime control {control} is malformed")
        batch_index = control_row.get("batch_index")
        expected_batches = {str(batch) for batch in range(1, batch_limit + 1)}
        if not isinstance(batch_index, Mapping) or set(batch_index) != expected_batches:
            _fail(f"control {control} has missing or extra indexed batches")
        refs[control] = {}
        for batch_name in sorted(batch_index, key=lambda value: int(value)):
            batch = int(batch_name)
            result, result_path = _load_indexed_control_result(root, control, batch, batch_index[batch_name])
            if result.get("schema") != "cassi.qi-flow-w4-periodic-fft2-control.v1" or result.get("name") != control or result.get("potential_enabled") is not (control != "potential-off") or result.get("batch_lanes") != batch:
                _fail(f"control {control} batch {batch} detailed result metadata drifted")
            refs[control][batch_name] = {"result": result, "path": result_path}
            for role in ("predecessor", "candidate"):
                metadata = result.get(role)
                if not isinstance(metadata, Mapping):
                    _fail(f"control {control} batch {batch} omits {role} metadata")
                path = metadata.get("path")
                if not isinstance(path, str) or Path(path).is_absolute() or ".." in Path(path).parts or path not in raw_files:
                    _fail(f"control {control} batch {batch} has invalid {role} path")
                declared_shape = metadata.get("shape")
                if not isinstance(declared_shape, list) or len(declared_shape) != 3 or any(isinstance(v, bool) or not isinstance(v, int) for v in declared_shape):
                    _fail(f"control {control} batch {batch} has invalid {role} shape")
                shape = tuple(int(v) for v in declared_shape)
                if shape[:2] != shape_prefix or shape[2] != batch:
                    _fail(f"control {control} batch {batch} {role} shape is not [S,9M,B]")
                raw, tensor = _decode_raw(root / path, metadata, shape=shape)
                refs[control][batch_name][role] = {"path": path, "metadata": dict(metadata), "raw": raw, "tensor": tensor}
                referenced.add(path)
    unreferenced = raw_files - referenced
    allowed_fixtures = {p for p in unreferenced if "composition-reversal" in Path(p).name}
    if unreferenced - allowed_fixtures:
        _fail("raw state object is unreferenced by a control")
    return refs


def _verify_control_ids(candidate: Mapping[str, Any], controls: Mapping[str, Any]) -> None:
    declared = candidate.get("control_ids")
    if declared != list(CONTROL_IDS):
        _fail("candidate control_ids are missing, reordered, or extra")
    if not isinstance(controls, Mapping) or set(controls) != set(CONTROL_IDS) or len(controls) != len(CONTROL_IDS):
        _fail("control set is missing or contains extras")
    for name in CONTROL_IDS:
        row = controls[name]
        if not isinstance(row, Mapping) or set(row) != {"schema", "name", "batch_lanes", "potential_enabled", "batch_index"}:
            _fail(f"control {name} compact index is malformed")
        if row.get("schema") != "cassi.qi-flow-w4-periodic-fft2-control.v1" or row.get("name") != name or row.get("potential_enabled") is not (name != "potential-off"):
            _fail(f"control {name} name/schema/potential mismatch")
        if row.get("batch_lanes") != list(range(1, len(row.get("batch_index", {})) + 1)):
            _fail(f"control {name} batch lanes are malformed")

def _carrier_transform_phi(transform: Any) -> float:
    if not isinstance(transform, Mapping) or set(transform) != {"phi", "forward", "inverse", "metric"}:
        _fail("carrier D/C transform fields are missing or extra")
    phi = _f64(transform.get("phi"), name="carrier phi")
    if phi <= 0.0:
        _fail("carrier phi must be positive")
    if transform.get("forward") != {"D": "EY-phi*EI", "C": "(phi*EY+EI)/(1+phi^2)", "V_D": "VY-phi*VI", "V_C": "(phi*VY+VI)/(1+phi^2)"} or transform.get("inverse") != {"EY": "w_D*D+phi*C", "EI": "C-phi*w_D*D", "VY": "w_D*V_D+phi*V_C", "VI": "V_C-phi*w_D*V_D"} or transform.get("metric") != {"w_D": "1/(1+phi^2)", "w_C": "1+phi^2"}:
        _fail("carrier coordinate transform drifted")
    return phi
def _verify_profile(root: Path, geometry: PeriodicSheetGeometry, transport: Any, parent_index: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    del parent_index
    profile = _read_json(root / "profile" / "carrier-profile.json")
    carrier_root = _read_json(root / "profile" / "carrier-root.json")
    if profile.get("schema") != "cassi.qi-flow-carrier-profile.v1" or carrier_root.get("schema") != "cassi.qi-flow-carrier-root.v1":
        _fail("carrier profile/root schema is stale")
    _check_content_hash(profile, field="profile_sha256", path="profile/carrier-profile.json", domain=PROFILE_DOMAIN)
    _check_self(carrier_root, path="profile/carrier-root.json", domains=(ROOT_DOMAIN,))
    layout = geometry.profile.base_profile.state_layout
    scales = int(layout["scale_count"])
    mode_count = int(layout["mode_count"])
    component_count = int(layout["component_count"])
    w2 = geometry.profile
    w2_parent = profile.get("w2_parent")
    if not isinstance(w2_parent, Mapping) or w2_parent.get("profile_sha256") != w2.profile_sha256 or w2_parent.get("contract_root_sha256") != w2.contract_root_sha256 or w2_parent.get("geometry_contract_sha256") != w2.geometry_contract_sha256 or w2_parent.get("operator_semantic_sha256") != w2.operator_semantic_sha256:
        _fail("carrier profile is not bound to current W2 geometry")
    w3_parent = profile.get("w3_parent")
    if not isinstance(w3_parent, Mapping) or w3_parent.get("profile_sha256") != transport.profile_sha256 or w3_parent.get("contract_root_sha256") != transport.contract_root_sha256 or w3_parent.get("semantic_sha256") != transport.transport_semantic_sha256 or w3_parent.get("parent_w2") != transport.parent_w2:
        _fail("carrier profile is not bound to current W3 transport")
    phi = _carrier_transform_phi(profile.get("d_c_transform"))
    composition = profile.get("composition")
    dynamics = profile.get("dynamics")
    if not isinstance(composition, Mapping) or not isinstance(dynamics, Mapping): _fail("carrier profile omits composition/dynamics")
    beta = tuple(_f64(v, name=f"beta[{i}]") for i, v in enumerate(composition.get("beta", [])))
    epsilon_ref = tuple(_f64(v, name=f"epsilon_ref[{i}]") for i, v in enumerate(composition.get("epsilon_ref", [])))
    if len(beta) != scales or len(epsilon_ref) != scales or any(v < 0.0 or v >= 1.0 for v in beta) or any(v <= 0.0 for v in epsilon_ref):
        _fail("composition extension does not cover validated scales")
    def vec(section: Mapping[str, Any], key: str) -> tuple[float, ...]:
        values = section.get(key)
        if not isinstance(values, list) or len(values) != scales: _fail(f"carrier dynamics {key} does not cover validated scales")
        return tuple(_f64(v, name=f"{key}[{i}]") for i, v in enumerate(values))
    d, c = dynamics.get("D"), dynamics.get("C")
    if not isinstance(d, Mapping) or not isinstance(c, Mapping): _fail("carrier D/C dynamics are missing")
    c_d, omega_d, gamma_d, kappa_d = (vec(d, key) for key in ("c_m_per_s", "omega_rad_per_s", "gamma_per_s", "kappa"))
    c_c, omega_c, gamma_c, kappa_c = (vec(c, key) for key in ("c_m_per_s", "omega_rad_per_s", "gamma_per_s", "kappa"))
    p = transport.pinned_parameters
    for actual, expected, name in ((c_d, p.c_D_m_per_s, "D c"), (omega_d, p.omega_rad_per_s, "D omega"), (gamma_d, p.gamma_per_s, "D gamma"), (kappa_d, p.kappa, "D kappa")):
        if tuple(actual) != tuple(expected): _fail(f"carrier {name} differs from current W3")
    base = geometry.profile.base_profile.payload["dynamics"]
    for actual, key, name in ((c_c, "c_C_m_per_s", "C c"), (omega_c, "omega_C_rad_per_s", "C omega"), (gamma_c, "gamma_C_per_s", "C gamma"), (kappa_c, "kappa_C", "C kappa")):
        expected = tuple(_f64(v, name=f"base {key}") for v in base[key])
        if tuple(actual) != expected: _fail(f"carrier {name} differs from frozen W1 dynamics")
    if profile.get("state", {}).get("shape") != "[S,9M,B]" or profile.get("state", {}).get("components") != ["EY.re", "EY.im", "EI.re", "EI.im", "VY.re", "VY.im", "VI.re", "VI.im", "epsilon2_ema"] or profile.get("state", {}).get("additional_state") is not False or component_count != 9:
        _fail("carrier state layout is not [S,9M,B]")
    if composition.get("potential") != "w_C*omega_C_s^2*beta_s*tanh(epsilon_s/epsilon_ref_s)*abs(C_s)^2/2" or composition.get("epsilon") != "abs(EY)^2-phi*abs(EI)^2" or composition.get("epsilon_wirtinger") != {"D": "a_phi*(EY+phi^2*EI)", "C": "phi*(EY-EI)"} or composition.get("force") != "reciprocal-metric-wirtinger-v1" or composition.get("potential_off") != "uncoupled-combined-dc-reference-v1":
        _fail("carrier composition law drifted")
    if profile.get("integration") != {"split": "preflight-local-halfkick-analytic-fft2-half-center-placeholder-analytic-fft2-half-local-halfkick-precommit.v2", "spectral_operator": "W2-periodic-fft2-unitary-exact-damped-2x2.v1", "duration": "validated-W3-clock-interval", "local_nonlinear": "metric-adjoint-projected-pseudospectral-cubic.v1", "candidate_policy": "finite-envelope-and-work-bound-reject-before-commit.v1", "inactive_conversion": "centered-conversion-placeholder.v1"}:
        _fail("carrier integration law drifted")
    if profile.get("law_id") != "reciprocal-composition-combined-dc-velocity-verlet.v2" or profile.get("symmetry") != {"phase_current_reversal": "conjugate-EY-EI-VY-VI.v1", "coordinate_negation": "D-and-VD-only;not-epsilon-reversal.v1", "imbalance_reversal": "composition-reversal-v1-exact-paired-density.v1", "yang_yin_exchange": "metric-normalized-Yang-Yin-exchange-epsilon-sign-reversal.v1"}:
        _fail("carrier law/symmetry identity drifted")
    if carrier_root.get("profile_sha256") != profile.get("profile_sha256") or carrier_root.get("w2_geometry_profile_sha256") != w2.profile_sha256 or carrier_root.get("w2_geometry_contract_root_sha256") != w2.contract_root_sha256 or carrier_root.get("w2_operator_semantic_sha256") != w2.operator_semantic_sha256 or carrier_root.get("w3_transport_profile_sha256") != transport.profile_sha256 or carrier_root.get("w3_transport_contract_root_sha256") != transport.contract_root_sha256 or carrier_root.get("w3_transport_semantic_sha256") != transport.transport_semantic_sha256 or carrier_root.get("state_layout") != dict(layout) or carrier_root.get("no_secondary_state") is not True or carrier_root.get("profile_extension") != "w4-composition-beta-epsilon-ref.v1":
        _fail("carrier root binding is stale")
    params = {"phi": phi, "w_d": 1.0 / (1.0 + phi * phi), "w_c": 1.0 + phi * phi, "beta": beta, "epsilon_ref": epsilon_ref, "c_d": c_d, "omega_d": omega_d, "gamma_d": gamma_d, "kappa_d": kappa_d, "c_c": c_c, "omega_c": omega_c, "gamma_c": gamma_c, "kappa_c": kappa_c, "mode_count": mode_count, "scale_count": scales, "batch_limit": int(layout["batch_limit"])}
    return profile, carrier_root, params


def _check_state_tails(state: torch.Tensor, geometry: PeriodicSheetGeometry, mode_count: int) -> None:
    for scale in range(state.shape[0]):
        active = int(geometry.active_site_count(scale))
        for component in range(9):
            tail = state[scale, component * mode_count + active:(component + 1) * mode_count]
            if bool(torch.count_nonzero(tail).item()):
                _fail(f"scale {scale} component {component} inactive tail is nonzero")


def _verify_receipt_hashes(node: Any, path: str = "") -> None:
    if isinstance(node, Mapping):
        if "self_sha256" in node:
            domains = [str(node.get("schema", "")), RECEIPT_DOMAIN, DERIVATION_DOMAIN, SECTION_DOMAIN, EXTENSION_DOMAIN, GUARD_DOMAIN, "cassi.qi-flow-w3n-certificate.v1", "cassi.qi-flow-w3n-extension.v1"]
            _check_self(node, path=path or "object", domains=tuple(d for d in domains if d))
        for key, value in node.items():
            _verify_receipt_hashes(value, f"{path}.{key}" if path else str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node): _verify_receipt_hashes(value, f"{path}[{index}]")


def _root_name_allowed(root_name: str, run_id: str, *, allow_staging_root: bool) -> bool:
    if root_name == run_id:
        return True
    prefix = ".w4-periodic-fft2-"
    return allow_staging_root and root_name.startswith(prefix) and len(root_name) > len(prefix)


def verify(root: Path, *, allow_staging_root: bool = False) -> dict[str, Any]:
    root = Path(root).resolve()
    if not root.is_dir() or root.parent.name != OUTPUT_ROOT.name:
        _fail("root is not a W4 periodic-FFT2 artifact directory")
    index = _read_json(root / "index.json")
    if index.get("schema") != INDEX_SCHEMA or index.get("status") != STATUS:
        _fail("W4 index schema/status is stale")
    run_id = index.get("run_id")
    if not isinstance(run_id, str) or index.get("run_id") != canonical_hash({key: value for key, value in index.items() if key not in {"run_id", "self_sha256"}}, ARTIFACT_DOMAIN):
        _fail("W4 run_id does not match canonical artifact identity")
    if not _root_name_allowed(root.name, run_id, allow_staging_root=allow_staging_root):
        _fail("W4 run_id does not identify the artifact directory")
    _check_self(index, path="index.json", domains=(INDEX_SCHEMA,))
    _strict_file_inventory(root, index)
    manifest = _read_json(root / "manifest.json")
    if manifest.get("schema") != "cassi.qi-flow-w4-periodic-fft2-manifest.v1":
        _fail("manifest schema is stale")
    _check_self(manifest, path="manifest.json", domains=(manifest["schema"],))
    _manifest_inventory(root, manifest, index)

    identity = _read_json(root / "run-spec" / "source-identity.json")
    if identity.get("schema") != "cassi.qi-flow-w4-periodic-fft2-source-identity.v1":
        _fail("source identity schema is stale")
    _source_exact(root, identity, expected=SOURCE_PATHS)
    parent_root, parent_index, _ = _discover_parent()
    parent_link = _read_json(root / "run-spec" / "parent-w3n.json")
    parent_cert = _read_json(parent_root / "certificate" / "certificate-root.json")
    parent_ext = _read_json(parent_root / "certificate" / "extension-0001.json")
    parent_map = parent_index.get("parents")
    if not isinstance(parent_map, Mapping):
        parent_map = parent_index.get("parent_lineage")
    if not isinstance(parent_map, Mapping):
        _fail("current W3N index omits its W3/W2 lineage")
    parent_expected = {
        "run_id": parent_index.get("run_id"),
        "index_sha256": _sha((parent_root / "index.json").read_bytes()),
        "status": parent_index.get("status"),
        "source_identity_sha256": parent_index.get("source_identity_sha256"),
        "w3_profile_sha256": parent_index.get("w3_profile_sha256", parent_index.get("profile_sha256")),
        "w3_identity": parent_map.get("w3", {}),
        "w2_identity": parent_map.get("w2", {}),
        "numerical_certificate_sha256": parent_cert.get("self_sha256"),
        "certificate_extension_sha256": parent_ext.get("self_sha256"),
        "certificate_chain_id": parent_cert.get("certificate_chain_id"),
    }
    for key, expected in parent_expected.items():
        if key in parent_link and parent_link.get(key) != expected:
            _fail(f"parent-w3n {key} mismatch")
    if parent_link.get("schema") != "cassi.qi-flow-w4-periodic-fft2-parent-w3n.v1" or parent_link.get("run_id") != parent_index.get("run_id"):
        _fail("W4 parent link schema or run identity is stale")
    if parent_link.get("independent_verification", {}).get("status") not in {"PASS", "PASS_W3N_G3N"}:
        _fail("parent link omits independent W3N verification")
    if parent_link.get("w3_identity") != parent_expected["w3_identity"] or parent_link.get("w2_identity") != parent_expected["w2_identity"]:
        _fail("W3/W2 ancestry was altered")
    if index.get("parents") != [parent_link] or index.get("parent_lineage") != {"w3n": parent_link, "w3": parent_link.get("w3_identity", {}), "w2": parent_link.get("w2_identity", {})}:
        _fail("index parent graph omits exact current W3N lineage")
    if _read_json(root / "run-spec" / "w3n-index.json") != parent_index:
        _fail("W3N index snapshot differs from selected parent")
    lineage = _read_json(root / "run-spec" / "w3-w2-lineage.json")
    if lineage.get("w3n_index") != parent_index or lineage.get("w3_identity") != parent_link.get("w3_identity") or lineage.get("w2_identity") != parent_link.get("w2_identity"):
        _fail("W3/W2 lineage snapshot is stale")
    geometry_profile = load_w2_geometry_profile()
    geometry = PeriodicSheetGeometry(geometry_profile)
    transport = load_w3_transport_profile(geometry=geometry_profile)
    profile, carrier_root, params = _verify_profile(root, geometry, transport, parent_index)
    if index.get("w3n_parent_run_id") != parent_index.get("run_id") or index.get("w3n_index_sha256") != parent_link.get("index_sha256"):
        _fail("index W3N identity mismatch")
    for key, expected in (("w3_profile_sha256", transport.profile_sha256), ("w2_geometry_profile_sha256", geometry.profile.profile_sha256), ("carrier_profile_sha256", profile["profile_sha256"]), ("carrier_root_sha256", carrier_root["self_sha256"])):
        if index.get(key) != expected:
            _fail(f"index {key} mismatch")

    binding = _read_json(root / "run-spec" / "w4-profile.json")
    _check_self(binding, path="run-spec/w4-profile.json", domains=(binding.get("schema", ""),))
    if binding.get("schema") != "cassi.qi-flow-w4-periodic-fft2-profile-binding.v1" or binding.get("immutable") is not True or binding.get("carrier_profile_sha256") != profile["profile_sha256"] or binding.get("carrier_root_sha256") != carrier_root["self_sha256"] or binding.get("w2_identity") != parent_link.get("w2_identity") or binding.get("w3_identity") != parent_link.get("w3_identity") or binding.get("w3n_identity") != parent_link:
        _fail("W4 immutable profile binding is stale")
    base_layout = geometry.profile.base_profile.state_layout
    base_field = geometry.profile.base_profile.payload["field"]
    expected_layout = {
        "layout_id": str(base_layout.get("layout_id", "cassi.qi-flow-state-layout.v3")),
        "shape_prefix": [params["scale_count"], 9 * params["mode_count"]],
        "scale_count": params["scale_count"],
        "mode_count": params["mode_count"],
        "component_count": int(base_layout["component_count"]),
        "batch_limit": params["batch_limit"],
        "dtype": str(base_layout.get("tensor_dtype")),
        "byte_order": str(base_layout.get("state_object_endianness")),
        "component_order": list(base_field["component_order"]),
        "active_shapes": [list(geometry.sheet_shape(s)) for s in range(params["scale_count"])],
        "active_site_counts": [int(geometry.active_site_count(s)) for s in range(params["scale_count"])],
    }
    if binding.get("state_layout", {}).keys() - (set(expected_layout) | {"topology"}):
        _fail("W4 state layout has extra fields")
    if any(binding.get("state_layout", {}).get(key) != value for key, value in expected_layout.items()):
        _fail("W4 state layout is not dynamically bound to validated geometry")
    topology = binding["state_layout"].get("topology")
    retention = geometry.profile.base_profile.payload["retention"]
    expected_topology = {
        "active_sheet": int(retention["slow_scale"]),
        "edge_registry": retention["edge_registry"],
        "cycle_registry": retention["cycle_registry"],
        "edge_registry_sha256": retention.get("edge_registry_sha256"),
        "cycle_registry_sha256": retention.get("cycle_registry_sha256"),
    }
    if topology != expected_topology:
        _fail("W4 topology binding is stale")

    schedule = _read_json(root / "run-spec" / "w4-stage-schedule.json")
    _check_self(schedule, path="run-spec/w4-stage-schedule.json", domains=(schedule.get("schema", ""),))
    duration = _f64(schedule.get("h_s"), name="W4 duration")
    _close(duration, float(transport.pinned_parameters.h), name="W4 duration/current W3 clock", rtol=0.0, atol=0.0)
    expected_transport_schedule = w3_stage_schedule(duration)
    if _numeric_tree(schedule.get("transport_schedule")) != _numeric_tree(expected_transport_schedule) or schedule.get("transport_schedule_sha256") != canonical_hash(expected_transport_schedule, expected_transport_schedule["schema"]):
        _fail("transport schedule snapshot drifted")
    _verify_schedule(schedule, duration=duration, geometry=geometry)

    cert = _read_json(root / "certificate" / "g3n-certificate-root.json")
    parent_ext_copy = _read_json(root / "certificate" / "g3n-extension-0001.json")
    cert_copy = _read_json(root / "certificate" / "certificate-root.json")
    ext_copy = _read_json(root / "certificate" / "extension-0001.json")
    if cert != parent_cert or cert_copy != cert or parent_ext_copy != parent_ext or ext_copy != parent_ext:
        _fail("copied G3N certificate chain differs from current W3N parent")
    _check_self(cert, path="certificate/g3n-certificate-root.json", domains=("cassi.qi-flow-w3n-certificate.v1",))
    _check_self(cert_copy, path="certificate/certificate-root.json", domains=("cassi.qi-flow-w3n-certificate.v1",))
    _check_self(parent_ext_copy, path="certificate/g3n-extension-0001.json", domains=("cassi.qi-flow-w3n-extension.v1",))
    _check_self(ext_copy, path="certificate/extension-0001.json", domains=("cassi.qi-flow-w3n-extension.v1",))
    derivation = _read_json(root / "certificate" / "composition-derivation.json")
    section = _read_json(root / "certificate" / "composition-section.json")
    extension = _read_json(root / "certificate" / "extension-0002.json")
    if _read_json(root / "certificate" / "w4-extension.json") != extension:
        _fail("duplicated W4 extension differs")
    _check_self(derivation, path="certificate/composition-derivation.json", domains=(DERIVATION_DOMAIN,))
    _check_self(section, path="certificate/composition-section.json", domains=(SECTION_DOMAIN,))
    _check_self(extension, path="certificate/extension-0002.json", domains=(extension.get("schema", ""),))
    if derivation.get("carrier_profile_sha256") != profile["profile_sha256"] or derivation.get("carrier_root_sha256") != carrier_root["self_sha256"] or derivation.get("g3n_numerical_certificate_sha256") != cert["self_sha256"]:
        _fail("composition derivation identity mismatch")
    raw_cap = _f64(cert["online_guard_contract"]["raw_component_admission_abs"], name="G3N raw cap")
    cert_min = _f64(cert["offline_derivation"]["inputs"]["h_min_s"], name="G3N h_min")
    cert_max = _f64(cert["offline_derivation"]["inputs"]["h_max_s"], name="G3N h_max")
    if not (0.0 < cert_min <= duration <= cert_max):
        _fail("W4 runtime duration is outside the G3N certified clock interval")
    c_cap = math.sqrt(2.0) * (1.0 + params["phi"]) * raw_cap * params["w_d"]
    gradient_cap = math.sqrt(2.0) * raw_cap * (1.0 + 2.0 * params["phi"])
    curvature_by_scale = [params["w_c"] * params["omega_c"][s] ** 2 * params["beta"][s] * (2.0 / params["epsilon_ref"][s] + 4.0 * c_cap * gradient_cap / params["epsilon_ref"][s] + 2.0 * c_cap * c_cap * gradient_cap * gradient_cap / params["epsilon_ref"][s] ** 2) for s in range(params["scale_count"])]
    curvature = max(curvature_by_scale, default=0.0); work_bound = (curvature + 1.0) * cert_max * cert_max * 128.0
    expected_inputs = {"duration_s": cert_max, "duration_interval_s": {"minimum": cert_min, "maximum": cert_max}}
    for key, expected in expected_inputs.items():
        if _numeric_tree(derivation["inputs"][key]) != _numeric_tree(expected):
            _fail(f"composition derivation clock input mismatch: {key}")
    for key, expected in (("raw_component_admission_abs", raw_cap), ("bounds", {"c_abs": c_cap, "epsilon_wirtinger_abs": gradient_cap, "curvature_abs_per_scale": curvature_by_scale, "curvature_abs": curvature, "coordinate_work_rounding_abs": work_bound, "total_coupled_integrator_abs": work_bound})):
        actual = derivation.get(key)
        if isinstance(expected, Mapping):
            for subkey, value in expected.items(): _close(actual.get(subkey), value, name=f"derivation.bounds.{subkey}")
        else: _close(actual, expected, name=f"derivation.{key}")
    if section.get("offline_derivation_sha256") != derivation["self_sha256"] or section.get("carrier_profile_sha256") != profile["profile_sha256"] or section.get("carrier_root_sha256") != carrier_root["self_sha256"]:
        _fail("composition section identity mismatch")
    if extension.get("parent_certificate_sha256") != parent_ext["self_sha256"] or extension.get("composition_derivation_sha256") != derivation["self_sha256"] or extension.get("added_section") != section or extension.get("accepted_w3n_identity") != parent_link or extension.get("chain_ordinal") != parent_ext.get("chain_ordinal", 1) + 1:
        _fail("W4 certificate extension chain is stale")
    extension_body = {key: value for key, value in extension.items() if key not in {"self_sha256", "final_certificate_identity_sha256"}}
    if extension.get("final_certificate_identity_sha256") != canonical_hash(extension_body, extension["schema"]):
        _fail("W4 extension final identity mismatch")

    runtime = _read_json(root / "results" / "runtime.json")
    _check_self(runtime, path="results/runtime.json", domains=(runtime.get("schema", ""),))
    if runtime.get("schema") != "cassi.qi-flow-w4-periodic-fft2-runtime.v1" or runtime.get("raw_state_domain") != RAW_DOMAIN or runtime.get("carrier_profile_sha256") != profile["profile_sha256"] or runtime.get("carrier_root_sha256") != carrier_root["self_sha256"] or runtime.get("w3n_parent_run_id") != parent_index["run_id"] or _numeric_tree(runtime.get("schedule")) != _numeric_tree(schedule) or runtime.get("no_clipping") is not True or runtime.get("no_projection") is not True or runtime.get("no_new_state") is not True:
        _fail("runtime identity/schedule binding is stale")
    if runtime.get("references") is None or runtime.get("composition_reversal_v1") is None:
        _fail("runtime control references are missing")
    runtime_layout = runtime.get("layout")
    if runtime_layout != binding["state_layout"]:
        _fail("runtime layout differs from immutable profile binding")
    _verify_receipt_hashes(runtime)
    controls_runtime = runtime.get("controls")
    candidate = _read_json(root / "gates" / "g04-carrier" / "carrier.json")
    controls_receipt = _read_json(root / "gates" / "g04-carrier" / "controls.json")
    status = _read_json(root / "gates" / "g04-carrier" / "status.json")
    _verify_receipt_hashes(candidate); _verify_receipt_hashes(controls_receipt); _verify_receipt_hashes(status)
    if not isinstance(controls_runtime, Mapping): _fail("runtime controls are missing")
    _verify_control_ids(candidate, controls_runtime)
    refs = _load_state_metadata(root, runtime, controls_runtime, candidate, shape_prefix=(params["scale_count"], 9 * params["mode_count"]), batch_limit=params["batch_limit"])
    if candidate.get("schema") != "cassi.qi-flow-g4-candidate.v1" or candidate.get("artifact_schema") != "cassi.qi-flow-w4-periodic-fft2-carrier-candidate.v1" or candidate.get("status") != STATUS or candidate.get("carrier_profile_sha256") != profile["profile_sha256"] or candidate.get("carrier_root_sha256") != carrier_root["self_sha256"] or candidate.get("controls") != controls_runtime or candidate.get("runtime_sha256") != runtime["self_sha256"] or candidate.get("stage_schedule_sha256") != schedule["self_sha256"] or candidate.get("transport_stage_schedule_sha256") != schedule["transport_schedule_sha256"] or candidate.get("source_identity_sha256") != identity["source_identity_sha256"] or candidate.get("composition_reversal_v1") != runtime.get("composition_reversal_v1") or candidate.get("counterfactuals") != {"potential_off_uncoupled_dc": runtime.get("references")}:
        _fail("carrier candidate graph is stale")
    expected_fail_before_commit = {"post_candidate_guard": True, "rejected_candidate_exposed": False, "clipping": False, "projection": False, "new_state": False, "fallback": False}
    if candidate.get("candidate_fail_before_commit") != expected_fail_before_commit:
        _fail("candidate fail-before-commit policy is stale")
    if candidate.get("parent_w3n") != parent_link or candidate.get("composition_derivation_sha256") != derivation["self_sha256"] or candidate.get("composition_section_sha256") != section["self_sha256"] or candidate.get("certificate_extension_sha256") != extension["self_sha256"]:
        _fail("carrier candidate ancestry/extension binding is stale")
    expected_control_receipts = {
        name: {batch: refs[name][batch]["result"].get("receipt_sha256") for batch in refs[name]}
        for name in CONTROL_IDS
    }
    curvature_extension = controls_receipt.get("composition_curvature_work_extension")
    if controls_receipt.get("schema") != "cassi.qi-flow-w4-periodic-fft2-controls.v1" or controls_receipt.get("status") != "PASS" or controls_receipt.get("control_ids") != list(CONTROL_IDS) or controls_receipt.get("batch_lanes") != list(range(1, params["batch_limit"] + 1)) or controls_receipt.get("all_scales") != params["scale_count"] or controls_receipt.get("heterogeneous_batch") is not (params["batch_limit"] > 1) or controls_receipt.get("potential_off_reference") != "uncoupled-combined-dc-reference-v1" or controls_receipt.get("control_receipt_sha256") != expected_control_receipts or controls_receipt.get("coordinate_negation_is_not_epsilon_reversal") is not True or controls_receipt.get("phase_current_reversal") != "R_J" or controls_receipt.get("yang_yin_exchange") != "explicit-metric-exchange" or controls_receipt.get("phase_shuffle_is_equal_energy_falsifier") is not True or not isinstance(curvature_extension, Mapping):
        _fail("G4 controls receipt is missing or stale")
    if set(curvature_extension) != {"derivation_sha256", "section_sha256", "curvature_abs", "coordinate_work_rounding_abs", "total_coupled_integrator_abs"} or curvature_extension.get("derivation_sha256") != derivation["self_sha256"] or curvature_extension.get("section_sha256") != section["self_sha256"]:
        _fail("G4 curvature/work extension identity is stale")
    for key in ("curvature_abs", "coordinate_work_rounding_abs", "total_coupled_integrator_abs"):
        _close(curvature_extension.get(key), derivation["bounds"][key], name=f"controls curvature/work extension {key}")
    if controls_receipt.get("self_sha256") != candidate.get("controls_sha256"):
        _fail("candidate controls receipt hash mismatch")
    if controls_receipt.get("controls") != controls_runtime:
        _fail("controls receipt map differs from runtime controls")
    negative = _read_json(root / "gates" / "g04-carrier" / "negative-controls" / "coherent-wave-total-ledger-mutation.json")
    _verify_receipt_hashes(negative)
    mutation = negative.get("mutation")
    if negative.get("schema") != "cassi.qi-flow-w4-periodic-fft2-negative-control.v1" or negative.get("control_id") != "coherent-wave-total-ledger-mutation" or negative.get("expected_decision") != "REJECT" or negative.get("rejection_reason") != "coherent-wave-total-ledger-mutation" or not isinstance(mutation, Mapping) or set(mutation) != {"wave_energy_delta_add", "total_coupled_closure_add"} or _f64(mutation.get("wave_energy_delta_add"), name="negative mutation wave_energy_delta_add") != 1.0 or _f64(mutation.get("total_coupled_closure_add"), name="negative mutation total_coupled_closure_add") != 1.0:
        _fail("negative ledger control identity is stale")
    source_control = negative.get("source_control")
    source_result = refs[source_control]["1"]["result"] if isinstance(source_control, str) and source_control in refs else None
    mutated_receipt = negative.get("mutated_receipt")
    if not isinstance(source_result, Mapping) or not isinstance(mutated_receipt, Mapping) or not isinstance(source_result.get("receipt"), Mapping):
        _fail("negative ledger control omits its source receipt")
    source_receipt = source_result["receipt"]
    source_composition = source_receipt.get("composition")
    if not isinstance(source_composition, Mapping) or set(source_composition) != {"base_energy_pre", "base_energy_post", "U_pre", "U_D_path", "U_center", "U_C_path", "U_post", "Delta_U", "W_D", "W_center", "W_C", "coordinate_work_closure", "registered_coordinate_work_bound", "wave_energy_delta", "total_coupled_closure", "registered_total_coupled_integrator_bound", "force_D_sum_re", "force_C_sum_re", "slow_carrier_bias_re", "per_scale_U_pre", "per_scale_U_post"}:
        _fail("negative ledger source composition is malformed")
    mutated_composition = mutated_receipt.get("composition")
    if set(mutated_receipt) != set(source_receipt) or not isinstance(mutated_composition, Mapping) or set(mutated_composition) != set(source_composition):
        _fail("negative ledger mutation shape differs from source receipt")
    for key, value in source_receipt.items():
        if key not in {"composition", "self_sha256"} and mutated_receipt.get(key) != value:
            _fail("negative ledger mutation is not limited to its declared fields")
    for key, value in source_composition.items():
        if key not in {"wave_energy_delta", "total_coupled_closure"} and mutated_composition.get(key) != value:
            _fail("negative ledger mutation changed an undeclared composition field")
    _close(mutated_composition.get("wave_energy_delta"), _f64(source_composition["wave_energy_delta"], name="negative source wave_energy_delta") + 1.0, name="negative mutated wave_energy_delta")
    _close(mutated_composition.get("total_coupled_closure"), _f64(source_composition["total_coupled_closure"], name="negative source total_coupled_closure") + 1.0, name="negative mutated total_coupled_closure")
    _check_self(mutated_receipt, path="negative-control.mutated_receipt", domains=(RECEIPT_DOMAIN,))
    raw_component = negative.get("raw_component_recomputation")
    if not isinstance(raw_component, Mapping) or set(raw_component) != {"coordinate_work_closure", "wave_energy_delta", "total_coupled_closure"}:
        _fail("negative ledger raw recomputation is incomplete")
    u_pre = _f64(source_composition["U_pre"], name="negative source U_pre")
    u_d_path = _f64(source_composition["U_D_path"], name="negative source U_D_path")
    u_post = _f64(source_composition["U_post"], name="negative source U_post")
    base_pre = _f64(source_composition["base_energy_pre"], name="negative source base_energy_pre")
    base_post = _f64(source_composition["base_energy_post"], name="negative source base_energy_post")
    for key, expected in (
        ("coordinate_work_closure", -(u_d_path - u_pre) - (u_post - u_d_path) + (u_post - u_pre)),
        ("wave_energy_delta", base_post - base_pre),
        ("total_coupled_closure", base_post - base_pre + (u_post - u_pre)),
    ):
        _close(raw_component.get(key), expected, name=f"negative-control.raw_component_recomputation.{key}")
    if candidate.get("negative_controls") != {negative["control_id"]: negative}:
        _fail("candidate negative-control graph is stale")
    if status.get("schema") != "cassi.qi-flow-w4-periodic-fft2-status.v1" or status.get("gate") != "G4" or status.get("status") != STATUS or status.get("decision") != STATUS or status.get("candidate_sha256") != candidate["self_sha256"] or status.get("runtime_sha256") != runtime["self_sha256"] or status.get("source_identity_sha256") != identity["source_identity_sha256"] or status.get("certificate_extension_sha256") != extension["self_sha256"]:
        _fail("G4 status graph is stale")
    conditions = status.get("conditions")
    if not isinstance(conditions, Mapping) or set(conditions) != {"current_source_exact_w3n", "independent_w3n_verification", "w3_w2_lineage_retained", "seven_stage_combined_dc_schedule", "all_scales", "heterogeneous_batches", "potential_off_uncoupled_dc", "composition_reversal_zero_velocity", "metric_gradient_work_recorded", "raw_predecessor_candidate_states", "no_clipping_projection_new_state"} or any(value is not True for value in conditions.values()):
        _fail("G4 conditions are incomplete")

    states = runtime.get("states")
    if not isinstance(states, Mapping) or not states:
        _fail("runtime state map is missing")
    state_paths: set[str] = set()
    for state_sha, metadata in states.items():
        if not isinstance(metadata, Mapping) or metadata.get("state_sha256") != state_sha:
            _fail("runtime state map identity mismatch")
        path = metadata.get("path"); fixture_meta_path = root / f"fixtures/{state_sha}.json"
        if not isinstance(path, str) or not fixture_meta_path.is_file() or fixture_meta_path.read_bytes() != canonical_json_bytes(dict(metadata)):
            _fail("fixture metadata snapshot mismatch")
        declared_shape = metadata.get("shape")
        if not isinstance(declared_shape, list) or len(declared_shape) != 3:
            _fail("fixture state shape is missing")
        tensor = _decode_raw(root / path, metadata, shape=tuple(int(v) for v in declared_shape))[1]
        _check_state_tails(tensor, geometry, params["mode_count"])
        state_paths.add(path)
    reversal = runtime.get("composition_reversal_v1")
    if not isinstance(reversal, Mapping) or reversal.get("fixture_id") != "composition-reversal-v1" or not isinstance(reversal.get("raw_fixture_paths"), Mapping):
        _fail("composition reversal fixture is missing")
    raw_fixture_paths = reversal["raw_fixture_paths"]
    if set(raw_fixture_paths) != {"minus", "plus"}:
        _fail("composition reversal raw fixture map is incomplete")
    for arm in ("minus", "plus"):
        arm_path = raw_fixture_paths.get(arm)
        if not isinstance(arm_path, str) or Path(arm_path).is_absolute() or ".." in Path(arm_path).parts or not (root / arm_path).is_file():
            _fail(f"composition reversal {arm} raw fixture is missing")
    static_paths = {
        "run-spec/source-identity.json", "run-spec/parent-w3n.json", "run-spec/w3n-index.json", "run-spec/w3-w2-lineage.json", "run-spec/w4-profile.json", "run-spec/w4-stage-schedule.json", "run-spec/hash-graph.json",
        "profile/carrier-profile.json", "profile/carrier-root.json",
        "certificate/g3n-certificate-root.json", "certificate/g3n-extension-0001.json", "certificate/certificate-root.json", "certificate/extension-0001.json", "certificate/composition-derivation.json", "certificate/composition-section.json", "certificate/extension-0002.json", "certificate/w4-extension.json",
        "results/runtime.json", "gates/g04-carrier/carrier.json", "gates/g04-carrier/controls.json", "gates/g04-carrier/status.json", "gates/g04-carrier/negative-controls/coherent-wave-total-ledger-mutation.json",
    }
    static_paths.update(f"sources/{source}" for source in SOURCE_PATHS)
    expected_paths = static_paths | {str(metadata["path"]) for metadata in states.values()} | {str(reversal["raw_fixture_paths"][arm]) for arm in ("minus", "plus")}
    expected_paths |= {f"fixtures/{state_sha}.json" for state_sha in states}
    for control in CONTROL_IDS:
        safe = control.replace("+", "-plus-").replace("/", "-").replace(" ", "-")
        expected_paths |= {f"gates/g04-carrier/controls/{safe}/batch-{batch}.json" for batch in range(1, params["batch_limit"] + 1)}
    actual_paths = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() and path.relative_to(root).as_posix() not in {"index.json", "manifest.json"}}
    if actual_paths != expected_paths:
        _fail("artifact object set differs from the contracted W4 inventory")

    # Every batch is replayed independently.  The force receipt is checked for
    # both D and C, preventing a one-sided or double-counted composition force.
    for control in CONTROL_IDS:
        row = controls_runtime[control]
        if not isinstance(row, Mapping) or row.get("name") != control or row.get("potential_enabled") is not (control != "potential-off"):
            _fail(f"control {control} identity mismatch")
        for batch_name in sorted(row["batch_index"], key=lambda value: int(value)):
            batch = int(batch_name)
            refs_row = refs[control][batch_name]
            result = refs_row["result"]
            expected_receipt_path = refs_row["path"]
            if not isinstance(result, Mapping):
                _fail(f"control {control} batch {batch} gate receipt is malformed")
            if result.get("schema") != "cassi.qi-flow-w4-periodic-fft2-control.v1" or result.get("name") != control or result.get("batch_lanes") != batch or result.get("potential_enabled") is not (control != "potential-off") or result.get("receipt_path") != expected_receipt_path:
                _fail(f"control {control} batch {batch} result identity is stale")
            predecessor, candidate_state = refs_row["predecessor"], refs_row["candidate"]
            if result.get("predecessor") != predecessor["metadata"] or result.get("candidate") != candidate_state["metadata"]:
                _fail(f"control {control} batch {batch} result state metadata differs from runtime")
            receipt = result.get("receipt")
            if not isinstance(receipt, Mapping):
                _fail(f"control {control} batch {batch} omits receipt")
            _check_self(receipt, path=f"{control}/{batch}.receipt", domains=(RECEIPT_DOMAIN,))
            if receipt.get("status") != "PASS" or receipt.get("committable") is not True or receipt.get("predecessor_state_sha256") != predecessor["metadata"]["state_sha256"] or receipt.get("candidate_state_sha256") != candidate_state["metadata"]["state_sha256"] or result.get("receipt_sha256") != receipt["self_sha256"] or result.get("predecessor_raw_sha256") != predecessor["metadata"]["raw_sha256"] or result.get("candidate_raw_sha256") != candidate_state["metadata"]["raw_sha256"]:
                _fail(f"control {control} batch {batch} state/receipt hash mismatch")
            if receipt.get("carrier_profile_sha256") != profile["profile_sha256"] or receipt.get("carrier_root_sha256") != carrier_root["self_sha256"] or receipt.get("w3_transport_profile_sha256") != transport.profile_sha256 or receipt.get("w3_transport_semantic_sha256") != transport.transport_semantic_sha256 or receipt.get("w2_geometry_profile_sha256") != geometry.profile.profile_sha256 or _f64(receipt.get("duration_s"), name=f"{control}/{batch} duration_s") != duration or _numeric_tree(receipt.get("stage_schedule")) != _numeric_tree(schedule.get("transport_schedule")):
                _fail(f"control {control} batch {batch} receipt ancestry or schedule drift")
            replayed, evidence = _replay(predecessor["tensor"], geometry=geometry, params=params, duration=duration, enabled=control != "potential-off")
            if not torch.equal(replayed, candidate_state["tensor"]) and not bool(torch.allclose(replayed, candidate_state["tensor"], rtol=0.0, atol=2.0e-13)):
                _fail(f"control {control} batch {batch} failed independent D/C FFT2 replay")
            predecessor_values = _coords(predecessor["tensor"], geometry, phi=params["phi"], mode_count=params["mode_count"])
            candidate_values = _coords(candidate_state["tensor"], geometry, phi=params["phi"], mode_count=params["mode_count"])
            _verify_epsilon_summary(result.get("epsilon"), predecessor_values, geometry, params, name=f"{control}/{batch}/predecessor")
            _verify_epsilon_summary(result.get("candidate_epsilon"), candidate_values, geometry, params, name=f"{control}/{batch}/candidate")
            stage_evidence = receipt.get("stage_evidence")
            if not isinstance(stage_evidence, list) or len(stage_evidence) != 7:
                _fail(f"control {control} batch {batch} does not retain seven stages")
            for ordinal, stage in enumerate(stage_evidence, 1):
                if not isinstance(stage, Mapping) or stage.get("ordinal") != ordinal:
                    _fail(f"control {control} batch {batch} stage ordinal drift")
                if stage.get("name") != schedule["stages"][ordinal - 1]["name"]:
                    _fail(f"control {control} batch {batch} stage name drift")
            _match_summaries(stage_evidence[1].get("force", {}), evidence["first_force"], name=f"{control}/{batch}/stage2")
            _match_summaries(stage_evidence[5].get("force", {}), evidence["second_force"], name=f"{control}/{batch}/stage6")
            for stage_index, branch_key in ((2, "branches_first"), (4, "branches_second")):
                actual = stage_evidence[stage_index].get("spectral", {})
                expected = evidence[branch_key]
                if actual.get("branches") != expected or _f64(actual.get("duration_s"), name=f"{control}/{batch} spectral duration_s") != 0.5 * duration:
                    _fail(f"control {control} batch {batch} spectral FFT2 replay drift")
            _verify_energy_and_ledger(
                result,
                receipt,
                evidence,
                predecessor=predecessor["tensor"],
                candidate=candidate_state["tensor"],
                geometry=geometry,
                params=params,
                enabled=control != "potential-off",
                registered_bound=work_bound,
            )
            if receipt.get("split") != "combined-dc-symmetric-seven-stage.v2" or receipt.get("damping") != "D-and-C-analytic-fft2-exactly-once-per-half.v1" or receipt.get("projection") != "metric-adjoint-projected-pseudospectral-cubic.v1":
                _fail(f"control {control} batch {batch} split/operator identity drift")
            if not control == "potential-off" and receipt.get("potential_off_identity") is not None:
                _fail("potential-off identity leaked into coupled control")
            if control == "potential-off":
                reference = candidate.get("counterfactuals", {}).get("potential_off_uncoupled_dc", {}).get(str(batch))
                if not isinstance(reference, Mapping) or reference.get("kind") != "uncoupled-combined-dc-reference-v1" or reference.get("state_sha256") != candidate_state["metadata"]["state_sha256"]:
                    _fail(f"potential-off batch {batch} is not the uncoupled combined D+C replay")

    # Pattern and matched-condition checks use only raw predecessor fields.
    def same(a: torch.Tensor, b: torch.Tensor) -> bool:
        return torch.equal(a, b) or bool(torch.allclose(a, b, rtol=0.0, atol=2.0e-13))
    for batch_name in sorted(refs["D+C"], key=lambda value: int(value)):
        dc = refs["D+C"][batch_name]["predecessor"]["tensor"]; vals = _coords(dc, geometry, phi=params["phi"], mode_count=params["mode_count"])
        d_only = _coords(refs["D-only"][batch_name]["predecessor"]["tensor"], geometry, phi=params["phi"], mode_count=params["mode_count"])
        c_only = _coords(refs["C-only"][batch_name]["predecessor"]["tensor"], geometry, phi=params["phi"], mode_count=params["mode_count"])
        zero = refs["zero"][batch_name]["predecessor"]["tensor"]
        if any(torch.count_nonzero(value).item() for value in (*c_only["d"], *c_only["vd"])) or any(torch.count_nonzero(value).item() for value in (*d_only["c"], *d_only["vc"])) or bool(torch.count_nonzero(zero).item()):
            _fail(f"control pattern batch {batch_name} violates D/C or zero basis")
        if not same(refs["potential-off"][batch_name]["predecessor"]["tensor"], dc):
            _fail(f"potential-off batch {batch_name} does not use D+C predecessor")
        for name, transform in (("coordinate-negation", "negate-d"), ("phase-current-reversal", "phase"), ("yang-yin-exchange", "exchange"), ("phase-shuffled-equal-energy", "shuffle")):
            source = dc.clone()
            if transform == "negate-d":
                cv = _coords(source, geometry, phi=params["phi"], mode_count=params["mode_count"])
                cv = {**cv, "d": tuple(-x for x in cv["d"]), "vd": tuple(-x for x in cv["vd"])}
                source = _pack_coords(source, cv, geometry, phi=params["phi"], mode_count=params["mode_count"])
            elif transform == "phase":
                for component in (1, 3, 5, 7): source[:, component * params["mode_count"]:(component + 1) * params["mode_count"]] *= -1.0
            elif transform == "exchange":
                root_phi = math.sqrt(params["phi"])
                for a, b in ((0, 2), (1, 3), (4, 6), (5, 7)):
                    left = source[:, a * params["mode_count"]:(a + 1) * params["mode_count"]].clone()
                    source[:, a * params["mode_count"]:(a + 1) * params["mode_count"]] = root_phi * source[:, b * params["mode_count"]:(b + 1) * params["mode_count"]]
                    source[:, b * params["mode_count"]:(b + 1) * params["mode_count"]] = left / root_phi
            else:
                for s in range(params["scale_count"]):
                    for lane in range(int(source.shape[-1])):
                        turn = (s + lane + 1) % 4
                        for a, b in ((0, 1), (2, 3), (4, 5), (6, 7)):
                            real = source[s, a * params["mode_count"]:(a + 1) * params["mode_count"], lane].clone()
                            imag = source[s, b * params["mode_count"]:(b + 1) * params["mode_count"], lane].clone()
                            if turn == 1: nr, ni = -imag, real
                            elif turn == 2: nr, ni = -real, -imag
                            elif turn == 3: nr, ni = imag, -real
                            else: nr, ni = real, imag
                            source[s, a * params["mode_count"]:(a + 1) * params["mode_count"], lane] = nr
                            source[s, b * params["mode_count"]:(b + 1) * params["mode_count"], lane] = ni
            if not same(source, refs[name][batch_name]["predecessor"]["tensor"]):
                _fail(f"{name} batch {batch_name} transform mismatch")
    if params["scale_count"] > 0:
        slow = int(topology["active_sheet"])
        for batch_name in refs["scale-local"]:
            local = _coords(refs["scale-local"][batch_name]["predecessor"]["tensor"], geometry, phi=params["phi"], mode_count=params["mode_count"])
            if any(bool(torch.count_nonzero(local[key][s]).item()) for key in ("d", "c", "vd", "vc") for s in range(params["scale_count"]) if s != slow):
                _fail("scale-local control activates an inactive scale")

    graph = _read_json(root / "run-spec" / "hash-graph.json")
    _check_self(graph, path="run-spec/hash-graph.json", domains=(graph.get("schema", ""),))
    expected_nodes = {
        "w3n": {"run_id": parent_link["run_id"], "index_sha256": parent_link["index_sha256"]},
        "w3": parent_link["w3_identity"], "w2": parent_link["w2_identity"],
        "certificate": {"self_sha256": cert["self_sha256"]}, "certificate_extension_parent": {"self_sha256": parent_ext["self_sha256"]},
        "carrier_profile": {"self_sha256": profile["profile_sha256"]}, "carrier_root": {"self_sha256": carrier_root["self_sha256"]},
        "composition_derivation": {"self_sha256": derivation["self_sha256"]}, "composition_section": {"self_sha256": section["self_sha256"]},
        "certificate_extension": {"self_sha256": extension["self_sha256"]}, "runtime": {"self_sha256": runtime["self_sha256"]},
        "candidate": {"self_sha256": candidate["self_sha256"]}, "status": {"self_sha256": status["self_sha256"]},
    }
    if graph.get("nodes") != expected_nodes or graph.get("edges") != [["w3n", "w3"], ["w3", "w2"], ["w3n", "certificate"], ["certificate", "certificate_extension_parent"], ["carrier_profile", "carrier_root"], ["certificate_extension_parent", "certificate_extension"], ["composition_derivation", "composition_section"], ["certificate_extension", "candidate"], ["runtime", "candidate"], ["candidate", "status"]] or graph.get("state_object_count") != len(states) or graph.get("receipt_count") != len(CONTROL_IDS) * params["batch_limit"]:
        _fail("hash graph is missing, extra, or stale edges")

    reversal_states = runtime["composition_reversal_v1"]
    if not isinstance(reversal_states, Mapping):
        _fail("composition reversal fixture is malformed")
    observations = reversal_states.get("observations")
    raw_fixture_paths = reversal_states.get("raw_fixture_paths")
    raw_state_sha256 = reversal_states.get("raw_state_sha256")
    if not isinstance(observations, Mapping) or not isinstance(raw_fixture_paths, Mapping) or not isinstance(raw_state_sha256, Mapping):
        _fail("composition reversal observations or identities are missing")
    expected_observation_keys = {"position_density", "epsilon", "velocity_max_abs", "full_energy"}
    reversal_values: dict[str, dict[str, Any]] = {}
    for arm in ("minus", "plus"):
        meta = reversal_states.get(f"{arm}_state")
        if not isinstance(meta, Mapping):
            _fail(f"reversal {arm} metadata is missing")
        state_path = meta.get("path")
        fixture_path = raw_fixture_paths.get(arm)
        if not isinstance(state_path, str) or not isinstance(fixture_path, str) or Path(state_path).is_absolute() or ".." in Path(state_path).parts or Path(fixture_path).is_absolute() or ".." in Path(fixture_path).parts or not (root / state_path).is_file() or not (root / fixture_path).is_file() or not fixture_path.endswith(f"composition-reversal-v1-{arm}.f64le"):
            _fail(f"reversal {arm} raw fixture path is stale")
        shape = meta.get("shape")
        if not isinstance(shape, list) or len(shape) != 3 or tuple(int(value) for value in shape[:2]) != (params["scale_count"], 9 * params["mode_count"]) or int(shape[2]) != 1:
            _fail(f"reversal {arm} shape is not dynamically bound")
        raw, values = _decode_raw(root / state_path, meta, shape=tuple(int(value) for value in shape))
        if (root / fixture_path).read_bytes() != raw:
            _fail(f"reversal {arm} raw fixture differs from state object")
        _check_state_tails(values, geometry, params["mode_count"])
        coords = _coords(values, geometry, phi=params["phi"], mode_count=params["mode_count"])
        velocity_max_abs = max((float(value.abs().amax().item()) for key in ("vd", "vc") for value in coords[key]), default=0.0)
        if velocity_max_abs != 0.0:
            _fail("composition reversal fixture has nonzero velocity")
        reversal_values[arm] = {
            "position_density": [float((coords["ey"][scale].abs().square() + coords["ei"][scale].abs().square()).real.mean().item()) for scale in range(params["scale_count"])],
            "epsilon": [float((coords["ey"][scale].abs().square() - params["phi"] * coords["ei"][scale].abs().square()).real.mean().item()) for scale in range(params["scale_count"])],
            "velocity_max_abs": velocity_max_abs,
            "full_energy": _carrier_energy(coords, geometry, params, coupled=True),
        }
        if raw_state_sha256.get(arm) != meta.get("state_sha256"):
            _fail(f"composition reversal {arm} state identity mismatch")
        actual = observations.get(arm)
        if not isinstance(actual, Mapping) or set(actual) != expected_observation_keys:
            _fail(f"composition reversal {arm} observations are incomplete")
        for key in ("position_density", "epsilon"):
            values_actual = actual.get(key)
            values_expected = reversal_values[arm][key]
            if not isinstance(values_actual, list) or len(values_actual) != len(values_expected):
                _fail(f"composition reversal {arm} {key} observations are malformed")
            for scale, (actual_value, expected_value) in enumerate(zip(values_actual, values_expected, strict=True)):
                _close(actual_value, expected_value, name=f"composition reversal {arm} {key}[{scale}]")
        _close(actual.get("velocity_max_abs"), velocity_max_abs, name=f"composition reversal {arm} velocity_max_abs", rtol=0.0, atol=0.0)
        _close(actual.get("full_energy"), reversal_values[arm]["full_energy"], name=f"composition reversal {arm} full_energy")
    for field in ("full_energy", "position_energy"):
        declared = reversal_states.get(field)
        if not isinstance(declared, Mapping) or set(declared) != {"minus", "plus"}:
            _fail(f"composition reversal {field} evidence is incomplete")
        for arm in ("minus", "plus"):
            _close(declared.get(arm), reversal_values[arm]["full_energy"], name=f"composition reversal {field}.{arm}")
    _close(reversal_states.get("velocity_max_abs"), 0.0, name="composition reversal velocity_max_abs", rtol=0.0, atol=0.0)
    for scale in range(params["scale_count"]):
        _close(reversal_values["minus"]["position_density"][scale], reversal_values["plus"]["position_density"][scale], name=f"composition reversal position_density[{scale}]")
        if reversal_values["minus"]["epsilon"][scale] * reversal_values["plus"]["epsilon"][scale] >= 0.0:
            _fail(f"composition reversal epsilon does not change sign at scale {scale}")
    _close(reversal_values["minus"]["full_energy"], reversal_values["plus"]["full_energy"], name="composition reversal full_energy")
    if any(value is not True for value in status["conditions"].values()):
        _fail("G4 status contains a false condition")
    return {"status": STATUS, "root": str(root), "run_id": index["run_id"], "parent_w3n_run_id": parent_index["run_id"], "control_ids": list(CONTROL_IDS), "scale_count": params["scale_count"], "mode_count": params["mode_count"], "batch_count": params["batch_limit"]}


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT_ROOT
    try:
        result = verify(target)
    except Exception as exc:
        print(f"W4/G4 FAIL: {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
