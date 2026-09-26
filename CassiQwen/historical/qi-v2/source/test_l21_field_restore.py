"""Provider session-checkpoint restore smoke check.

Run this against a live native-Qi provider.  The provider owns exactly one
canonical Qi state per session; no organism, decoder, or learned-head snapshot
exists.
"""

from __future__ import annotations

import json
import os
import urllib.request


URL = os.environ.get("CASSI_PROVIDER_URL", "http://127.0.0.1:8086/v1/chat/completions")
MODEL = "cassi-qi-language-v1"


def request(session: str) -> dict:
    body = {"model": MODEL, "messages": [{"role": "user", "content": "checkpoint restore probe"}], "max_tokens": 1, "user": session}
    value = urllib.request.Request(URL, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(value, timeout=300) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    first = request("field-restore-session")
    if not first["cassi"].get("checkpoint"):
        raise AssertionError("provider response lacks canonical session checkpoint")
    restored = request("field-restore-session")
    if restored["cassi"]["state_in_sha256"] != first["cassi"]["state_out_sha256"]:
        raise AssertionError("session did not restore the prior field successor")
    if restored["cassi"].get("displacement_receipt", {}).get("schema") != "cassi.qi-native-displacement.v1":
        raise AssertionError("restored request lacks native-Qi displacement receipt")
    if restored["cassi"].get("field_text_receipt", {}).get("schema") != "cassi.qi-text-result.v1":
        raise AssertionError("restored request lacks native-Qi text receipt")
    print("native-Qi checkpoint restore PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
