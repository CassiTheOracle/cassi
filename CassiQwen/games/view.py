"""The watch surface: one page that shows a world being played.

The page is deliberately dumb.  It shows the world's own screen, the numbers the
world reports, and the decisions the player made with their reasons.  Nothing
here knows anything about NetHack or about any other game: give it a screen and
a panel and it will show them.
"""
from __future__ import annotations

import html
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping, Sequence

DEFAULT_PORT = 8099
POLL_MS = 600

_MONSTERS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
_WALLS = set("|-│─┌┐└┘├┤┬┴┼╔╗╚╝║═╠╣╦╩╬")
_ITEMS = {
    "$": "gold",
    "?": "scroll",
    "!": "potion",
    ")": "weapon",
    "[": "armor",
    "%": "food",
    "/": "wand",
    "=": "ring",
    '"': "amulet",
    "(": "tool",
    "*": "gem",
    "+": "book",
}


def _class_of(character: str) -> str:
    if character == "@":
        return "me"
    if character in "><":
        return "stairs"
    if character in _WALLS:
        return "wall"
    if character in _ITEMS:
        return f"item {_ITEMS[character]}"
    if character in ".#":
        return "floor"
    if character in _MONSTERS:
        return "monster"
    return "plain"


def render_screen(lines: Sequence[str], prose_rows: Sequence[int] = ()) -> str:
    """Render a world screen as HTML, colouring glyph runs.

    `prose_rows` are the game's message and status lines: they are words, not
    map, so they keep their own colour instead of being read as monsters.
    """
    prose = set(prose_rows)
    rows = []
    for index, line in enumerate(lines):
        if index in prose:
            rows.append(f'<div class="row">{html.escape(line) or "&nbsp;"}</div>')
            continue
        pieces: list[str] = []
        run: list[str] = []
        current = None
        for character in line:
            kind = _class_of(character)
            if kind != current:
                if run:
                    pieces.append(
                        f'<span class="{current}">{html.escape("".join(run))}</span>'
                    )
                run = [character]
                current = kind
            else:
                run.append(character)
        if run:
            pieces.append(f'<span class="{current}">{html.escape("".join(run))}</span>')
        row_class = "row status" if index >= len(lines) - 2 else "row"
        rows.append(f'<div class="{row_class}">{"".join(pieces) or "&nbsp;"}</div>')
    return "".join(rows)


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: #0b0d12; color: #d7dbe0;
    font-family: "Segoe UI", system-ui, sans-serif; font-size: 14px;
  }}
  header {{
    display: flex; align-items: baseline; gap: 14px;
    padding: 10px 18px; border-bottom: 1px solid #1d2430; background: #0e1118;
  }}
  header h1 {{ font-size: 15px; font-weight: 600; margin: 0; letter-spacing: .01em; }}
  #status {{ font-size: 12px; color: #7d8899; }}
  main {{ display: flex; gap: 18px; padding: 18px; align-items: flex-start; }}
  .terminal {{
    background: #05070a; border: 1px solid #223047; border-radius: 8px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, .45); overflow: hidden; flex: 0 0 auto;
  }}
  .bar {{
    display: flex; align-items: center; gap: 8px; padding: 7px 10px;
    background: #111725; border-bottom: 1px solid #223047;
    font-size: 12px; color: #8b98ab;
  }}
  .bar .dot {{ width: 9px; height: 9px; border-radius: 50%; background: #2b3a52; }}
  .bar .dot.live {{ background: #52d1a4; }}
  #screen {{
    font-family: "Cascadia Mono", "Consolas", monospace; font-size: 16px;
    line-height: 1.2; padding: 10px 14px; white-space: pre; letter-spacing: 0;
    width: max-content;
  }}
  .row {{ height: 1.2em; }}
  .row.status {{ color: #c8d4e4; font-weight: 600; }}
  .plain {{ color: #cdd3da; }} .floor {{ color: #6b7686; }} .wall {{ color: #5a6a90; }}
  .me {{ color: #ffe066; font-weight: 700; }} .monster {{ color: #ff8a80; }}
  .stairs {{ color: #8ee6ff; font-weight: 700; }}
  .gold {{ color: #ffd54f; }} .scroll {{ color: #e6e6e6; }} .potion {{ color: #ff7bd5; }}
  .weapon {{ color: #b0bec5; }} .armor {{ color: #90caf9; }} .food {{ color: #a5d6a7; }}
  .wand {{ color: #ce93d8; }} .ring {{ color: #ffcc80; }} .amulet {{ color: #fff59d; }}
  .tool {{ color: #bcaaa4; }} .gem {{ color: #80deea; }} .book {{ color: #f48fb1; }}
  aside {{ flex: 1 1 320px; min-width: 300px; display: flex; flex-direction: column; gap: 12px; }}
  .card {{ background: #0e1118; border: 1px solid #1d2430; border-radius: 6px; padding: 10px 12px; }}
  .card h2 {{ margin: 0 0 8px; font-size: 11px; text-transform: uppercase;
              letter-spacing: .09em; color: #7d8899; font-weight: 600; }}
  .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px 10px; }}
  .stat {{ font-variant-numeric: tabular-nums; }}
  .stat b {{ display: block; font-size: 16px; font-weight: 600; color: #e8edf3; }}
  .stat span {{ font-size: 11px; color: #7d8899; }}
  #message {{ font-family: "Cascadia Mono", Consolas, monospace; color: #ffd479;
              min-height: 1.3em; }}
  .decision {{ font-size: 13px; }}
  .decision .key {{ color: #8ee6ff; font-weight: 600; }}
  .decision .reason {{ color: #c6ced9; }}
  .decision .source {{ color: #7d8899; font-size: 11px; }}
  ol#journal {{ margin: 0; padding-left: 18px; max-height: 34vh; overflow-y: auto; }}
  ol#journal li {{ margin-bottom: 4px; color: #aab4c0; font-size: 12px; }}
  ol#journal li b {{ color: #8ee6ff; font-weight: 600; }}
  .done {{ color: #ff8a80; }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <div id="status"></div>
</header>
<main>
  <div class="terminal">
    <div class="bar"><span class="dot live"></span><span id="bar-title">NetHack 5.0</span></div>
    <div id="screen"></div>
  </div>
  <aside>
    <div class="card"><h2>Message</h2><div id="message"></div></div>
    <div class="card"><h2>State</h2><div class="stats" id="stats"></div></div>
    <div class="card"><h2>Last decision</h2><div class="decision" id="decision"></div></div>
    <div class="card"><h2>Journal</h2><ol id="journal"></ol></div>
  </aside>
</main>
<script>
const POLL = {poll};
async function tick() {{
  try {{
    const response = await fetch("state", {{cache: "no-store"}});
    const data = await response.json();
    document.getElementById("screen").innerHTML = data.screen_html;
    document.getElementById("bar-title").textContent = data.title || "";
    document.getElementById("status").textContent = data.status;
    document.getElementById("message").textContent = data.message || "";
    const stats = document.getElementById("stats");
    stats.innerHTML = Object.entries(data.stats || {{}}).map(
      ([k, v]) => `<div class="stat"><b>${{v}}</b><span>${{k}}</span></div>`
    ).join("");
    const decision = data.decision || {{}};
    document.getElementById("decision").innerHTML =
      `<span class="key">${{decision.label || "—"}}</span> ` +
      `<span class="reason">${{decision.reason || ""}}</span><br>` +
      `<span class="source">${{decision.source || ""}}</span>`;
    document.getElementById("journal").innerHTML = (data.journal || []).map(
      row => `<li><b>${{row.turn}}.</b> ${{row.label}} — ${{row.reason}}</li>`
    ).join("");
  }} catch (error) {{
    document.getElementById("status").textContent = "waiting for the runner…";
  }}
}}
tick();
setInterval(tick, POLL);
</script>
</body>
</html>
"""


class _SingleWatchServer(ThreadingHTTPServer):
    """A watch server that refuses to share its port.

    `HTTPServer` sets `allow_reuse_address`, which on Windows lets a second
    run bind the same port and leave two listeners answering one address; the
    page then shows whichever run bound first. Refusing the port makes a
    colliding run fail where the operator can see it.
    """

    allow_reuse_address = False


class WatchView:
    """A local page showing one world: screen, state, decisions."""

    def __init__(
        self,
        *,
        title: str = "Cassi plays NetHack",
        port: int = DEFAULT_PORT,
        host: str = "127.0.0.1",
    ) -> None:
        self.title = title
        self.port = int(port)
        self.host = host
        self._lock = threading.RLock()
        self._payload: dict[str, Any] = {
            "screen_html": "",
            "status": "starting",
            "message": "",
            "stats": {},
            "decision": {},
            "journal": [],
        }
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # -- publishing ------------------------------------------------------
    def publish(
        self,
        *,
        screen: Sequence[str],
        stats: Mapping[str, Any],
        message: str,
        status: str,
        decision: Mapping[str, Any],
        journal: Sequence[Mapping[str, Any]],
        title: str = "",
        prose_rows: Sequence[int] = (),
    ) -> None:
        with self._lock:
            self._payload = {
                "screen_html": render_screen(screen, prose_rows),
                "status": status,
                "message": message,
                "stats": dict(stats),
                "decision": dict(decision),
                "journal": [dict(row) for row in journal],
                "title": title or self.title,
            }

    def snapshot(self) -> Mapping[str, Any]:
        with self._lock:
            return dict(self._payload)

    # -- serving ---------------------------------------------------------
    def start(self) -> str:
        view = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:  # silence the access log
                return

            def do_GET(self) -> None:  # noqa: N802 - http.server API
                path = self.path.split("?", 1)[0]
                if path in {"/", "/index.html"}:
                    body = _PAGE.format(title=html.escape(view.title), poll=POLL_MS)
                    content_type = "text/html; charset=utf-8"
                elif path == "/state":
                    body = json.dumps(view.snapshot())
                    content_type = "application/json"
                else:
                    self.send_error(404)
                    return
                encoded = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(encoded)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(encoded)

        try:
            self._server = _SingleWatchServer((self.host, self.port), Handler)
        except OSError as failure:
            raise RuntimeError(
                f"the watch port {self.port} is already held, likely by another run still "
                f"holding its last screen; stop it or choose another --port ({failure})"
            ) from failure
        self._server.daemon_threads = True
        self.port = int(self._server.server_address[1])
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="cassi-watch",
            daemon=True,
        )
        self._thread.start()
        return f"http://{self.host}:{self.port}/"

    def stop(self) -> None:
        server, self._server = self._server, None
        if server is not None:
            server.shutdown()
            server.server_close()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=3.0)
