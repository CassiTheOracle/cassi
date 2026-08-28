"""Strict stdlib-only verifier for one immutable W5/G5 engineering exchange artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent
W4R_RUN = "bf5c141a22f30e9b20bb0cefcebf4cb7d0989dc91ae24baa11511f544604530e"
W4R_PROFILE = "838a21ab6bab7f10898fa0bba9f786450141e4f46af0f075ddebb0108b323f22"
W4R_ROOT = "6c8f932e34b38394202c4f9ef685c0edd45efc5b05137d218673de42f28eb525"
W4R_EXTENSION = "2d9b98645ef11c2c4a5378fc93397bb24b6c1c9a6996946d4ba13083a2592a0e"
W4R_CANDIDATE = "467a7ac93b0699afcd45ea16c98f921c4402ee80cd95120a66d2fc8639148335"
G3_RUN = "1b36f54f4e669b818bba422726d051f1f928db43e64d812c6bd8e93e1159bc48"
G3_CERT = "c189a80b10f5c6bc98e0658da6703054f93ee61aacd2cd4d473d5acc1d62254b"
INDEX_SCHEMA = "cassi.qi-flow-w5-run-index.v1"
ARTIFACT_DOMAIN = "cassi.qi-flow-w5-artifact.v1"
PROFILE_DOMAIN = "cassi.qi-flow-w5-exchange-profile.v1"
ROOT_DOMAIN = "cassi.qi-flow-w5-exchange-root.v1"
LAW_DOMAIN = "cassi.qi-flow-w5-integrated-exchange-flux-law.v1"
RECEIPT_DOMAIN = "cassi.qi-flow-w5-exchange-receipt.v1"
INTEGRATED_DOMAIN = "cassi.qi-flow-w5-integrated-receipt.v1"
CANDIDATE_DOMAIN = "cassi.qi-flow-w5-exchange-candidate.v1"
RAW_DOMAIN = b"cassi.qi-flow-w5-raw-state.v1"
W4_RAW_DOMAIN = b"cassi.qi-flow-w4-raw-state.v1"
W4R_RAW_DOMAIN = b"cassi.qi-flow-w4r-raw-state.v1"
W4R_RECEIPT_DOMAIN = "cassi.qi-flow-w4r-topology-receipt.v1"
W4_RECEIPT_DOMAIN = "cassi.qi-flow-w4-carrier-receipt.v1"
W3_RECEIPT_DOMAIN = "cassi.qi-flow-transport-w3-receipt.v1"
EXPECTED_SOURCES = {
    "cassi_qi_exchange.py", "run_cassi_qi_exchange.py", "verify_cassi_qi_exchange.py", "test_cassi_qi_exchange.py",
    "cassi_qi_numerical_certificate.py", "cassi_qi_field.py", "cassi_qi_geometry.py", "cassi_qi_transport.py",
    "cassi_qi_carrier.py", "cassi_qi_topology.py", "cassi_qi_profile.py",
}
PASS_CONTROLS = {
    "zero-conversion-exact-noop", "uniform-zero-flux", "manufactured-periodic-flux-divergence",
    "positive-phase-current", "negative-phase-current", "yang-yin-exchange", "amplitude-base", "amplitude-doubled",
    "spatial-sign-reversal", "conversion-term-off", "flux-term-off",
}
REJECT_CONTROLS = {"source-rejection", "nonfinite-rejection", "certificate-rejection", "profile-rejection"}


class VerificationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> Any:
    raise VerificationError(f"nonfinite JSON constant: {value}")


def f64(value: Any) -> float:
    require(isinstance(value, str) and value.startswith("f64:") and len(value) == 20, "canonical f64 required")
    result = struct.unpack(">d", bytes.fromhex(value[4:]))[0]
    require(math.isfinite(result) and not (result == 0.0 and math.copysign(1.0, result) < 0.0), "invalid f64")
    return result


def number(value: Any) -> float:
    return f64(value) if isinstance(value, str) and value.startswith("f64:") else float(value)


def validate(value: Any) -> None:
    if value is None or isinstance(value, bool) or (isinstance(value, int) and not isinstance(value, bool)):
        return
    if isinstance(value, float):
        raise VerificationError("decimal JSON number forbidden")
    if isinstance(value, str):
        value.encode("utf-8")
        if value.startswith("f64:"):
            f64(value)
        return
    if isinstance(value, list):
        for item in value:
            validate(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            require(isinstance(key, str), "non-string JSON key")
            validate(item)
        return
    raise VerificationError("unsupported canonical value")


def canonical(value: Any) -> bytes:
    validate(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any, domain: str) -> str:
    payload, raw_domain = canonical(value), domain.encode("utf-8")
    return hashlib.sha256(len(raw_domain).to_bytes(8, "big") + raw_domain + len(payload).to_bytes(8, "big") + payload).hexdigest()

def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes(), object_pairs_hook=_pairs, parse_constant=_constant)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"object required: {path}")
    validate(value)
    return value


def self_hash(value: Mapping[str, Any], domain: str, name: str = "self_sha256") -> None:
    body = dict(value)
    claim = body.pop(name, None)
    require(isinstance(claim, str) and claim == digest(body, domain), f"bad {name} for {domain}")


def raw_hash(raw: bytes, domain: bytes = RAW_DOMAIN) -> str:
    return sha(len(domain).to_bytes(8, "big") + domain + len(raw).to_bytes(8, "big") + raw)


def decode(raw: bytes) -> list[float]:
    require(len(raw) == 4 * 9 * 32 * 8, "unexpected sole-field raw length")
    result = list(struct.unpack("<1152d", raw))
    require(all(math.isfinite(item) for item in result), "nonfinite raw state")
    return result


def index_of(scale: int, component: int, mode: int) -> int:
    return scale * 288 + component * 32 + mode


def grid_index(z: int, y: int, x: int) -> int:
    return (z * 4 + y) * 4 + x


def first(values: list[float], axis: int, z: int, y: int, x: int, spacing: tuple[float, float, float]) -> float:
    if axis == 0:
        return (values[grid_index((z + 1) % 2, y, x)] - values[grid_index((z - 1) % 2, y, x)]) / (2.0 * spacing[0])
    if axis == 1:
        return (values[grid_index(z, (y + 1) % 4, x)] - values[grid_index(z, (y - 1) % 4, x)]) / (2.0 * spacing[1])
    return (values[grid_index(z, y, (x + 1) % 4)] - values[grid_index(z, y, (x - 1) % 4)]) / (2.0 * spacing[2])


def w4r_map(values: list[float], profile: Mapping[str, Any], kernel_active: bool) -> list[float]:
    h = f64(profile["hamiltonian"]["duration_s"])
    omega = f64(profile["hamiltonian"]["omega_sq"])
    if kernel_active:
        kernel = profile["kernel"]
        kxx, kxy, kyx, kyy = (f64(kernel[key]) for key in ("K_XX", "K_XY", "K_YX", "K_YY"))
    else:
        kxx = kxy = kyx = kyy = 0.0
    output = list(values)
    for mode in range(32):
        xi, yi, pxi, pyi = (index_of(3, lane, mode) for lane in (0, 2, 4, 6))
        x, y, px, py = output[xi], output[yi], output[pxi], output[pyi]
        gx, gy = omega * x + kxx * x + kxy * y, omega * y + kyx * x + kyy * y
        pxh, pyh = px - .5 * h * gx, py - .5 * h * gy
        xe, ye = x + h * pxh, y + h * pyh
        gx, gy = omega * xe + kxx * xe + kxy * ye, omega * ye + kyx * xe + kyy * ye
        output[xi], output[yi] = xe, ye
        output[pxi], output[pyi] = pxh - .5 * h * gx, pyh - .5 * h * gy
    return output


def topology_status(values: list[float], topology_profile: Mapping[str, Any]) -> tuple[str, list[list[bool]], list[list[bool]], list[list[bool]], list[list[bool]], list[list[int]]]:
    top = topology_profile["topology"]
    rho, branch, minimum, integer = (f64(top[key]) for key in ("rho_topo", "branch_margin_rad", "minimum_coverage", "integer_margin"))
    psi = [[complex(values[index_of(3, 0, y * 4 + x)], values[index_of(3, 2, y * 4 + x)]) for x in range(4)] for y in range(4)]
    valid = [[abs(psi[y][x]) >= rho for x in range(4)] for y in range(4)]
    angle = lambda item: math.atan2(item.imag, item.real)
    dx = [[angle(psi[y][x].conjugate() * psi[y][(x + 1) % 4]) for x in range(4)] for y in range(4)]
    dy = [[angle(psi[y][x].conjugate() * psi[(y + 1) % 4][x]) for x in range(4)] for y in range(4)]
    ex = [[valid[y][x] and valid[y][(x + 1) % 4] and abs(dx[y][x]) <= math.pi - branch for x in range(4)] for y in range(4)]
    ey = [[valid[y][x] and valid[(y + 1) % 4][x] and abs(dy[y][x]) <= math.pi - branch for x in range(4)] for y in range(4)]
    winding = [[(dx[y][x] + dy[y][(x + 1) % 4] - dx[(y + 1) % 4][x] - dy[y][x]) / (2.0 * math.pi) for x in range(4)] for y in range(4)]
    charge = [[int(math.floor(winding[y][x] + .5)) if winding[y][x] >= 0.0 else int(math.ceil(winding[y][x] - .5)) for x in range(4)] for y in range(4)]
    pmask = [[ex[y][x] and ey[y][x] and ex[(y + 1) % 4][x] and ey[y][(x + 1) % 4] and abs(winding[y][x] - charge[y][x]) <= integer for x in range(4)] for y in range(4)]
    coverage = sum(pmask[y][x] for y in range(4) for x in range(4)) / 16.0
    status = "VALID" if coverage >= minimum and all(valid[y][x] for y in range(4) for x in range(4)) and all(pmask[y][x] for y in range(4) for x in range(4)) else "INVALID"
    return status, valid, ex, ey, pmask, charge


def exchange_map(
    values: list[float], profile: Mapping[str, Any], *, conversion: bool, flux_enabled: bool
) -> tuple[list[float], list[dict[str, float]]]:
    params = profile["parameters"]
    h = f64(params["duration_s"])
    gamma_rate = f64(params["gamma_rate_s_inv"])
    phase_gain = f64(params["phase_gain"])
    current_gain = f64(params["current_gain"])
    length = f64(params["current_reference_length_m"])
    diffusivity = f64(params["flux_diffusivity_m2_s"])
    floor = f64(params["density_floor"])
    spacings = tuple(f64(value) for value in profile["w2_operator"]["spacings_m"])
    output = list(values)
    ledgers: list[dict[str, float]] = []
    for scale in range(4):
        yang = [complex(values[index_of(scale, 0, mode)], values[index_of(scale, 1, mode)]) for mode in range(32)]
        yin = [complex(values[index_of(scale, 2, mode)], values[index_of(scale, 3, mode)]) for mode in range(32)]
        n_y, n_i = [abs(item) ** 2 for item in yang], [abs(item) ** 2 for item in yin]
        require(all(item > floor for item in n_y + n_i), "pre-exchange density floor")
        grad_y, grad_i = [[0j] * 32 for _ in range(3)], [[0j] * 32 for _ in range(3)]
        for z in range(2):
            for y in range(4):
                for x in range(4):
                    point = grid_index(z, y, x)
                    for axis in range(3):
                        grad_y[axis][point] = complex(first([item.real for item in yang], axis, z, y, x, spacings), first([item.imag for item in yang], axis, z, y, x, spacings))
                        grad_i[axis][point] = complex(first([item.real for item in yin], axis, z, y, x, spacings), first([item.imag for item in yin], axis, z, y, x, spacings))
        gamma, flux = [0.0] * 32, [[0.0] * 32 for _ in range(3)]
        for point in range(32):
            assist = n_y[point] * n_i[point] / (n_y[point] + n_i[point])
            phase = (yang[point].conjugate() * yin[point]).imag / math.sqrt(n_y[point] * n_i[point])
            rel = [(yang[point].conjugate() * grad_y[axis][point]).imag / n_y[point] - (yin[point].conjugate() * grad_i[axis][point]).imag / n_i[point] for axis in range(3)]
            gamma[point] = gamma_rate * assist * (phase_gain * phase + current_gain * length * rel[2]) if conversion else 0.0
            for axis in range(3):
                flux[axis][point] = diffusivity * assist * rel[axis] if flux_enabled else 0.0
        divergence = [0.0] * 32
        for z in range(2):
            for y in range(4):
                for x in range(4):
                    point = grid_index(z, y, x)
                    divergence[point] = sum(first(flux[axis], axis, z, y, x, spacings) for axis in range(3))
        ly, li = [-h * item for item in gamma], [h * item for item in gamma]
        fy, fi = [-h * item for item in divergence], [h * item for item in divergence]
        target_y, target_i = [n_y[i] + ly[i] + fy[i] for i in range(32)], [n_i[i] + li[i] + fi[i] for i in range(32)]
        require(all(item > floor and math.isfinite(item) for item in target_y + target_i), "target density floor")
        next_y = [yang[i] * math.sqrt(target_y[i] / n_y[i]) for i in range(32)]
        next_i = [yin[i] * math.sqrt(target_i[i] / n_i[i]) for i in range(32)]
        for mode in range(32):
            output[index_of(scale, 0, mode)], output[index_of(scale, 1, mode)] = next_y[mode].real, next_y[mode].imag
            output[index_of(scale, 2, mode)], output[index_of(scale, 3, mode)] = next_i[mode].real, next_i[mode].imag
        pre = sum(n_y) + sum(n_i)
        post = sum(abs(item) ** 2 for item in next_y) + sum(abs(item) ** 2 for item in next_i)
        ledgers.append({
            "gamma_raw_integral": sum(gamma), "gamma_raw_l1": sum(abs(item) for item in gamma),
            "local_yang_delta": sum(ly), "local_yang_delta_l1": sum(abs(item) for item in ly),
            "local_yin_delta": sum(li), "local_yin_delta_l1": sum(abs(item) for item in li),
            "flux_yang_delta": sum(fy), "flux_yang_delta_l1": sum(abs(item) for item in fy),
            "flux_yin_delta": sum(fi), "flux_yin_delta_l1": sum(abs(item) for item in fi),
            "integrated_divergence": sum(divergence), "divergence_l1": sum(abs(item) for item in divergence),
            "source_work_proxy": sum(h * gamma[i] * ((yang[i].conjugate() * yin[i]).imag / math.sqrt(n_y[i] * n_i[i])) for i in range(32)),
            "position_density_work": .5 * (post - pre), "total_density_closure": sum(ly[i] + li[i] + fy[i] + fi[i] for i in range(32)), "realized_total_density_delta": post - pre,
        })
    return output, ledgers

def close(left: list[float], right: list[float], tolerance: float, message: str) -> None:
    require(len(left) == len(right), message)
    delta = max((abs(a - b) for a, b in zip(left, right)), default=0.0)
    require(delta <= tolerance, f"{message}: {delta}")


def verify(root: Path) -> dict[str, Any]:
    index = read_json(root / "index.json")
    self_hash(index, INDEX_SCHEMA)
    require(index.get("schema") == INDEX_SCHEMA and index.get("status") == "PASS" and index.get("engineering_candidate_only") is True and index.get("w5v_forward_domain_certificate") is None, "index status")
    records = index.get("objects")
    require(isinstance(records, list) and len(records) == index.get("object_count"), "inventory")
    for record in records:
        raw = (root / record["path"]).read_bytes()
        require(set(record) == {"path", "byte_count", "sha256"} and len(raw) == record["byte_count"] and sha(raw) == record["sha256"], "artifact object")
    parent_dir = ROOT / "_diag" / "cassi-qi-flow-w4r-final" / W4R_RUN
    parent_index_raw = (parent_dir / "index.json").read_bytes()
    parent_index = read_json(parent_dir / "index.json")
    parent_candidate = read_json(parent_dir / "gates" / "g04r-topology" / "topology.json")
    parent_profile = read_json(parent_dir / "profiles" / "topology-profile.json")
    parent_root = read_json(parent_dir / "profiles" / "topology-root.json")
    parent_extension = read_json(parent_dir / "certificate" / "extension-0003.json")
    parent = {"run_id": W4R_RUN, "index_sha256": sha(parent_index_raw), "candidate_sha256": W4R_CANDIDATE, "topology_profile_sha256": W4R_PROFILE, "topology_root_sha256": W4R_ROOT, "certificate_extension_sha256": W4R_EXTENSION, "preserved": True}
    require(parent_index["run_id"] == W4R_RUN and parent_candidate["self_sha256"] == W4R_CANDIDATE and parent_profile["profile_sha256"] == W4R_PROFILE and parent_root["self_sha256"] == W4R_ROOT and parent_extension["self_sha256"] == W4R_EXTENSION, "frozen W4R identity")
    require(index.get("parents") == [parent] and index.get("source_exact_successor_of") == parent and read_json(root / "run-spec" / "parent-w4r.json") == parent, "corrected W4R parent")
    material = {"schema": ARTIFACT_DOMAIN, "parents": [parent], "source_exact_successor_of": parent, "objects": records, "exchange_profile_sha256": index["exchange_profile_sha256"], "exchange_root_sha256": index["exchange_root_sha256"], "law_sha256": index["law_sha256"], "engineering_candidate_only": True}
    require(index["run_id"] == digest(material, ARTIFACT_DOMAIN), "run identity")
    source_identity = read_json(root / "run-spec" / "source-identity.json")
    sources = source_identity.get("sources")
    require(isinstance(sources, list) and {item.get("path") for item in sources} == EXPECTED_SOURCES, "source inventory")
    for source in sources:
        raw = (root / "sources" / source["path"]).read_bytes()
        require(sha(raw) == source["sha256"] and len(raw) == source["byte_count"], "source snapshot")
    profile = read_json(root / "profile" / "exchange-profile.json")
    body = dict(profile)
    profile_claim = body.pop("profile_sha256")
    require(profile_claim == digest(body, PROFILE_DOMAIN) == index["exchange_profile_sha256"], "profile identity")
    law = profile["law"]
    require(profile["law_sha256"] == digest(law, LAW_DOMAIN) == index["law_sha256"], "law identity")
    require(profile["w4r_parent_run_id"] == W4R_RUN and profile["w4r_topology_profile_sha256"] == W4R_PROFILE and profile["w4r_topology_root_sha256"] == W4R_ROOT and profile["w4r_certificate_extension_sha256"] == W4R_EXTENSION and profile["w4r_candidate_sha256"] == W4R_CANDIDATE, "profile W4R binding")
    require(law["no_additive_phase_source"] is True and law["no_damping"] is True and law["no_projection"] is True and law["no_clipping_or_bounding"] is True and law["no_new_persistent_state"] is True, "law restrictions")
    exchange_root = read_json(root / "profile" / "exchange-root.json")
    self_hash(exchange_root, ROOT_DOMAIN)
    require(exchange_root["profile_sha256"] == profile_claim and exchange_root["law_sha256"] == profile["law_sha256"] and exchange_root["self_sha256"] == index["exchange_root_sha256"] and exchange_root["persistent_state_added"] is False and exchange_root["w5v_forward_domain_certificate"] is None, "root binding")
    frozen_certificate = read_json(root / "certificate" / "g3n-certificate-root.json")
    require(frozen_certificate["self_sha256"] == G3_CERT and frozen_certificate == read_json(ROOT / "_diag" / "cassi-qi-flow-w3n-final" / G3_RUN / "certificate" / "certificate-root.json"), "frozen certificate")
    candidate = read_json(root / "gates" / "g05-exchange" / "exchange.json")
    self_hash(candidate, CANDIDATE_DOMAIN)
    require(candidate["parent_w4r"] == parent and candidate["exchange_profile_sha256"] == profile_claim and candidate["exchange_root_sha256"] == exchange_root["self_sha256"] and candidate["law_sha256"] == profile["law_sha256"] and candidate["engineering_candidate_only"] is True and candidate["w5v_forward_domain_certificate"] is None and candidate["certificate_extension_added"] is False, "candidate provenance")
    require(not any(record["path"].startswith("certificate/extension") for record in records), "no placeholder W5 certificate extension")
    controls = candidate.get("controls")
    require(isinstance(controls, dict) and set(controls) == PASS_CONTROLS | REJECT_CONTROLS, "control inventory")
    for name, control in controls.items():
        raw_pre = (root / "fixtures" / f"{name}-predecessor.bin").read_bytes()
        require(control["predecessor_raw_sha256"] == raw_hash(raw_pre), f"{name} predecessor identity")
        if name in REJECT_CONTROLS:
            require(control["actual_decision"] == "REJECT" and control["candidate_exposed"] is False and control["candidate_raw_sha256"] is None, f"{name} precommit rejection")
            self_hash(control["receipt"], INTEGRATED_DOMAIN)
            continue
        require(control["actual_decision"] == "PASS" and control["candidate_exposed"] is True, f"{name} accepted")
        raw_w3 = (root / "fixtures" / f"{name}-w3_guarded_transport.bin").read_bytes()
        raw_w4 = (root / "fixtures" / f"{name}-w4_corrected_carrier.bin").read_bytes()
        raw_w4r = (root / "fixtures" / f"{name}-w4r_hamiltonian_topology.bin").read_bytes()
        raw_final = (root / "fixtures" / f"{name}-candidate.bin").read_bytes()
        receipt = control["receipt"]
        self_hash(receipt, INTEGRATED_DOMAIN)
        require(control["candidate_raw_sha256"] == raw_hash(raw_final) == receipt["candidate_state_sha256"], f"{name} final raw identity")
        stages = receipt["stages"]
        require(stages["w3_guarded_transport"]["direct_parent_state_sha256"] == raw_hash(raw_pre) and stages["w3_guarded_transport"]["candidate_state_sha256"] == raw_hash(raw_w3), f"{name} W3 direct parent")
        require(stages["w4_corrected_carrier"]["direct_parent_state_sha256"] == raw_hash(raw_w3) and stages["w4_corrected_carrier"]["candidate_state_sha256"] == raw_hash(raw_w4), f"{name} W4 direct parent")
        require(stages["w4r_hamiltonian_topology"]["direct_parent_state_sha256"] == raw_hash(raw_w4) and stages["w4r_hamiltonian_topology"]["candidate_state_sha256"] == raw_hash(raw_w4r), f"{name} W4R direct parent")
        require(stages["w5_exchange_flux"]["direct_parent_state_sha256"] == raw_hash(raw_w4r) and stages["w5_exchange_flux"]["candidate_state_sha256"] == raw_hash(raw_final), f"{name} W5 direct parent")
        w3_receipt, w4_receipt, w4r_receipt, w5_receipt = (stages[key]["receipt"] for key in ("w3_guarded_transport", "w4_corrected_carrier", "w4r_hamiltonian_topology", "w5_exchange_flux"))
        require(
            w3_receipt["schema"] == "cassi.qi-flow-field-transport.v3"
            and w3_receipt["status"] == "PASS"
            and w3_receipt["numerical_guard"]["decision"] == "ACCEPT",
            f"{name} guarded W3 receipt",
        )
        self_hash(w4_receipt, W4_RECEIPT_DOMAIN)
        self_hash(w4r_receipt, W4R_RECEIPT_DOMAIN)
        self_hash(w5_receipt, RECEIPT_DOMAIN)
        require(w4_receipt["guarded_w3_candidate_state_sha256"] == raw_hash(raw_w3, W4_RAW_DOMAIN), f"{name} W4 guarded W3 linkage")
        expected_w4r = w4r_map(decode(raw_w4), parent_profile, bool(w4r_receipt["kernel_active"]))
        close(expected_w4r, decode(raw_w4r), 3.0e-14, f"{name} W4R raw reconstruction")
        expected_final, ledgers = exchange_map(decode(raw_w4r), profile, conversion=bool(control["conversion_enabled"]), flux_enabled=bool(control["flux_enabled"]))
        close(expected_final, decode(raw_final), 4.0e-13, f"{name} full integrated W5 candidate reconstruction")
        recorded_ledgers = w5_receipt["per_scale_work_source_ledger"]
        require(len(recorded_ledgers) == len(ledgers) == 4, f"{name} scale ledger")
        ledger_keys = set(ledgers[0])
        for expected, recorded in zip(ledgers, recorded_ledgers, strict=True):
            for key in ledger_keys:
                require(abs(expected[key] - number(recorded[key])) <= 2.0e-10, f"{name} {key} reconstruction")
        aggregate = w5_receipt["continuity"]["aggregate"]
        for key in ledger_keys:
            if key in aggregate:
                require(abs(sum(ledger[key] for ledger in ledgers) - number(aggregate[key])) <= 3.0e-10, f"{name} aggregate {key}")
        status, valid, ex, ey, pmask, charge = topology_status(decode(raw_final), parent_profile)
        recorded_topology = receipt["post_exchange_topology"]
        require(status == "VALID" and recorded_topology["status"] == status and recorded_topology["valid_vertex_mask"] == valid and recorded_topology["edge_x_mask"] == ex and recorded_topology["edge_y_mask"] == ey and recorded_topology["plaquette_mask"] == pmask and recorded_topology["charge"] == charge, f"{name} W5 topology reconstruction")
    measurements = candidate["measurements"]
    require(measurements["zero_conversion_raw_noop"] is True and number(measurements["uniform_zero_flux"]["divergence_l1"]) == 0.0 and number(measurements["uniform_zero_flux"]["flux_yang_delta_l1"]) == 0.0, "zero controls")
    require(number(measurements["manufactured_periodic_flux"]["divergence_l1"]) > 0.0 and abs(number(measurements["manufactured_periodic_flux"]["integrated_divergence"])) <= 1.0e-12, "periodic flux control")
    require(number(measurements["positive_gamma"]) * number(measurements["negative_gamma"]) < 0.0 and number(measurements["conversion_term_off"]["gamma_raw_l1"]) == 0.0 and number(measurements["flux_term_off"]["divergence_l1"]) == 0.0 and abs(number(measurements["direct_amplitude_scaling_ratio"]) - 4.0) <= 1.0e-12, "G5 measurements")
    replay_a = (root / "fixtures" / "deterministic-replay-a-candidate.bin").read_bytes()
    replay_b = (root / "fixtures" / "deterministic-replay-b-candidate.bin").read_bytes()
    require(replay_a == replay_b and measurements["replay"]["raw_equal"] is True, "deterministic replay")
    status = read_json(root / "gates" / "g05-exchange" / "status.json")
    self_hash(status, "cassi.qi-flow-g5-status.v1")
    require(status["status"] == "PASS" and status["engineering_candidate_only"] is True and status["w5v_forward_domain_certificate"] is None and all(status["conditions"].values()), "G5 status")
    return {"gate": "G5", "status": "PASS", "run_id": index["run_id"], "profile_sha256": profile_claim, "root_sha256": exchange_root["self_sha256"], "law_sha256": profile["law_sha256"], "candidate_sha256": candidate["self_sha256"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path, nargs="?", default=None)
    args = parser.parse_args()
    root = args.artifact or max((ROOT / "_diag" / "cassi-qi-flow-w5-final").iterdir(), key=lambda item: item.stat().st_mtime)
    try:
        print(json.dumps(verify(root), sort_keys=True, separators=(",", ":")))
    except Exception as exc:
        print(f"W5/G5 VERIFY FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
