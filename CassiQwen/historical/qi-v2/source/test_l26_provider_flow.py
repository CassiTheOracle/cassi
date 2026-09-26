"""Verify direct Qi-state continuation through the field-only HTTP seam."""

from __future__ import annotations

import json
import os
import urllib.request


URL = os.environ.get("CASSI_PROVIDER_URL", "http://127.0.0.1:8086/v1/chat/completions")
BODY = {"model": "cassi-qi-language-v1", "messages": [{"role": "user", "content": "active field probe"}], "max_tokens": 1, "user": "field-active-session"}


def request() -> dict:
    value = urllib.request.Request(URL, data=json.dumps(BODY).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(value, timeout=300) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    first = request()
    second = request()
    first_cassi, second_cassi = first["cassi"], second["cassi"]
    assert first_cassi["displacement_receipt"]["architecture"]["learned_parameter_count"] == 0
    assert second_cassi["state_in_sha256"] == first_cassi["state_out_sha256"]
    assert first_cassi["displacement_receipt"]["field_text"]["committed_output_count"] >= 1
    assert second_cassi["displacement_receipt"]["field_text"]["all_outputs_field_owned"] is True
    print(json.dumps({"first_state": first_cassi["state_out_sha256"], "second_state": second_cassi["state_out_sha256"], "field_only": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
