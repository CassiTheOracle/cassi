"""Field-only provider policy and fail-closed ownership checks."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


URL = os.environ.get("CASSI_PROVIDER_URL", "http://127.0.0.1:8086/v1/chat/completions")


def request(session: str, **extra: object) -> dict:
    body: dict[str, object] = {
        "model": "cassi-qi-language-v1",
        "messages": [{"role": "user", "content": f"field policy probe {session}"}],
        "max_tokens": 1,
        "user": session,
    }
    body.update(extra)
    value = urllib.request.Request(URL, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(value, timeout=300) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("choices"):
        raise AssertionError(f"provider response lacks choices: {result}")
    return result


def main() -> None:
    result = request("field-policy")
    receipt = result["cassi"]["displacement_receipt"]
    assert receipt["schema"] == "cassi.qi-native-displacement.v1"
    assert receipt["field_text"]["all_outputs_field_owned"] is True
    assert receipt["teacher"]["called"] is False and receipt["teacher"]["calls"] == 0
    counts = receipt["qwen_serving"]["counts"]
    assert all(value == 0 for value in counts.values())
    architecture = receipt["architecture"]
    assert architecture["adaptive_persistent_tensor_count"] == 1
    assert architecture["learned_parameter_count"] == 0
    assert architecture["neural_layer_count"] == 0
    assert architecture["optimizer_state_bytes"] == 0
    assert architecture["engineered_feature_width"] == 0
    assert architecture["probabilistic_sampler"] is False
    try:
        request("field-policy-invalid", temperature=0.1)
    except urllib.error.HTTPError as error:
        if error.code != 400:
            raise
    else:
        raise AssertionError("provider accepted probabilistic sampling")
    print(json.dumps({"receipt": result["cassi"]["displacement_receipt_sha256"], "field_owned": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
