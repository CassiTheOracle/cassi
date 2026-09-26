"""One-request probe used on each side of a field-provider restart."""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8086/v1/chat/completions")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--session", default="field-restart-lineage")
    args = parser.parse_args()
    body = {"model": "cassi-qi-language-v1", "messages": [{"role": "user", "content": "restart lineage probe"}], "max_tokens": 1, "user": args.session}
    request = urllib.request.Request(args.url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=300) as response:
        value = json.loads(response.read().decode("utf-8"))
    cassi = value["cassi"]
    displacement = cassi.get("displacement_receipt", {})
    if not cassi.get("state_out_sha256") or displacement.get("schema") != "cassi.qi-native-displacement.v1":
        raise AssertionError("restart probe lacks native-Qi state or displacement receipt")
    args.output.write_text(json.dumps({"state_in_sha256": cassi["state_in_sha256"], "state_out_sha256": cassi["state_out_sha256"], "receipt_sha256": cassi["displacement_receipt_sha256"], "request_id": cassi["request_id"]}, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"state_out_sha256": cassi["state_out_sha256"], "receipt_sha256": cassi["displacement_receipt_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
