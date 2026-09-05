from __future__ import annotations

import json
from pathlib import Path

import torch

from cassi_qi_boundary import QiLinearBoundaryPort
from cassi_qi_boundary_permeability import (
    REQUIRED_OPENNESS_CONTROLS,
    QiBoundaryPermeabilityDescriptor,
    QiBoundaryPermeabilityProfile,
    QiSensoryOpennessReceipt,
    validate_permeability_profile,
    validate_sensory_openness_receipt,
)
from cassi_qi_profile import canonical_hash
from cassi_qi_scattering import validate_scattering_receipt
_REPOSITORY_ROOT = Path(__file__).resolve().parent


def run(*, evidence_path: str | Path = "_diag/cassi_qi_boundary_permeability.json") -> dict[str, object]:
    port = QiLinearBoundaryPort.create(name="optical", observation_rows=((1 + 0j, 0j), (0j, 1 + 0j)), source_metric=(1.0, 1.0), field_metric=(1.0, 1.0), gain=1.0, port_indices=(0, 1))
    descriptor = QiBoundaryPermeabilityDescriptor.create(port_id="optical", interface_id="sensory:optical:scale:0", scale=0, component=0, port=port, characteristic_basis=(1 + 0j, 0j), metric=(1.0, 1.0), geometry_sha256=canonical_hash({"scale": 0}, "cassi.qi-flow-run-geometry.v1"), operator_sha256=canonical_hash({"port": port.descriptor_sha256}, "cassi.qi-flow-run-operator.v1"), metric_sha256=canonical_hash({"metric": [1.0, 1.0]}, "cassi.qi-flow-run-metric.v1"))
    profile = QiBoundaryPermeabilityProfile.create(descriptor=descriptor)
    validate_permeability_profile(profile)
    closed = torch.tensor([-1 + 0j, 0j], dtype=torch.complex128)
    open_state = torch.tensor([1 + 0j, 0j], dtype=torch.complex128)
    live = profile.scatter(1 + 0.25j, duration=2.0, state=closed, state_samples=(closed, open_state), state_gate_mode="live")
    frozen = profile.scatter(1 + 0.25j, duration=2.0, state=closed, state_samples=(closed, open_state), state_gate_mode="frozen")
    admission = profile.admit_scratch(open_state, incident_amplitude=1 + 0.25j, duration=1.0, source_cursor=3)
    if not admission.accepted or admission.scattering_receipt is None:
        raise RuntimeError(admission.failure_reason or "positive ingress rejected")
    validate_scattering_receipt(admission.scattering_receipt, port=descriptor.scattering_port(profile.profile_sha256))
    openness = QiSensoryOpennessReceipt.create(profile=profile, pre_state=closed, post_state=open_state, pre_scatter=profile.scatter(1 + 0j, duration=1.0, state=closed), post_scatter=profile.scatter(1 + 0j, duration=1.0, state=open_state), source_free_horizon=profile.recovery_horizon, recovery_work=0.1, downstream_return_sha256=(canonical_hash({"return": 1}, "cassi.qi-flow-run-return.v1"),), controls=REQUIRED_OPENNESS_CONTROLS)
    validate_sensory_openness_receipt(openness)
    rejected = profile.admit_scratch(open_state, incident_amplitude=0j, duration=1.0, source_cursor=3)
    result = {"status": "PASS", "profile_sha256": profile.profile_sha256, "descriptor_sha256": descriptor.descriptor_sha256, "live_admitted_work": live.W_transmitted.payload(), "frozen_admitted_work": frozen.W_transmitted.payload(), "receipt_sha256": admission.scattering_receipt.self_sha256, "openness_receipt_sha256": openness.self_sha256, "zero_work_rejected": not rejected.accepted and rejected.failure_reason == "ZERO_INCIDENT_WORK"}
    out = Path(evidence_path)
    if not out.is_absolute():
        out = _REPOSITORY_ROOT / out
    out = out.resolve()
    try:
        out.relative_to(_REPOSITORY_ROOT)
    except ValueError as exc:
        raise ValueError("evidence_path must remain within repository root") from exc
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
