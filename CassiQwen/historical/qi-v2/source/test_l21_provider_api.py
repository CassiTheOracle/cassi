"""Native-Qi provider continuation and ownership smoke check."""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path


URL = os.environ.get("CASSI_PROVIDER_URL", "http://127.0.0.1:8086/v1/chat/completions")
STATE = Path(os.environ.get("CASSI_PROVIDER_STATE", str(Path(__file__).resolve().parent / "_diag" / "cassi-qi-native" / "provider-sessions")))
MODEL = "cassi-qi-language-v1"


def request() -> dict:
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "The field remembers"}],
        "max_tokens": 2,
        "user": "field-checkpoint-session",
    }
    value = urllib.request.Request(URL, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(value, timeout=300) as response:
        result = json.loads(response.read().decode("utf-8"))
    cassi = result.get("cassi", {})
    displacement = cassi.get("displacement_receipt", {})
    if not result.get("choices") or not cassi.get("field_text_receipt_sha256"):
        raise AssertionError("provider response lacks native-Qi text receipt")
    if displacement.get("schema") != "cassi.qi-native-displacement.v1":
        raise AssertionError("provider response lacks native-Qi displacement receipt")
    counts = displacement.get("qwen_serving", {}).get("counts", {})
    if isinstance(counts, dict) and any(value != 0 for value in counts.values()):
        raise AssertionError("live Qwen serving count is nonzero")
    architecture = displacement.get("architecture", {})
    if architecture.get("adaptive_persistent_tensor_count") != 1:
        raise AssertionError("adaptive_persistent_tensor_count is not exactly one")
    for key in ("learned_parameter_count", "neural_layer_count", "optimizer_state_bytes", "engineered_feature_width"):
        if architecture.get(key, 0) != 0:
            raise AssertionError(f"classical-ML architecture counter {key} is nonzero")
    if architecture.get("probabilistic_sampler") is not False:
        raise AssertionError("probabilistic_sampler is not False")
    if architecture.get("state_layout") != "[S,9M,B]":
        raise AssertionError("state_layout is not the canonical Qi layout")
    if displacement.get("field_text", {}).get("all_outputs_field_owned") is not True:
        raise AssertionError("committed outputs are not marked field-owned")
    if displacement.get("teacher", {}).get("called") is not False:
        raise AssertionError("teacher was called in a field-only runtime")
    return result


def main() -> int:
    first = request()
    second = request()
    if first["cassi"]["state_out_sha256"] == second["cassi"]["state_out_sha256"]:
        raise AssertionError("persistent field session did not advance")
    if not STATE.is_dir() or not list(STATE.glob("*.pt")):
        raise AssertionError("provider did not write an atomic session checkpoint")
    print(json.dumps({"first": first["choices"][0]["message"]["content"], "second": second["choices"][0]["message"]["content"], "checkpoint": str(STATE)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
