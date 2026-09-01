"""Field-only provider policy and fail-closed ownership checks."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


URL = os.environ.get("CASSI_PROVIDER_URL", "http://127.0.0.1:8086/v1/chat/completions")


def request(session: str, **extra: object) -> dict:
    body: dict[str, object] = {
        "model": "cassi-phi-harmonic-language-v1",
        "messages": [{"role": "user", "content": "gi High School culture fest"}],
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
    cassi = result["cassi"]
    receipt = cassi["field_text_receipt"]
    assert receipt["schema"] == "cassi.qi-phi-harmonic-text-receipt.v1"
    assert cassi["reply_kind"] == "field"
    assert cassi["trained_tape_preserved"] is True
    assert len(cassi["provider_fingerprint"]) == 64
    assert len(cassi["engine_fingerprint"]) == 64
    assert "displacement_receipt" not in cassi
    try:
        request("field-policy-invalid", temperature=0.1)
    except urllib.error.HTTPError as error:
        if error.code != 400:
            raise
    else:
        raise AssertionError("provider accepted probabilistic sampling")
    print(json.dumps({"receipt": result["cassi"]["field_text_receipt_sha256"], "field_owned": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
