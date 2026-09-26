"""Seven-pool Phi loopback health, model-list, SSE, and receipt checks."""

from __future__ import annotations

import json
import os
import urllib.request


ROOT = os.environ.get("CASSI_PROVIDER_ROOT", "http://127.0.0.1:8086")
MODEL = "cassi-phi-harmonic-language-v1"


def get(path: str) -> dict:
    with urllib.request.urlopen(ROOT + path, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    health = get("/health")
    assert health["ok"] is True and health["field"] is True
    models = get("/v1/models")
    assert models["data"][0]["id"] == MODEL
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "gi High School culture fest"}],
        "max_tokens": 2,
        "user": "field-openai-surface",
        "stream": True,
    }
    request = urllib.request.Request(ROOT + "/v1/chat/completions", data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read().decode("utf-8")
    assert "chat.completion.chunk" in raw and "cassi.qi-phi-harmonic-text-receipt.v1" in raw and "data: [DONE]" in raw
    print("Phi OpenAI surface PASS")


if __name__ == "__main__":
    main()
