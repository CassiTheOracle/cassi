"""Screen worlds: games whose interface is a screen and a keyboard.

`ScreenWorld` carries everything a text-mode game shares — spawn, handshake,
settle, type, diff the message line, keep the history — and leaves four small
hooks for the game itself: what to run, how to get past the title screens, how
to read the screen, and what the player may do.  A second terminal game is
those four hooks.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4

from games.surface import SurfaceTerminalBackend, SurfaceTerminalError
from games.terminal import ScreenFrame, TerminalError, TerminalSession
from games.world import Action, Observation, StepResult, WorldError

HISTORY_LIMIT = 240
# The conventional screen-game movement keys, as (row, column) steps.
MOVE_DELTAS: Mapping[str, tuple[int, int]] = {
    "k": (-1, 0),
    "j": (1, 0),
    "h": (0, -1),
    "l": (0, 1),
    "y": (-1, -1),
    "u": (-1, 1),
    "b": (1, -1),
    "n": (1, 1),
}

class _SurfaceGrantWait(SurfaceTerminalError):
    """A bounded grant expired or was revoked; only the host may resume it."""



class ScreenWorld:
    """A `GameWorld` over one terminal session."""

    name = "screen"
    goal = ""
    # Rows that are the game's own prose (its message line, its status lines)
    # rather than part of the map.  A watch surface colours the map by glyph and
    # leaves these as text; a game says which rows those are.
    PROSE_ROWS: tuple[int, ...] = (0,)
    # The map area, when a game draws one inside the screen.  A game that has no
    # separate map (the whole screen is the world) leaves these at zero and gets
    # the screen's own size.
    map_top = 0
    map_rows = 0
    map_cols = 0

    def __init__(
        self,
        *,
        cols: int = 80,
        rows: int = 24,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        quiet: float = 0.35,
        idle: float = 3.0,
    ) -> None:
        self.cols = int(cols)
        self.rows = int(rows)
        if not self.map_rows:
            self.map_rows = self.rows
        if not self.map_cols:
            self.map_cols = self.cols
        self.cwd = cwd
        self.env = dict(env) if env else None
        self.quiet = float(quiet)
        self.idle = float(idle)
        self.session: TerminalSession | None = None
        self.turn = 0
        self.score = 0.0
        self.done = False
        self.messages: deque[str] = deque(maxlen=40)
        self.history: deque[Mapping[str, Any]] = deque(maxlen=HISTORY_LIMIT)
        self.position: tuple[int, int] | None = None
        self.last_note = ""
        self._last_message = ""
        self._position: tuple[int, int] | None = None
        self._started_at = 0.0

        # Host injection is explicit: standalone worlds keep their original
        # ConPTY path unless a live SurfaceBroker is supplied by the host.
        self._surface_broker: Any | None = None
        self._surface_mission_id = ""
        self._surface_grant_source: str | Callable[[Mapping[str, Any]], str | Mapping[str, Any]] | None = None
        self._surface_max_updates = 4096
        self._surface_backend: SurfaceTerminalBackend | None = None
        self._surface_backend_registered = False
        self._surface_binding: dict[str, Any] | None = None
        self._surface_last_binding: dict[str, Any] | None = None
        self._surface_grant_id: str | None = None
        self._surface_grant: dict[str, Any] = {}
        self._surface_grant_generation = 0
        self._surface_grant_max_updates = 4096
        self._surface_control_sequence = 0
        self._surface_heartbeat_sequence = 0
        self._surface_heartbeat_timeout_ns = 30_000_000_000

        self._surface_heartbeat_stop = threading.Event()
        self._surface_heartbeat_thread: threading.Thread | None = None
        self._surface_control_lock = threading.RLock()
        self._surface_control_error: Exception | None = None
        self._surface_wait_kind = ""
        self._surface_wait_reason = ""
        self._surface_cleanup: dict[str, Any] = {}
        self._surface_publication: dict[str, Any] | None = None
        self._surface_fenced = False
        self._surface_effects: list[dict[str, Any]] = []

    def configure_surface(
        self,
        broker: Any,
        mission_id: str,
        grant_id: str | Callable[[Mapping[str, Any]], str | Mapping[str, Any]] | None = None,
        *,
        surface_backend: SurfaceTerminalBackend | None = None,
        max_updates: int = 4096,
    ) -> None:
        """Attach the host entity's live broker before starting this world.

        A supplied backend is already registered by the host and is reused
        without registration here.  With no supplied grant identifier, the
        broker's configured host authorizer is asked for a fresh, bounded runner
        grant after each source binding.  A callable may provide an already-
        issued grant for that exact binding; a literal grant is consumed once.
        """
        if self.session is not None or self._surface_binding is not None:
            raise WorldError("Surface must be configured before the terminal session starts")
        if not isinstance(mission_id, str) or not mission_id or len(mission_id) > 192 or "\x00" in mission_id:
            raise WorldError("Surface mission_id must be bounded nonempty text")
        required = (
            "register_backend",
            "bind",
            "capture",
            "grant",
            "submit_intent",
            "heartbeat",
            "inspect_binding",
            "revoke",
        )
        if broker is None or any(not callable(getattr(broker, name, None)) for name in required):
            raise WorldError("Surface mode requires an injected live SurfaceBroker")
        if grant_id is not None and not isinstance(grant_id, str) and not callable(grant_id):
            raise WorldError("Surface grant_id must be text, a binding grant provider, or None")
        if isinstance(grant_id, str) and (not grant_id or len(grant_id) > 192 or "\x00" in grant_id):
            raise WorldError("Surface grant_id must be bounded nonempty text")
        if isinstance(max_updates, bool) or not isinstance(max_updates, int) or not 1 <= max_updates <= 4096:
            raise WorldError("Surface control updates must be bounded to 1..4096")
        if surface_backend is not None:
            if not isinstance(surface_backend, SurfaceTerminalBackend):
                raise WorldError("hosted Surface backend must be a SurfaceTerminalBackend")
            if (
                surface_backend._cols != self.cols
                or surface_backend._rows != self.rows
                or not surface_backend.source_id.startswith(
                    f"games.{self.name}.terminal."
                )
            ):
                raise WorldError("hosted Surface backend does not match this game's terminal")
            if (
                self._surface_backend is not None
                and self._surface_backend is not surface_backend
            ):
                raise WorldError("game world is already bound to a different Surface backend")
            self._surface_backend = surface_backend
            self._surface_backend_registered = True
        self._surface_broker = broker
        self._surface_mission_id = mission_id
        self._surface_grant_source = grant_id
        self._surface_max_updates = max_updates

    def surface_receipt(self) -> Mapping[str, Any]:
        """Return non-secret source and ledger evidence for the life receipt."""
        binding = self._surface_last_binding or self._surface_binding
        published = self._surface_publication or {}
        public_fields = (
            "binding_id",
            "source_id",
            "source_instance",
            "source_epoch",
            "environment_incarnation",
            "geometry_revision",
            "sequence",
            "generation",
            "width",
            "height",
            "pixel_format",
            "structure_byte_length",
            "structure_sha256",
            "structure_codec",
            "update_kind",
            "sample_time_ns",
            "sample_clock_domain",
            "receipt_time_ns",
            "receipt_clock_domain",
        )
        return {
            "enabled": self._surface_broker is not None,
            "binding": {
                key: binding[key]
                for key in (
                    "binding_id",
                    "backend_id",
                    "source_id",
                    "source_instance",
                    "source_epoch",
                    "environment_incarnation",
                    "geometry_revision",
                    "operations",
                )
                if binding is not None and key in binding
            },
            "latest_publication": {
                key: published[key] for key in public_fields if key in published
            },
            "control": {
                "grant_generation": self._surface_grant_generation,
                "intent_sequence": self._surface_control_sequence,
                "heartbeat_sequence": self._surface_heartbeat_sequence,
                "grant_max_updates": self._surface_grant_max_updates,
            },
            "effects": list(self._surface_effects),
            "cleanup": dict(self._surface_cleanup),
            "wait": {
                "kind": self._surface_wait_kind,
                "reason": self._surface_wait_reason,
            } if self._surface_wait_kind else None,
            "fenced": self._surface_fenced,
        }

    def _bind_surface_session(self, session: TerminalSession) -> None:
        broker = self._surface_broker
        if broker is None:
            return
        previous = self._surface_last_binding
        if previous is not None:
            inspected = broker.inspect_binding(str(previous["binding_id"]))
            if (
                not isinstance(inspected, Mapping)
                or inspected.get("human_control") is not False
                or inspected.get("inhibited") is not False
                or inspected.get("state")
                not in {"bound", "lease-expired", "revoked", "observation-only"}
            ):
                raise SurfaceTerminalError(
                    "previous ConPTY binding is not available for a new game session"
                )
        if self._surface_backend is None:
            self._surface_backend = SurfaceTerminalBackend(
                self.name, cols=self.cols, rows=self.rows
            )
        backend = self._surface_backend
        token = session.enable_surface_transport(
            self._dispatch_surface_input,
            lambda: self._surface_terminal_closing(session),
        )
        backend.attach(session, token)
        if not self._surface_backend_registered:
            broker.register_backend(backend)
            self._surface_backend_registered = True
        binding = broker.bind(backend.backend_id, backend.source_id)
        if not isinstance(binding, Mapping):
            raise SurfaceTerminalError("Surface broker returned an invalid terminal binding")
        self._surface_binding = dict(binding)
        self._surface_last_binding = dict(binding)
        if "keyboard.text" not in binding.get("operations", ()):
            raise SurfaceTerminalError("bound ConPTY source does not support keyboard.text")
        self._surface_publication = None
        self._surface_cleanup = {}

        self._surface_fenced = False
        self._surface_grant_id = None
        self._surface_grant = {}

        self._surface_control_error = None
        self._surface_issue_grant()

    def _surface_issue_grant(self) -> None:
        broker = self._surface_broker
        binding = self._surface_binding
        if broker is None or binding is None:
            raise SurfaceTerminalError("Surface source is not bound")
        source = self._surface_grant_source
        if callable(source):
            supplied = source(dict(binding))
        elif isinstance(source, str):
            supplied = source
            self._surface_grant_source = None
        else:
            now = time.monotonic_ns()
            supplied = broker.grant(
                self._surface_mission_id,
                str(binding["binding_id"]),
                ("keyboard.text",),
                now + 3_600_000_000_000,
                {
                    "max_duration_ns": 300_000_000_000,
                    "heartbeat_timeout_ns": 30_000_000_000,
                    "max_updates": self._surface_max_updates,
                    "max_payload_bytes": 2048,
                    "runner": "CassiQwen.run_cassi_game",
                    "world": self.name,
                    "source_id": binding["source_id"],
                },
            )
        if isinstance(supplied, Mapping):
            grant = dict(supplied)
            grant_id = grant.get("grant_id")
            if (
                grant.get("mission_id") != self._surface_mission_id
                or grant.get("binding_id") != binding["binding_id"]
                or grant.get("focus_epoch") != binding.get("focus_epoch")
            ):
                raise SurfaceTerminalError("Surface grant does not match this game binding")
            operations = grant.get("operations")
            if not isinstance(operations, (list, tuple)) or tuple(operations) != ("keyboard.text",):
                raise SurfaceTerminalError("Surface grant must authorize only keyboard.text")
            expires_ns = grant.get("expires_ns")
            duration_ns = grant.get("max_duration_ns")
            if (
                not isinstance(expires_ns, int)
                or isinstance(expires_ns, bool)
                or expires_ns <= time.monotonic_ns()
                or not isinstance(duration_ns, int)
                or isinstance(duration_ns, bool)
                or not 1 <= duration_ns <= 300_000_000_000
            ):
                raise SurfaceTerminalError("Surface grant is expired or has an invalid duration")
        else:
            grant = {}
            grant_id = supplied
        if not isinstance(grant_id, str) or not grant_id or len(grant_id) > 192:
            raise SurfaceTerminalError("Surface host did not issue a valid keyboard grant")
        self._surface_grant = grant
        self._surface_grant_id = grant_id
        self._surface_control_sequence = 0
        self._surface_heartbeat_sequence = 0
        heartbeat_timeout_ns = grant.get("heartbeat_timeout_ns", 3_000_000_000)
        max_updates = grant.get("max_updates", self._surface_max_updates)
        if (
            isinstance(max_updates, bool)
            or not isinstance(max_updates, int)
            or not 1 <= max_updates <= self._surface_max_updates
            or isinstance(heartbeat_timeout_ns, bool)
            or not isinstance(heartbeat_timeout_ns, int)
            or not 100_000_000 <= heartbeat_timeout_ns <= 30_000_000_000
        ):
            raise SurfaceTerminalError("Surface grant has invalid control limits")
        self._surface_grant_max_updates = max_updates
        self._surface_heartbeat_timeout_ns = heartbeat_timeout_ns
        self._surface_grant_generation += 1
        self._surface_fenced = False
        self._surface_control_error = None
        self._surface_wait_reason = ""
        self._surface_wait_kind = ""
        self._surface_heartbeat_stop.clear()
        self._surface_heartbeat_thread = threading.Thread(
            target=self._surface_heartbeat_loop,
            name="cassi-surface-game-lease",
            daemon=True,
        )
        self._surface_heartbeat_thread.start()

    def _set_surface_wait(self, kind: str, reason: str, error: Exception | None = None) -> None:
        self._surface_wait_kind = kind
        self._surface_wait_reason = reason
        self._surface_control_error = error
        self._surface_fenced = True
        self._surface_heartbeat_stop.set()

    def resume_with_grant(self, grant: Mapping[str, Any]) -> None:
        """Resume a fenced game only with a fresh grant issued by its host."""
        if not isinstance(grant, Mapping):
            raise WorldError("Surface resume requires a host-issued grant object")
        if self._surface_wait_kind != "grant" or not self._surface_fenced:
            raise WorldError("Surface world is not waiting for a host-issued grant")
        self._stop_surface_heartbeat()
        with self._surface_control_lock:
            broker = self._surface_broker
            binding = self._surface_binding
            if broker is None or binding is None or self.session is None:
                raise SurfaceTerminalError("Surface game session is no longer bound")
            binding_id = str(binding.get("binding_id") or "")
            inspected = broker.inspect_binding(binding_id)
            identity_fields = (
                "binding_id",
                "source_id",
                "source_instance",
                "source_epoch",
                "environment_incarnation",
                "geometry_revision",
                "focus_epoch",
                "input_domain_epoch",
            )
            if (
                not isinstance(inspected, Mapping)
                or any(inspected.get(key) != binding.get(key) for key in identity_fields)
                or "keyboard.text" not in binding.get("operations", ())
                or "keyboard.text" not in inspected.get("operations", ())
            ):
                raise SurfaceTerminalError(
                    "Surface source identity, epoch, or keyboard capability changed; host must bind it again"
                )
            if (
                inspected.get("human_control") is not False
                or inspected.get("inhibited") is not False
                or inspected.get("state")
                not in {"bound", "lease-expired", "revoked", "observation-only"}
            ):
                raise SurfaceTerminalError(
                    "Surface resume is refused while the source is under human control or inhibited"
                )
            for key, expected in (
                ("mission_id", self._surface_mission_id),
                ("binding_id", binding_id),
            ):
                if grant.get(key) != expected:
                    raise SurfaceTerminalError(f"Surface resume grant {key} does not match")
            grant_id = grant.get("grant_id")
            operations = grant.get("operations")
            expires_ns = grant.get("expires_ns")
            duration_ns = grant.get("max_duration_ns")
            heartbeat_ns = grant.get("heartbeat_timeout_ns", 3_000_000_000)
            updates = grant.get("max_updates", self._surface_max_updates)
            if (
                not isinstance(grant_id, str)
                or not grant_id
                or len(grant_id) > 192
                or not isinstance(operations, (list, tuple))
                or set(operations) != {"keyboard.text"}
                or not isinstance(expires_ns, int)
                or isinstance(expires_ns, bool)
                or expires_ns <= time.monotonic_ns()
                or not isinstance(duration_ns, int)
                or isinstance(duration_ns, bool)
                or not 1 <= duration_ns <= 300_000_000_000
                or not isinstance(heartbeat_ns, int)
                or isinstance(heartbeat_ns, bool)
                or not 100_000_000 <= heartbeat_ns <= 30_000_000_000
                or not isinstance(updates, int)
                or isinstance(updates, bool)
                or not 1 <= updates <= self._surface_max_updates
                or grant.get("focus_epoch") != inspected.get("focus_epoch")
            ):
                raise SurfaceTerminalError(
                    "Surface host grant is expired, out of scope, or does not match the current focus epoch"
                )
            self._surface_grant = dict(grant)
            self._surface_grant_id = grant_id
            self._surface_control_sequence = 0
            self._surface_heartbeat_sequence = 0
            self._surface_grant_max_updates = updates
            self._surface_heartbeat_timeout_ns = heartbeat_ns
            self._surface_grant_generation += 1
            self._surface_control_error = None
            self._surface_wait_reason = ""
            self._surface_wait_kind = ""
            self._surface_fenced = False
            self.done = False
            self._surface_heartbeat_stop.clear()
            self._surface_heartbeat_thread = threading.Thread(
                target=self._surface_heartbeat_loop,
                name="cassi-surface-game-lease",
                daemon=True,
            )
            self._surface_heartbeat_thread.start()

    def _surface_heartbeat_loop(self) -> None:
        while not self._surface_heartbeat_stop.is_set():
            interval = min(
                10.0,
                max(0.05, self._surface_heartbeat_timeout_ns / 3_000_000_000),
            )
            if self._surface_heartbeat_stop.wait(interval):
                return
            try:
                self._renew_surface_lease()
            except Exception as exc:
                with self._surface_control_lock:
                    if not self._surface_heartbeat_stop.is_set():
                        self._set_surface_wait(
                            "grant",
                            "Surface control lease expired or was revoked; wait for the host to inspect "
                            "human-control state and source epoch, then issue a fresh grant.",
                            exc,
                        )

    def _renew_surface_lease(self) -> None:
        with self._surface_control_lock:
            broker = self._surface_broker
            binding = self._surface_binding
            grant_id = self._surface_grant_id
            if broker is None or binding is None or grant_id is None:
                raise SurfaceTerminalError("Surface runner control is no longer bound")
            if self._surface_fenced:
                if self._surface_wait_reason:
                    raise _SurfaceGrantWait(self._surface_wait_reason)
                raise SurfaceTerminalError("Surface runner control is fenced")
            if self._surface_control_error is not None:
                raise _SurfaceGrantWait(self._surface_wait_reason or
                                        "Surface runner grant is unavailable; host reauthorization is required")
            sequence = self._surface_heartbeat_sequence + 1
            try:
                broker.heartbeat(str(binding["binding_id"]), grant_id, sequence)
            except Exception as exc:
                self._surface_control_error = exc
                self._surface_wait_reason = (
                    "Surface control grant expired or was revoked; wait for the host to inspect "
                    "human-control state and source epoch, then issue a fresh grant."
                )
                self._surface_fenced = True
                self._surface_heartbeat_stop.set()
                raise _SurfaceGrantWait(self._surface_wait_reason) from exc
            self._surface_heartbeat_sequence = sequence

    def _dispatch_surface_input(
        self,
        keys: str,
        *,
        quiet: float,
        idle: float,
        timeout: float,
    ) -> ScreenFrame:
        with self._surface_control_lock:
            return self._dispatch_surface_input_locked(
                keys, quiet=quiet, idle=idle, timeout=timeout
            )

    def _dispatch_surface_input_locked(
        self,
        keys: str,
        *,
        quiet: float,
        idle: float,
        timeout: float,
    ) -> ScreenFrame:
        broker = self._surface_broker
        binding = self._surface_binding
        session = self.session
        if broker is None or binding is None or session is None:
            raise SurfaceTerminalError("Surface runner input is not bound")
        if self._surface_fenced:
            if self._surface_wait_kind:
                raise _SurfaceGrantWait(self._surface_wait_reason)
            raise SurfaceTerminalError("Surface runner input is fenced; no key was sent")
        self._renew_surface_lease()
        grant_id = self._surface_grant_id
        if grant_id is None:
            raise SurfaceTerminalError("Surface runner grant is no longer active")
        if self._surface_control_sequence >= self._surface_grant_max_updates:
            reason = (
                "Surface control grant has no remaining updates; wait for the host to inspect "
                "human-control state and issue a fresh grant."
            )
            self._set_surface_wait("grant", reason)
            raise _SurfaceGrantWait(reason)
        sequence = self._surface_control_sequence + 1
        operation_id = f"conpty-{uuid4().hex}"
        now = time.monotonic_ns()
        intent: dict[str, Any] = {
            "operation_id": operation_id,
            "mission_id": self._surface_mission_id,
            "binding_id": str(binding["binding_id"]),
            "grant_id": grant_id,
            "operation": "keyboard.text",
            "payload": {
                "text": keys,
                "quiet": quiet,
                "idle": idle,
                "timeout": timeout,
            },
            "expected_source_epoch": int(binding["source_epoch"]),
            "expected_geometry_revision": int(binding["geometry_revision"]),
            "sequence": sequence,
            "created_ns": now,
            "deadline_ns": now + int(min(timeout + quiet, 30.0) * 1_000_000_000),
            "max_duration_ns": max(1, int(min(timeout + quiet, 30.0) * 1_000_000_000)),
            "expected_effect": {"kind": "conpty-keyboard-text"},
            "stop_conditions": {"on_takeover": True, "on_source_epoch_change": True},
        }
        focus_epoch = self._surface_grant.get("focus_epoch", binding.get("focus_epoch"))
        if isinstance(focus_epoch, int) and not isinstance(focus_epoch, bool):
            intent["expected_focus_epoch"] = focus_epoch
        try:
            result = broker.submit_intent(intent)
        except Exception as exc:
            reason = (
                "Surface keyboard outcome is unknown; input stopped. The host must inspect and reconcile "
                "this operation before issuing another grant."
            )
            with self._surface_control_lock:
                self._set_surface_wait("reconciliation", reason, exc)
            self._surface_effects.append(
                {
                    "operation_id": operation_id,
                    "grant_generation": self._surface_grant_generation,
                    "sequence": sequence,
                    "state": "unknown",
                    "disposition": "unknown",
                    "delivered_count": 0,
                    "ack_strength": "none",
                    "reconciliation_required": True,
                    "detail": f"{type(exc).__name__}: {exc}"[:256],
                }
            )
            del self._surface_effects[:-256]
            raise _SurfaceGrantWait(reason) from exc
        self._surface_control_sequence = sequence
        record = {
            "operation_id": result.get("operation_id", operation_id),
            "grant_generation": self._surface_grant_generation,
            "sequence": result.get("sequence", sequence),
            "state": result.get("state"),
            "disposition": result.get("disposition"),
            "delivered_count": result.get("delivered_count", 0),
            "ack_strength": result.get("ack_strength"),
            "reconciliation_required": bool(result.get("reconciliation_required")),
            "detail": str(result.get("detail") or "")[:256],
        }
        self._surface_effects.append(record)
        del self._surface_effects[:-256]
        if result.get("state") != "settled":
            reason = (
                "Surface keyboard operation has not settled; wait for host reconciliation before resuming."
            )
            with self._surface_control_lock:
                self._set_surface_wait("reconciliation", reason)
            raise _SurfaceGrantWait(reason)
        disposition = result.get("disposition")
        if disposition in {"unknown", "partially-delivered"}:
            reason = (
                "Surface keyboard outcome is uncertain; no key was replayed and host reconciliation is required."
            )
            with self._surface_control_lock:
                self._set_surface_wait("reconciliation", reason)
            raise _SurfaceGrantWait(reason)
        if disposition != "delivered":
            reason = (
                f"Surface keyboard input was not delivered ({disposition or 'no disposition'}); "
                "the host must inspect human-control state and source epoch before reauthorization."
            )
            with self._surface_control_lock:
                self._set_surface_wait("grant", reason)
            raise _SurfaceGrantWait(reason)
        return self.frame()

    def _surface_terminal_closing(self, session: TerminalSession) -> None:
        with self._surface_control_lock:
            self._surface_fenced = True
            self._stop_surface_heartbeat()
            binding = self._surface_binding
            broker = self._surface_broker
            if binding is not None and broker is not None:
                if self._surface_wait_kind:
                    self._surface_last_binding = dict(binding)
                    self._surface_cleanup = {
                        "state": "host-control-wait",
                        "neutralization_confirmed": None,
                    }
                    self._surface_binding = None
                    self._surface_grant_id = None
                    self._surface_grant = {}
                else:
                    try:
                        inspected = broker.inspect_binding(str(binding["binding_id"]))
                    except Exception:
                        inspected = None
                    if (
                        not isinstance(inspected, Mapping)
                        or inspected.get("human_control") is not False
                        or inspected.get("inhibited") is not False
                    ):
                        self._surface_last_binding = dict(binding)
                        self._surface_cleanup = {
                            "state": "control-owner-preserved",
                            "neutralization_confirmed": None,
                        }
                        self._surface_binding = None
                        self._surface_grant_id = None
                        self._surface_grant = {}
                    else:
                        self._revoke_surface_binding(binding, broker)
            if self._surface_backend is not None:
                self._surface_backend.detach(session)

    def _revoke_surface_binding(self, binding: Mapping[str, Any], broker: Any) -> None:
        self._surface_last_binding = dict(binding)
        try:
            result = broker.revoke(str(binding["binding_id"]))
            neutral = result.get("neutralization")
            self._surface_cleanup = {
                "state": result.get("state"),
                "neutralization_confirmed": (
                    bool(neutral.get("confirmed")) if isinstance(neutral, Mapping) else False
                ),
            }
        except Exception as exc:
            self._surface_cleanup = {
                "state": "revoke-error",
                "reason": f"{type(exc).__name__}: {exc}"[:256],
                "neutralization_confirmed": False,
            }
        self._surface_binding = None
        self._surface_grant_id = None
        self._surface_grant = {}

        self._surface_fenced = True

    def _stop_surface_heartbeat(self) -> None:
        self._surface_heartbeat_stop.set()
        thread = self._surface_heartbeat_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        self._surface_heartbeat_thread = None

    def fence_surface(self) -> None:
        """Stop autonomous input before interruption cleanup or takeover exit."""
        with self._surface_control_lock:
            self._surface_fenced = True
            self._stop_surface_heartbeat()
            binding = self._surface_binding
            broker = self._surface_broker
            if binding is None or broker is None:
                return
            if self._surface_wait_kind:
                return
            try:
                inspected = broker.inspect_binding(str(binding["binding_id"]))
            except Exception:
                inspected = None
            if (
                not isinstance(inspected, Mapping)
                or inspected.get("human_control") is not False
                or inspected.get("inhibited") is not False
            ):
                self._surface_cleanup = {
                    "state": "control-owner-preserved",
                    "neutralization_confirmed": None,
                }
                return
            self._revoke_surface_binding(binding, broker)


    # -- hooks a game fills in -------------------------------------------
    def argv(self) -> Sequence[str]:
        raise WorldError(f"world {self.name!r} does not declare a program to run")

    def self_position(self, frame: ScreenFrame) -> tuple[int, int] | None:
        """Where the player is on screen, when the screen says so.

        '@' is the conventional "you" of a screen game; a game that draws its
        own avatar overrides this.  Knowing whether the last turn moved the
        player is the difference between reading a screen and reading a room.
        """
        return locate(frame, "@")

    def handshake(self, session: TerminalSession) -> None:
        """Dismiss titles, answer the first prompts, reach the playable screen."""
        session.wait_quiet(quiet=self.quiet, timeout=30.0)

    def read(self, frame: ScreenFrame) -> Mapping[str, Any]:
        """Interpret a settled frame.

        Returns any of `summary`, `events`, `prompt`, `done`, `score`.
        """
        return {}

    def vocabulary(self, frame: ScreenFrame) -> tuple[Action, ...]:
        raise WorldError(f"world {self.name!r} does not declare any actions")

    def level_cells(self, frame: ScreenFrame) -> Mapping[tuple[int, int], str]:
        """The map as memory classes; a game that has a map overrides this."""
        return {}

    def map_cell(self, position: tuple[int, int] | None) -> tuple[int, int] | None:
        """A screen position as a map cell; the two are the same by default."""
        return position

    def blocked_cell(
        self, position: tuple[int, int] | None, action: Action, *, moved: bool
    ) -> tuple[int, int, str] | None:
        """The cell that just refused the player, or None if the turn worked.

        A failed step blames the cell it tried to enter; anything else that
        failed (a door that would not open, a wall you searched) blames the cell
        the player stands on.  The kind of refusal is read from the game's own
        message: a locked door, a creature standing in the cell, or the cell
        itself being impassable.
        """
        if moved or position is None:
            return None
        step = MOVE_DELTAS.get(action.key)
        said = self.last_note.lower()
        named_door = "door" in said or "locked" in said
        if step is None and not named_door:
            # Something other than a step failed, and the game did not name a
            # door: that is not a fact about any cell, so the memory keeps none.
            return None
        cell = position if step is None else (position[0] + step[0], position[1] + step[1])
        if named_door:
            kind = "door"
        elif "blocked by" in said or "in the way" in said:
            # Something living stood in the cell: the cell is fine, the moment
            # was not, so the player must not remember it as impassable.
            kind = "creature"
        else:
            kind = "blocked"
        return (cell[0], cell[1], kind)

    # -- lifecycle -------------------------------------------------------
    def reset(self) -> Observation:
        self.close()
        self.turn = 0
        self.score = 0.0
        self.done = False
        self.messages.clear()
        self.history.clear()
        self._last_message = ""
        self._position = None

        self._surface_publication = None
        self._surface_cleanup = {}
        self._surface_effects.clear()
        self._surface_fenced = False
        self._surface_wait_kind = ""
        self._surface_wait_reason = ""
        self._surface_control_error = None
        session = TerminalSession(
            self.argv(),
            cols=self.cols,
            rows=self.rows,
            cwd=self.cwd,
            env=self.env,
        )
        try:
            session.start()
            self.session = session
            self._started_at = time.time()
            handshake_session: Any = session
            if self._surface_broker is not None:
                self._bind_surface_session(session)
                handshake_session = _SurfaceSessionView(self, session)
            self.handshake(handshake_session)
        except BaseException:
            if self.session is session:
                self.session = None
            session.close()
            raise
        return self.observe()

    def close(self) -> None:
        session, self.session = self.session, None
        if session is not None:
            session.close()
        elif self._surface_binding is not None:
            self.fence_surface()

    def __enter__(self) -> "ScreenWorld":
        self.reset()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- seam ------------------------------------------------------------
    def frame(self) -> ScreenFrame:
        session = self.session
        if session is None:
            raise WorldError(f"world {self.name!r} is not running")
        if self._surface_broker is None:
            return session.frame()
        binding = self._surface_binding
        backend = self._surface_backend
        if binding is None or backend is None:
            raise SurfaceTerminalError("Surface observation source is fenced or unavailable")
        publication = self._surface_broker.capture(
            str(binding["binding_id"]), channels=("accessibility",)
        )
        if not isinstance(publication, Mapping):
            raise SurfaceTerminalError("Surface broker did not return a publication")
        if (
            publication.get("binding_id") != binding.get("binding_id")
            or publication.get("source_epoch") != binding.get("source_epoch")
        ):
            self._surface_fenced = True
            raise SurfaceTerminalError("Surface publication belongs to a different terminal epoch")
        self._surface_publication = dict(publication)
        return backend.last_frame()

    def observe(self) -> Observation:
        frame = self.frame()
        reading = dict(self.read(frame))
        message = str(reading.get("message") or "").strip()
        fresh: list[str] = []
        for item in (message, *(reading.get("events") or ())):
            item = str(item).strip()
            if item and item != self._last_message:
                fresh.append(item)
                self.messages.append(item)
                self._last_message = item
        self.done = bool(reading.get("done", self.done)) or bool(self._surface_wait_kind)
        self.score = float(reading.get("score", self.score))
        summary = dict(reading.get("summary") or {})
        position = self.self_position(frame)
        if position is not None:
            if self._position is not None:
                summary["moved"] = position != self._position
            self._position = position
        self.position = position
        summary["message"] = message
        summary.setdefault("turn", self.turn)
        summary.setdefault("elapsed", round(time.time() - self._started_at, 1))
        return Observation(
            screen=_trim(frame.lines),
            summary=summary,
            events=tuple(fresh),
            prompt=reading.get("prompt"),
            done=self.done,
            score=self.score,
            turn=self.turn,
        )

    def actions(self) -> tuple[Action, ...]:
        return self.vocabulary(self.frame())

    def act(self, action: Action) -> StepResult:
        session = self.session
        if session is None:
            raise WorldError(f"world {self.name!r} is not running")
        if self.done:
            raise WorldError(f"world {self.name!r} is finished; no further actions")
        self.observe()  # consume whatever the world was already showing
        try:
            session.send(action.keys, quiet=self.quiet, idle=self.idle)
        except (TerminalError, SurfaceTerminalError) as exc:
            self.done = True
            observation = self.observe()
            note = str(exc)
            category = (
                "surface wait"
                if isinstance(exc, _SurfaceGrantWait)
                else "surface control error"
                if isinstance(exc, SurfaceTerminalError)
                else "terminal closed"
            )
            self.history.append(
                {
                    "turn": self.turn,
                    "action": action.as_dict(),
                    "note": f"{category}: {note}",
                    "score": self.score,
                }
            )
            return StepResult(observation=observation, accepted=False, note=note)
        self.turn += 1
        observation = self.observe()
        note = (
            observation.events[-1]
            if observation.events
            else (observation.prompt or "")
        )
        if not note and observation.summary.get("moved") is False:
            note = "you did not move"
        self.last_note = note
        result = StepResult(observation=observation, accepted=True, note=note)
        self.history.append(
            {
                "turn": self.turn,
                "action": action.as_dict(),
                "note": note,
                "score": self.score,
                "events": list(observation.events),
            }
        )
        return result

    # -- shared helpers --------------------------------------------------
    def message_line(self, frame: ScreenFrame) -> str:
        """The world's own one-line status: row 0 for most terminal games."""
        if not frame.lines:
            return ""
        return frame.lines[0].strip()

    def matches(self, frame: ScreenFrame, *needles: str) -> bool:
        text = frame.text
        return any(needle in text for needle in needles)


class _SurfaceSessionView:
    """Keep game handshakes on the same brokered frame/input transport."""

    def __init__(self, world: ScreenWorld, session: TerminalSession) -> None:
        self._world = world
        self._session = session

    def frame(self) -> ScreenFrame:
        return self._world.frame()

    def wait_change(self, revision: int, **kwargs: Any) -> bool:
        return self._session.wait_change(revision, **kwargs)

    def wait_quiet(self, **kwargs: Any) -> bool:
        return self._session.wait_quiet(**kwargs)

    def send(self, keys: str, **kwargs: Any) -> ScreenFrame:
        return self._session.send(keys, **kwargs)

    def exited(self) -> bool:
        return self._session.exited()



def _trim(lines: Sequence[str]) -> tuple[str, ...]:
    trimmed = list(lines)
    while trimmed and not trimmed[-1].strip():
        trimmed.pop()
    return tuple(trimmed)


def locate(frame: ScreenFrame, glyph: str) -> tuple[int, int] | None:
    """First cell holding `glyph` in a screen frame."""
    for row, line in enumerate(frame.lines):
        column = line.find(glyph)
        if column >= 0:
            return row, column
    return None
