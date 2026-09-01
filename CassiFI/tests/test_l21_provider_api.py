"""Seven-pool Phi provider continuation and ownership smoke check."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
if str(_CASSI_FI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSI_FI_ROOT))
from cassi_fi_paths import ARTIFACT_DIR

URL = os.environ.get("CASSI_PROVIDER_URL", "http://127.0.0.1:8086/v1/chat/completions")
STATE = Path(os.environ.get("CASSI_PROVIDER_STATE", str(ARTIFACT_DIR / "cassi-phi-harmonic-language" / "provider-sessions")))
MODEL = "cassi-phi-harmonic-language-v1"


def request() -> dict:
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "gi High School culture fest"}],
        "max_tokens": 2,
        "user": "field-checkpoint-session",
    }
    value = urllib.request.Request(URL, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(value, timeout=300) as response:
        result = json.loads(response.read().decode("utf-8"))
    cassi = result.get("cassi", {})
    receipt = cassi.get("field_text_receipt", {})
    if not result.get("choices") or not cassi.get("field_text_receipt_sha256"):
        raise AssertionError("provider response lacks Phi text receipt")
    if receipt.get("schema") != "cassi.qi-phi-harmonic-text-receipt.v1":
        raise AssertionError("provider response has the wrong Phi receipt")
    if cassi.get("reply_kind") != "field":
        raise AssertionError("provider output is not field-owned")
    if cassi.get("trained_tape_preserved") is not True:
        raise AssertionError("provider changed the learned Phi tape")
    if "displacement_receipt" in cassi:
        raise AssertionError("legacy Qwen displacement receipt is still live")
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
