"""Materialize immutable W5/G5 engineering exchange-flow evidence without W5V certification."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import math
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

import torch

from cassi_qi_carrier import load_w4_carrier_profile
from cassi_qi_exchange import (
    W5_PARENT_W4R_CANDIDATE,
    W5_PARENT_W4R_EXTENSION,
    W5_PARENT_W4R_PROFILE,
    W5_PARENT_W4R_ROOT,
    W5_PARENT_W4R_RUN,
    load_w5_exchange_profile,
    transition_w5_exchange,
    transition_w5_integrated,
)
from cassi_qi_field import QiFlowStateV3
from cassi_qi_geometry import load_w2_geometry_profile
from cassi_qi_numerical_certificate import raw_state_bytes_from_field
from cassi_qi_profile import canonical_hash, canonical_json_bytes, canonical_json_loads
from cassi_qi_topology import load_w4r_topology_profile
from cassi_qi_transport import load_w3_transport_profile

ROOT = Path(__file__).resolve().parent
W4R_ROOT = ROOT / "_diag" / "cassi-qi-flow-w4r-final" / W5_PARENT_W4R_RUN
G3_ROOT = ROOT / "_diag" / "cassi-qi-flow-w3n-final" / "1b36f54f4e669b818bba422726d051f1f928db43e64d812c6bd8e93e1159bc48"
OUTPUT_ROOT = ROOT / "_diag" / "cassi-qi-flow-w5-final"
INDEX_SCHEMA = "cassi.qi-flow-w5-run-index.v1"
ARTIFACT_DOMAIN = "cassi.qi-flow-w5-artifact.v1"
SOURCE_PATHS = (
    "cassi_qi_exchange.py", "run_cassi_qi_exchange.py", "verify_cassi_qi_exchange.py", "test_cassi_qi_exchange.py",
    "cassi_qi_numerical_certificate.py", "cassi_qi_field.py", "cassi_qi_geometry.py", "cassi_qi_transport.py",
    "cassi_qi_carrier.py", "cassi_qi_topology.py", "cassi_qi_profile.py",
)


class ExchangeArtifactError(ValueError):
    pass


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    result = canonical_json_loads(path.read_bytes())
    if not isinstance(result, dict):
        raise ExchangeArtifactError(f"object required: {path}")
    return result


def _write(stage: Path, relative: str, raw: bytes) -> None:
    path = stage / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def _write_json(stage: Path, relative: str, value: Any) -> None:
    _write(stage, relative, canonical_json_bytes(value))


def _records(root: Path) -> list[dict[str, Any]]:
    return [
        {"path": item.relative_to(root).as_posix(), "byte_count": len(raw := item.read_bytes()), "sha256": _sha(raw)}
        for item in sorted(root.rglob("*"))
        if item.is_file() and item.name != "index.json"
    ]


def _copy_sources(stage: Path) -> list[dict[str, Any]]:
    records = []
    for relative in SOURCE_PATHS:
        raw = (ROOT / relative).read_bytes()
        _write(stage, f"sources/{relative}", raw)
        records.append({"path": relative, "byte_count": len(raw), "sha256": _sha(raw)})
    return records


def _raw_hash(raw: bytes) -> str:
    domain = b"cassi.qi-flow-w5-raw-state.v1"
    return _sha(len(domain).to_bytes(8, "big") + domain + len(raw).to_bytes(8, "big") + raw)


def _state_from_raw(raw: bytes) -> QiFlowStateV3:
    if len(raw) != 4 * 9 * 32 * 8:
        raise ExchangeArtifactError("unexpected frozen sole-field raw length")
    field = torch.frombuffer(bytearray(raw), dtype=torch.float64).clone().reshape(4, 288, 1)
    return QiFlowStateV3(field.contiguous())


def _manufactured_state(*, amplitude: float = 0.22, conjugate: bool = False, swap: bool = False, sign: float = 1.0, uniform: bool = False) -> QiFlowStateV3:
    modes = 32
    field = torch.zeros((4, 9 * modes, 1), dtype=torch.float64)
    y, x = torch.meshgrid(torch.arange(4, dtype=torch.float64), torch.arange(4, dtype=torch.float64), indexing="ij")
    theta_yang = torch.zeros_like(x) if uniform else 0.45 * x + 0.20 * y
    theta_yin = torch.full_like(x, 1.05) if uniform else 1.05 - 0.25 * x + 0.15 * y
    if conjugate:
        theta_yang, theta_yin = -theta_yang, -theta_yin
    for scale in range(4):
        real_yang = (sign * amplitude * torch.cos(theta_yang)).repeat(2, 1, 1).reshape(modes)
        imag_yang = (sign * amplitude * torch.sin(theta_yang)).repeat(2, 1, 1).reshape(modes)
        real_yin = (sign * 0.82 * amplitude * torch.cos(theta_yin)).repeat(2, 1, 1).reshape(modes)
        imag_yin = (sign * 0.82 * amplitude * torch.sin(theta_yin)).repeat(2, 1, 1).reshape(modes)
        if swap:
            real_yang, real_yin = real_yin, real_yang
            imag_yang, imag_yin = imag_yin, imag_yang
        field[scale, 0:modes, 0] = real_yang
        field[scale, modes:2 * modes, 0] = imag_yang
        field[scale, 2 * modes:3 * modes, 0] = real_yin
        field[scale, 3 * modes:4 * modes, 0] = imag_yin
    return QiFlowStateV3(field.contiguous())


def _run_integrated(
    *,
    control_id: str,
    state: QiFlowStateV3,
    geometry: Any,
    transport: Any,
    carrier: Any,
    topology: Any,
    exchange: Any,
    certificate: Mapping[str, Any],
    source: Any = None,
    conversion_enabled: bool = True,
    flux_enabled: bool = True,
    expected: str,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    step = transition_w5_integrated(
        state,
        geometry_profile=geometry,
        transport_profile=transport,
        carrier_profile=carrier,
        topology_profile=topology,
        exchange_profile=exchange,
        numerical_certificate=certificate,
        source=source,
        conversion_enabled=conversion_enabled,
        flux_enabled=flux_enabled,
    )
    actual = "PASS" if step.committable else "REJECT"
    if actual != expected:
        raise ExchangeArtifactError(f"{control_id}: expected {expected}, got {actual}: {step.failure_reason}")
    blobs = {"predecessor": raw_state_bytes_from_field(state.field)}
    result = {
        "control_id": control_id,
        "expected_decision": expected,
        "actual_decision": actual,
        "predecessor_raw_sha256": _raw_hash(blobs["predecessor"]),
        "candidate_exposed": step.candidate is not None,
        "receipt": dict(step.receipt),
        "receipt_sha256": step.receipt["self_sha256"],
        "conversion_enabled": conversion_enabled,
        "flux_enabled": flux_enabled,
    }
    if step.candidate is not None:
        blobs["candidate"] = raw_state_bytes_from_field(step.candidate.field)
        result["candidate_raw_sha256"] = _raw_hash(blobs["candidate"])
        result["candidate_raw_matches_receipt"] = result["candidate_raw_sha256"] == step.receipt["candidate_state_sha256"]
        if step.stage_candidates is None:
            raise ExchangeArtifactError(f"{control_id}: accepted schedule omitted stage candidates")
        for name, candidate in step.stage_candidates.items():
            blobs[name] = raw_state_bytes_from_field(candidate.field)
        exchange_receipt = step.receipt["stages"]["w5_exchange_flux"]["receipt"]
        result["w5_continuity"] = exchange_receipt["continuity"]
        result["post_exchange_topology"] = step.receipt["post_exchange_topology"]
    else:
        result["candidate_raw_sha256"] = None
    return result, blobs


def _run() -> Path:
    parent_index_raw = (W4R_ROOT / "index.json").read_bytes()
    parent_index = _read_json(W4R_ROOT / "index.json")
    parent_candidate = _read_json(W4R_ROOT / "gates" / "g04r-topology" / "topology.json")
    parent_profile = _read_json(W4R_ROOT / "profiles" / "topology-profile.json")
    parent_root = _read_json(W4R_ROOT / "profiles" / "topology-root.json")
    parent_extension = _read_json(W4R_ROOT / "certificate" / "extension-0003.json")
    certificate = _read_json(G3_ROOT / "certificate" / "certificate-root.json")
    if (
        parent_index["run_id"] != W5_PARENT_W4R_RUN
        or parent_profile["profile_sha256"] != W5_PARENT_W4R_PROFILE
        or parent_root["self_sha256"] != W5_PARENT_W4R_ROOT
        or parent_extension["self_sha256"] != W5_PARENT_W4R_EXTENSION
    ):
        raise ExchangeArtifactError("frozen W4R parent linkage mismatch")
    geometry = load_w2_geometry_profile()
    transport = load_w3_transport_profile(geometry=geometry)
    carrier = load_w4_carrier_profile(geometry=geometry, transport=transport)
    topology = load_w4r_topology_profile(geometry=geometry)
    exchange = load_w5_exchange_profile(geometry=geometry)
    parent = {
        "run_id": W5_PARENT_W4R_RUN,
        "index_sha256": _sha(parent_index_raw),
        "candidate_sha256": W5_PARENT_W4R_CANDIDATE,
        "topology_profile_sha256": W5_PARENT_W4R_PROFILE,
        "topology_root_sha256": W5_PARENT_W4R_ROOT,
        "certificate_extension_sha256": W5_PARENT_W4R_EXTENSION,
        "preserved": True,
    }
    base = _manufactured_state()
    plans = {
        "zero-conversion-exact-noop": (base, None, False, False, "PASS"),
        "uniform-zero-flux": (_manufactured_state(uniform=True), None, True, True, "PASS"),
        "manufactured-periodic-flux-divergence": (_manufactured_state(), None, False, True, "PASS"),
        "positive-phase-current": (_manufactured_state(), None, True, True, "PASS"),
        "negative-phase-current": (_manufactured_state(conjugate=True), None, True, True, "PASS"),
        "yang-yin-exchange": (_manufactured_state(swap=True), None, True, True, "PASS"),
        "amplitude-base": (_manufactured_state(amplitude=0.16), None, True, False, "PASS"),
        "amplitude-doubled": (_manufactured_state(amplitude=0.32), None, True, False, "PASS"),
        "spatial-sign-reversal": (_manufactured_state(sign=-1.0), None, True, True, "PASS"),
        "conversion-term-off": (_manufactured_state(), None, False, True, "PASS"),
        "flux-term-off": (_manufactured_state(), None, True, False, "PASS"),
        "source-rejection": (_manufactured_state(), {"source": "blocked-source"}, True, True, "REJECT"),
        "nonfinite-rejection": (_state_from_raw(raw_state_bytes_from_field(_manufactured_state().field)), None, True, True, "REJECT"),
        "certificate-rejection": (_manufactured_state(), None, True, True, "REJECT"),
        "profile-rejection": (_manufactured_state(), None, True, True, "REJECT"),
    }
    plans["nonfinite-rejection"][0].field[0, 0, 0] = float("nan")
    controls: dict[str, dict[str, Any]] = {}
    blobs: dict[str, dict[str, bytes]] = {}
    for name, (state, source, conversion_enabled, flux_enabled, expected) in plans.items():
        selected_certificate = certificate
        selected_exchange = exchange
        if name == "certificate-rejection":
            selected_certificate = dict(certificate)
            selected_certificate["self_sha256"] = "0" * 64
        if name == "profile-rejection":
            selected_exchange = replace(exchange, profile_sha256="0" * 64)
        result, payloads = _run_integrated(
            control_id=name,
            state=state,
            geometry=geometry,
            transport=transport,
            carrier=carrier,
            topology=topology,
            exchange=selected_exchange,
            certificate=selected_certificate,
            source=source,
            conversion_enabled=conversion_enabled,
            flux_enabled=flux_enabled,
            expected=expected,
        )
        controls[name], blobs[name] = result, payloads
    replay_a, replay_a_blobs = _run_integrated(
        control_id="deterministic-replay-a", state=base, geometry=geometry, transport=transport, carrier=carrier,
        topology=topology, exchange=exchange, certificate=certificate, expected="PASS",
    )
    replay_b, replay_b_blobs = _run_integrated(
        control_id="deterministic-replay-b", state=base, geometry=geometry, transport=transport, carrier=carrier,
        topology=topology, exchange=exchange, certificate=certificate, expected="PASS",
    )
    if replay_a_blobs["candidate"] != replay_b_blobs["candidate"] or replay_a["receipt_sha256"] != replay_b["receipt_sha256"]:
        raise ExchangeArtifactError("deterministic replay/restart failed")
    if blobs["zero-conversion-exact-noop"]["w4r_hamiltonian_topology"] != blobs["zero-conversion-exact-noop"]["candidate"]:
        raise ExchangeArtifactError("zero conversion/flux W5 map was not an exact raw no-op")
    uniform = controls["uniform-zero-flux"]["w5_continuity"]["aggregate"]
    periodic = controls["manufactured-periodic-flux-divergence"]["w5_continuity"]["aggregate"]
    if uniform["divergence_l1"] != 0.0 or uniform["flux_yang_delta_l1"] != 0.0:
        raise ExchangeArtifactError("uniform zero-flux control is not exact")
    if not periodic["divergence_l1"] > 0.0 or abs(periodic["integrated_divergence"]) > 1.0e-12:
        raise ExchangeArtifactError("manufactured periodic flux/divergence control failed")
    positive_gamma = controls["positive-phase-current"]["w5_continuity"]["aggregate"]["gamma_raw_integral"]
    negative_gamma = controls["negative-phase-current"]["w5_continuity"]["aggregate"]["gamma_raw_integral"]
    if not positive_gamma * negative_gamma < 0.0:
        raise ExchangeArtifactError("phase-current reversal did not reverse raw Gamma")
    conversion_off = controls["conversion-term-off"]["w5_continuity"]["aggregate"]
    flux_off = controls["flux-term-off"]["w5_continuity"]["aggregate"]
    if conversion_off["gamma_raw_l1"] != 0.0 or flux_off["divergence_l1"] != 0.0:
        raise ExchangeArtifactError("term-off ablation altered its disabled term")
    direct_base = transition_w5_exchange(
        _manufactured_state(amplitude=0.16), geometry_profile=geometry, exchange_profile=exchange,
        numerical_certificate=certificate, conversion_enabled=True, flux_enabled=False,
    )
    direct_doubled = transition_w5_exchange(
        _manufactured_state(amplitude=0.32), geometry_profile=geometry, exchange_profile=exchange,
        numerical_certificate=certificate, conversion_enabled=True, flux_enabled=False,
    )
    if not direct_base.committable or not direct_doubled.committable:
        raise ExchangeArtifactError("direct law amplitude scaling controls rejected")
    scaling_ratio = (
        direct_doubled.receipt["continuity"]["aggregate"]["gamma_raw_integral"]
        / direct_base.receipt["continuity"]["aggregate"]["gamma_raw_integral"]
    )
    if abs(scaling_ratio - 4.0) > 1.0e-12:
        raise ExchangeArtifactError("direct law amplitude scaling is not quadratic")
    measurements = {
        "zero_conversion_raw_noop": True,
        "uniform_zero_flux": uniform,
        "manufactured_periodic_flux": periodic,
        "positive_gamma": positive_gamma,
        "negative_gamma": negative_gamma,
        "phase_current_reversal_ratio": negative_gamma / positive_gamma,
        "yang_yin_exchange": controls["yang-yin-exchange"]["w5_continuity"],
        "spatial_sign_reversal": controls["spatial-sign-reversal"]["w5_continuity"],
        "conversion_term_off": conversion_off,
        "flux_term_off": flux_off,
        "direct_amplitude_scaling_ratio": scaling_ratio,
        "integrated_amplitude_base": controls["amplitude-base"]["w5_continuity"],
        "integrated_amplitude_doubled": controls["amplitude-doubled"]["w5_continuity"],
        "replay": {"raw_equal": True, "receipt_sha256": replay_a["receipt_sha256"]},
    }
    status = {
        "schema": "cassi.qi-flow-g5-status.v1",
        "gate": "G5",
        "status": "PASS",
        "engineering_candidate_only": True,
        "w5v_forward_domain_certificate": None,
        "conditions": {
            "frozen_w4r_parent_exact": True,
            "sole_field_no_new_persistent_state": True,
            "exact_declared_schedule": True,
            "zero_conversion_raw_noop": True,
            "periodic_continuity_closure": True,
            "phase_current_reversal": True,
            "term_off_ablations": True,
            "precommit_rejections": True,
            "deterministic_replay": True,
        },
    }
    status["self_sha256"] = canonical_hash(status, "cassi.qi-flow-g5-status.v1")
    candidate = {
        "schema": "cassi.qi-flow-w5-exchange-candidate.v1",
        "parent_w4r": parent,
        "exchange_profile_sha256": exchange.profile_sha256,
        "exchange_root_sha256": exchange.root_sha256,
        "law_sha256": exchange.law_sha256,
        "g3n_numerical_certificate_sha256": certificate["self_sha256"],
        "schedule": list(exchange.payload["split_schedule"]),
        "controls": controls,
        "measurements": measurements,
        "status_sha256": status["self_sha256"],
        "engineering_candidate_only": True,
        "w5v_forward_domain_certificate": None,
        "certificate_extension_added": False,
    }
    candidate["self_sha256"] = canonical_hash(candidate, "cassi.qi-flow-w5-exchange-candidate.v1")
    stage = Path(tempfile.mkdtemp(prefix=".w5-", dir=OUTPUT_ROOT.parent))
    try:
        source_records = _copy_sources(stage)
        _write_json(stage, "parents/w4r-parent-index.json", parent_index)
        _write_json(stage, "parents/w4r-parent-candidate.json", parent_candidate)
        _write_json(stage, "parents/w4r-parent-profile.json", parent_profile)
        _write_json(stage, "parents/w4r-parent-root.json", parent_root)
        _write_json(stage, "parents/w4r-parent-extension-0003.json", parent_extension)
        _write_json(stage, "certificate/g3n-certificate-root.json", certificate)
        _write_json(stage, "profile/exchange-profile.json", dict(exchange.payload))
        _write_json(stage, "profile/exchange-root.json", dict(exchange.root))
        _write_json(stage, "run-spec/parent-w4r.json", parent)
        _write_json(stage, "run-spec/source-identity.json", {"schema": "cassi.qi-flow-w5-source-identity.v1", "sources": source_records})
        for name, payloads in blobs.items():
            for label, raw in payloads.items():
                _write(stage, f"fixtures/{name}-{label}.bin", raw)
            _write_json(stage, f"gates/g05-exchange/controls/{name}.json", controls[name])
        for label, raw in replay_a_blobs.items():
            _write(stage, f"fixtures/deterministic-replay-a-{label}.bin", raw)
        for label, raw in replay_b_blobs.items():
            _write(stage, f"fixtures/deterministic-replay-b-{label}.bin", raw)
        _write_json(stage, "gates/g05-exchange/measurements.json", measurements)
        _write_json(stage, "gates/g05-exchange/exchange.json", candidate)
        _write_json(stage, "gates/g05-exchange/status.json", status)
        records = _records(stage)
        material = {
            "schema": ARTIFACT_DOMAIN,
            "parents": [parent],
            "source_exact_successor_of": parent,
            "objects": records,
            "exchange_profile_sha256": exchange.profile_sha256,
            "exchange_root_sha256": exchange.root_sha256,
            "law_sha256": exchange.law_sha256,
            "engineering_candidate_only": True,
        }
        index = {
            "schema": INDEX_SCHEMA,
            "run_id": canonical_hash(material, ARTIFACT_DOMAIN),
            "status": "PASS",
            "parents": [parent],
            "source_exact_successor_of": parent,
            "exchange_profile_sha256": exchange.profile_sha256,
            "exchange_root_sha256": exchange.root_sha256,
            "law_sha256": exchange.law_sha256,
            "engineering_candidate_only": True,
            "w5v_forward_domain_certificate": None,
            "object_count": len(records),
            "objects": records,
        }
        index["self_sha256"] = canonical_hash(index, INDEX_SCHEMA)
        _write_json(stage, "index.json", index)
        output = OUTPUT_ROOT / index["run_id"]
        if output.exists():
            if (output / "index.json").read_bytes() != (stage / "index.json").read_bytes():
                raise ExchangeArtifactError("immutable W5 artifact collision")
            shutil.rmtree(stage)
        else:
            OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
            shutil.move(str(stage), str(output))
        return output
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def main() -> int:
    try:
        print(_run())
    except Exception as exc:
        print(f"W5/G5 FAIL: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
