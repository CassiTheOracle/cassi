"""Temporary loopback OpenAI-compatible provider for the native llama server.

This is a transport seam only: it forwards the native server's health, model,
metrics, and chat-completion surfaces without changing request or response
payloads. It is intentionally loopback-only and is not a second model runtime.
"""

from __future__ import annotations

import argparse
import json

import http.server
import socketserver
import sys
import urllib.error
import urllib.parse
import urllib.request


_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


class ProviderHandler(http.server.BaseHTTPRequestHandler):
    upstream: str
    timeout: float

    def log_message(self, format: str, *args: object) -> None:
        print(f"[native-omp] {format % args}", flush=True)

    def _forward(self) -> None:
        payload = None
        if self.command in {"POST", "PUT", "PATCH"}:
            length = int(self.headers.get("Content-Length", "0"))
            payload = self.rfile.read(length)
        url = f"{self.upstream}{self.path}"
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in _HOP_BY_HOP and key.lower() != "host"
        }
        request = urllib.request.Request(url, data=payload, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                self.send_response(response.status)
                for key, value in response.headers.items():
                    if key.lower() in _HOP_BY_HOP or key.lower() == "content-length":
                        continue
                    self.send_header(key, value)
                self.send_header("Connection", "close")
                self.end_headers()
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except urllib.error.HTTPError as error:
            body = error.read()
            self.send_response(error.code)
            self.send_header("Content-Type", error.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
        except (OSError, urllib.error.URLError) as error:
            body = (json.dumps({
                "error": {
                    "type": "native_omp_upstream_error",
                    "message": str(error),
                },
            }) + "\n").encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

    def do_GET(self) -> None:
        self._forward()

    def do_POST(self) -> None:
        self._forward()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", default="http://127.0.0.1:8080")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    parsed = urllib.parse.urlparse(args.upstream.rstrip("/"))
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("temporary native OMP provider requires an HTTP loopback upstream")
    if not (1 <= args.port <= 65535):
        raise ValueError("provider port must be in [1, 65535]")
    if args.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("temporary native OMP provider must bind to loopback")
    handler = type("NativeOMPHandler", (ProviderHandler,), {"upstream": args.upstream.rstrip("/"), "timeout": args.timeout})
    with socketserver.ThreadingTCPServer((args.host, args.port), handler) as server:
        server.daemon_threads = True
        print(f"native OMP provider listening on http://{args.host}:{args.port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            return 0
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"native OMP provider failed: {error}", file=sys.stderr)
        raise
