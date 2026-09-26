"""Provider session-checkpoint restore smoke check.

Run this against the live seven-pool Phi provider. The provider owns exactly
one adaptive field tensor per session.
"""

from __future__ import annotations

import json
import os
import urllib.request


URL = os.environ.get("CASSI_PROVIDER_URL", "http://127.0.0.1:8086/v1/chat/completions")
MODEL = "cassi-phi-harmonic-language-v1"


def request(session: str) -> dict:
    body = {"model": MODEL, "messages": [{"role": "user", "content": "gi High School culture fest"}], "max_tokens": 1, "user": session}
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
    receipt = restored["cassi"].get("field_text_receipt", {})
    if receipt.get("schema") != "cassi.qi-phi-harmonic-text-receipt.v1":
        raise AssertionError("restored request lacks Phi field text receipt")
    if restored["cassi"].get("trained_tape_preserved") is not True:
        raise AssertionError("restored request changed the learned Phi tape")
    print("Phi checkpoint restore PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
