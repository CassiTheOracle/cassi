import hashlib
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from cassi_entity_activities import PCSX2Activity, ActivityRefused, _identity
from pcsx2 import compare_snapshots as real_compare_snapshots
from pcsx2.gameplay import GameplayFocusLost, GameplayInputError


PINE_IDENTITY = {
    "emulator": "pcsx2",
    "version": "PCSX2 v2.8.2",
    "status": 0,
    "status_name": "running",
    "title": "Test Game",
    "game_id": "SLUS-20111",
    "game_uuid": "1a2b3c4d",
    "game_version": "1.00",
}


class FakeBrain:
    def __init__(self, content=None, error=None, finish_reason="stop"):
        self.content = content
        self.error = error
        self.finish_reason = finish_reason
        self.requests = []

    def complete(self, *, prompt, max_tokens, thinking=False, response_format=None):
        self.requests.append({"prompt": prompt, "max_tokens": max_tokens})
        if self.error is not None:
            raise self.error
        return {"content": self.content, "finish_reason": self.finish_reason}


class FakeEntity:
    def __init__(self, tmp_path, programs, brain=None, binding_record=None,
                 capture_publication=None, capture_error=None):
        self.config = SimpleNamespace(data_home=tmp_path / "member", entity_id="cassi-test")
        self.brain = brain
        self._programs = programs
        self.researcher = self
        self.received = None
        self.recorded = []
        self.binding_calls = []
        self.capture_calls = []
        self._binding_record = binding_record
        self._capture_publication = capture_publication
        self._capture_error = capture_error

    def program(self, program_id):
        return self._programs.get(program_id)

    def _record(self, **kwargs):
        self.recorded.append(kwargs) if hasattr(self, "recorded") else None
        self.received = kwargs
        return {"source_id": kwargs.get("source_id")}

    def inspect_surface_binding(self, binding_id, *, program_id, grant_id=None):
        self.binding_calls.append((binding_id, program_id))
        record = self._binding_record
        if isinstance(record, Exception):
            raise record
        return record

    def capture_surface(self, binding_id, *, program_id):
        self.capture_calls.append((binding_id, program_id))
        if self._capture_error is not None:
            raise self._capture_error
        return self._capture_publication


def _program(operations, program_id="program-1"):
    return {
        "program_id": program_id,
        "project_id": "project-1",
        "status": "active",
        "activity_scope": {"activities": {"pcsx2": list(operations)}},
    }


def _install_fake_pcsx2(monkeypatch, *, records, edges, strings=None,
                        references=None, identity=PINE_IDENTITY,
                        identity_sequence=None):
    calls = {"catalog": 0, "clients": 0, "snapshots": 0, "identities": 0}
    memory = bytearray(0x100_000)

    class FakeRecord:
        def __init__(self, address, size, name, source, evidence=None):
            self.address = address
            self.size = size
            self.name = name
            self.source = source
            self.evidence = evidence or {}

    class FakeAtlas:
        def __init__(self):
            self.identity = {
                "title": "Test Game",
                "serial": "SLUS-20111",
                "boot_serial": "SLUS-20111",
                "pcsx2_crc": "1A2B3C4D",
                "machine": "mips/r5900",
                "entry": 0x001000,
                "elf_sha256": "e" * 64,
                "iso_sha256": "i" * 64,
            }

        def summary(self):
            return {
                "functions": len(records),
                "strings": len(strings or ()),
                "references": len(references or {}),
                "paths": {
                    "iso": str(_ISO_PATH[0]),
                    "atlas": str(_ATLAS_PATH[0]),
                    "sym": str(_SYM_PATH[0]),
                },
                "identity": dict(self.identity),
            }

        def functions_for_address(self, address):
            return tuple(
                record
                for record in records
                if record.size is not None
                and record.address <= address < record.address + record.size
            )

        def symbol_at(self, address):
            covering = [
                record for record in records
                if record.size is not None
                and record.address <= address < record.address + record.size
            ]
            pool = covering or [record for record in records if record.address <= address]
            if not pool:
                return None
            return max(pool, key=lambda record: record.address)

        def callers_of(self, address):
            return tuple(sorted(set(edges.get(("callers", address), ()))))

        def callees_of(self, address):
            return tuple(sorted(set(edges.get(("callees", address), ()))))

        def references_for_address(self, address):
            return list((references or {}).get(address, ()))

        def references_near_address(self, address, span=64):
            return [
                row
                for target, rows in (references or {}).items()
                if address - span <= target <= address + span
                for row in rows
            ]

        def strings_near(self, address, span=64):
            return list(strings or ())

    def catalog_iso(iso_path, output_dir):
        calls["catalog"] += 1
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        atlas_json = output_dir / "atlas.json"
        sym_path = output_dir / "game.sym"
        _ATLAS_PATH[0] = atlas_json
        _SYM_PATH[0] = sym_path
        atlas = FakeAtlas()
        atlas_json.write_bytes(
            json.dumps(atlas.summary(), ensure_ascii=False, sort_keys=True).encode("utf-8"),
        )
        sym_path.write_bytes(b"00000100 T Foo\n00001020 T Bar\n")
        return atlas

    class FakePineError(RuntimeError):
        pass

    class FakePineClient:
        def __init__(self, *, host, slot, timeout, allow_effects):
            assert allow_effects is False, "the hosted activity must stay read-only"
            calls["clients"] += 1

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def identity(self):
            sequence = identity_sequence or (identity,)
            index = min(calls["identities"], len(sequence) - 1)
            calls["identities"] += 1
            return dict(sequence[index])

        def read(self, address, size):
            if address + size > len(memory):
                raise FakePineError("read out of range")
            return bytes(memory[address:address + size])

        def write(self, address, data):
            raise FakePineError("effects are disabled")

    def compare_snapshots(before, after, *, base_address, page_size=4096):
        calls["snapshots"] += 1
        return real_compare_snapshots(
            before, after, base_address=base_address, page_size=page_size,
        )

    module = types.ModuleType("pcsx2")
    module.PineClient = FakePineClient
    module.PineError = FakePineError
    module.catalog_iso = catalog_iso
    module.FunctionAtlas = FakeAtlas
    module.compare_snapshots = compare_snapshots
    monkeypatch.setitem(sys.modules, "pcsx2", module)
    return calls, memory


_ISO_PATH: list = [None]
_SYM_PATH: list = [None]
_ATLAS_PATH: list = [None]

def _evidence(address, name):
    return {
        "sha256": hashlib.sha256(name.encode()).hexdigest(),
        "instructions": [
            {"address": address, "word": 0x03E00008, "text": "jr $ra"},
            {"address": address + 4, "word": 0x00000000, "text": "nop"},
        ],
    }


_FOO = SimpleNamespace(address=0x001000, size=0x20, name="Foo", source="symbol",
                       evidence=_evidence(0x001000, "Foo"))
_BAR = SimpleNamespace(address=0x001020, size=0x20, name="Bar", source="jal-target",
                       evidence=_evidence(0x001020, "Bar"))
_EDGES = {
    ("callees", 0x001000): (0x001020,),
    ("callers", 0x001020): (0x001000,),
}
_REFERENCES = {
    0x001004: ({"kind": "call", "from_address": 0x000900, "to_address": 0x001000,
                "disasm": "jal 0x001000"},),
    0x002008: ({"kind": "data", "from_address": 0x001004, "to_address": 0x002008,
                "disasm": "addiu $a0, $a0, 0x2008"},),
}
_STRINGS = ("health restored",)


def _controller_state(packet, *, buttons=0, pressed=()):
    return {
        "packet_number": packet,
        "buttons": buttons,
        "pressed": list(pressed),
        "left_trigger": 0,
        "right_trigger": 0,
        "left_stick_x": 0,
        "left_stick_y": 0,
        "right_stick_x": 0,
        "right_stick_y": 0,
    }


class FakeGameplaySource:
    def __init__(
        self, memory, states, values, *, focus_gaps=(),
        post_read_focus_gaps=(), pine_error=None,
    ):
        self.memory = memory
        self.states = list(states)
        self.values = list(values)
        self.focus_gaps = set(focus_gaps)
        self.post_read_focus_gaps = set(post_read_focus_gaps)
        self.pine_error = pine_error
        self.samples = 0
        self.begins = 0
        self.ends = 0
        self.focus_checks = 0
        self.pine_checks = []
        self.bound = False

    def describe(self):
        return {
            "backend": "windows-xinput",
            "slot": 0,
            "process": "pcsx2-qt.exe",
            "pid": 4242 if self.bound else None,
        }

    def begin_session(self):
        self.begins += 1
        self.bound = True
        return self.describe()

    def assert_pine_endpoint(self, host, port):
        self.pine_checks.append((host, port))
        if self.pine_error is not None:
            raise self.pine_error

    def sample(self):
        index = self.samples
        self.samples += 1
        if index in self.focus_gaps:
            raise GameplayFocusLost("PCSX2 lost foreground focus")
        self.memory[0x002008] = self.values[index]
        return self.states[index]

    def assert_foreground(self):
        self.focus_checks += 1
        if self.samples - 1 in self.post_read_focus_gaps:
            raise GameplayFocusLost("PCSX2 lost foreground focus after memory read")

    def end_session(self):
        self.ends += 1
        self.bound = False

def _activity(tmp_path, monkeypatch, **kwargs):
    iso = tmp_path / "game.iso"
    iso.write_bytes(b"PS2-ISO-CONTENT")
    _ISO_PATH[0] = iso
    home = tmp_path / "pcsx2-home"
    home.mkdir()
    references = kwargs.pop("references", dict(_REFERENCES))
    calls, memory = _install_fake_pcsx2(
        monkeypatch,
        records=[_FOO, _BAR],
        edges=dict(_EDGES),
        strings=_STRINGS,
        references=references,
        **kwargs,
    )
    activity = PCSX2Activity(iso_path=iso, data_home=home)
    return activity, calls, memory


def test_host_configuration_rejects_inconsistent_paths_and_bounds(tmp_path):
    iso = tmp_path / "game.iso"
    iso.write_bytes(b"ISO")
    home = tmp_path / "home"
    home.mkdir()
    with pytest.raises(ActivityRefused):
        PCSX2Activity(iso_path=Path("relative.iso"), data_home=home)
    with pytest.raises(ActivityRefused):
        PCSX2Activity(iso_path=tmp_path / "missing.iso", data_home=home)
    with pytest.raises(ActivityRefused):
        PCSX2Activity(iso_path=iso, data_home=tmp_path / "missing-home")
    with pytest.raises(ActivityRefused):
        PCSX2Activity(iso_path=iso, data_home=home, pine_slot=0)
    with pytest.raises(ActivityRefused):
        PCSX2Activity(iso_path=iso, data_home=home, pine_slot=65_536)
    with pytest.raises(ActivityRefused):
        PCSX2Activity(iso_path=iso, data_home=home, pine_host="bad host")
    with pytest.raises(ActivityRefused):
        PCSX2Activity(iso_path=iso, data_home=home, pine_timeout=0)
    with pytest.raises(ActivityRefused):
        PCSX2Activity(iso_path=iso, data_home=home, pine_timeout=61)
    with pytest.raises(ActivityRefused):
        PCSX2Activity(iso_path=iso, data_home=home, max_observation_bytes=1 << 21)
    with pytest.raises(ActivityRefused):
        PCSX2Activity(iso_path=iso, data_home=home, xinput_slot=4)
    with pytest.raises(ActivityRefused):
        PCSX2Activity(iso_path=iso, data_home=home, max_capture_samples=1)
    assert PCSX2Activity(iso_path=str(iso), data_home=home).iso_path == iso.resolve()


def test_describe_is_read_only_and_bounded(tmp_path, monkeypatch):
    activity, _, _ = _activity(tmp_path, monkeypatch)
    described = activity.describe()
    assert described["pine"] == {"host": "127.0.0.1", "slot": 28_011, "read_only": True}
    assert described["input"] == {
        "backend": "windows-xinput",
        "slot": 0,
        "process": "pcsx2-qt.exe",
        "foreground_only": True,
    }
    assert described["max_observation_bytes"] == 65_536
    assert described["max_capture_samples"] == 3_600
    assert described["max_capture_seconds"] == 300
    assert described["source"].endswith("game.iso")


def test_program_scope_gates_every_operation(tmp_path, monkeypatch):
    activity, _, _ = _activity(tmp_path, monkeypatch)
    entity = FakeEntity(tmp_path, {"program-1": _program(["catalog"])})
    activity.attach(entity)
    with pytest.raises(ActivityRefused):
        activity.run("observe", {}, program={"program_id": "program-1"},
                     operation_id="obs-1")
    with pytest.raises(ActivityRefused):
        activity.run("capture-session", {}, program={"program_id": "program-1"},
                     operation_id="capture-1")
    with pytest.raises(ActivityRefused):
        activity.run("decompile", {}, program={"program_id": "program-1"},
                     operation_id="dc-1")
    with pytest.raises(ActivityRefused):
        activity.run("teleport", {}, program={"program_id": "program-1"},
                     operation_id="tp-1")
    assert entity.received is None or "pcsx2" not in json.dumps(entity.received, default=str)


def test_observe_persists_exact_artifact_and_replays_idempotently(tmp_path, monkeypatch):
    activity, calls, memory = _activity(tmp_path, monkeypatch)
    entity = FakeEntity(tmp_path, {"program-1": _program(["catalog", "observe"])})
    activity.attach(entity)
    memory[0x001004:0x001008] = b"\x39\x05\x00\x00"
    first = activity.run(
        "observe",
        {"address": 0x001000, "size": 0x40, "label": "calm window"},
        program={"program_id": "program-1"},
        operation_id="obs-1",
    )
    assert first["status"] == "COMPLETE"
    assert first["address"] == 0x001000
    assert first["size"] == 0x40
    assert first["label"] == "calm window"
    assert first["pine_identity"] == PINE_IDENTITY
    stored = Path(first["artifact"]["memory_path"]).read_bytes()
    assert stored == bytes(memory[0x001000:0x001040])
    assert first["sha256"] == hashlib.sha256(stored).hexdigest()
    metadata = json.loads(Path(first["artifact"]["metadata_path"]).read_text(encoding="utf-8"))
    assert metadata["data_sha256"] == first["sha256"]
    assert metadata["iso_sha256"] == hashlib.sha256(_ISO_PATH[0].read_bytes()).hexdigest()
    assert metadata["pine_identity"]["game_id"] == "SLUS-20111"

    first_field_record = dict(entity.recorded[-1])
    clients_before = calls["clients"]
    second = activity.run(
        "observe",
        {"address": 0x001000, "size": 0x40, "label": "calm window"},
        program={"program_id": "program-1"},
        operation_id="obs-1",
    )
    assert second == first
    assert calls["clients"] == clients_before

    assert len(entity.recorded) == 2
    assert entity.recorded[0] == entity.recorded[1] == first_field_record

def test_observe_refuses_oversized_or_unknown_parameters(tmp_path, monkeypatch):
    activity, _, _ = _activity(tmp_path, monkeypatch)
    activity.attach(FakeEntity(tmp_path, {"program-1": _program(["observe"])}))
    with pytest.raises(ActivityRefused):
        activity.run("observe", {"size": 65_537}, program={"program_id": "program-1"},
                     operation_id="too-big")
    with pytest.raises(ActivityRefused):
        activity.run("observe", {"address": -1}, program={"program_id": "program-1"},
                     operation_id="negative")
    with pytest.raises(ActivityRefused):
        activity.run("observe", {"cheat": True}, program={"program_id": "program-1"},
                     operation_id="unknown-key")
    with pytest.raises(ActivityRefused):
        activity.run("observe", {"label": "bad\nlabel"}, program={"program_id": "program-1"},
                     operation_id="bad-label")
    crossing_id = "crossing-window"
    with pytest.raises(ActivityRefused, match="32-bit"):
        activity.run(
            "observe", {"address": 0xFFFF_FFFF, "size": 2},
            program={"program_id": "program-1"}, operation_id=crossing_id,
        )
    assert not (
        activity.data_home / "operations" / _identity(crossing_id) / "intent.json"
    ).exists()


def test_capture_session_synchronizes_input_memory_and_function_evidence(
    tmp_path, monkeypatch,
):
    activity, calls, memory = _activity(tmp_path, monkeypatch)
    source = FakeGameplaySource(
        memory,
        [
            _controller_state(1),
            _controller_state(2, buttons=0x1000, pressed=("a",)),
            _controller_state(2, buttons=0x1000, pressed=("a",)),
        ],
        [0, 1, 2],
    )
    activity._gameplay_input_source = source
    entity = FakeEntity(
        tmp_path, {"program-1": _program(["capture-session"])},
    )
    activity.attach(entity)
    monkeypatch.setattr("cassi_entity_activities.time.sleep", lambda _seconds: None)

    first = activity.run(
        "capture-session",
        {
            "address": 0x002000,
            "size": 0x40,
            "label": "press A near game state",
            "samples": 3,
            "sample_hz": 60,
        },
        program={"program_id": "program-1"},
        operation_id="gameplay-1",
    )

    assert first["status"] == "COMPLETE"
    assert first["samples"]["requested"] == first["samples"]["captured"] == 3
    assert first["samples"]["focus_gaps"] == 0
    assert first["temporal_evidence"] == {
        "kind": "sampled-host-input-followed-by-memory",
        "interpretation": "temporal-response-hypothesis",
        "transition_samples": 1,
        "transition_count": 1,
        "analyzed_episodes": 1,
        "unresolved_episodes": 0,
    }
    episode = first["episodes"][0]
    assert episode["transitions"][0]["control"] == "a"
    assert episode["changes"]["changed_ranges"] == [{
        "start": 0x002008,
        "end": 0x002009,
        "length": 1,
    }]
    assert episode["function_evidence"][0]["name"] == "Foo"
    assert episode["function_evidence"][0]["reference_hits"] == 1
    assert first["function_evidence"][0]["name"] == "Foo"
    assert first["function_evidence"][0]["episode_count"] == 1
    assert first["controls"] == [{"control": "a", "events": 1}]
    assert calls["snapshots"] == 1
    assert source.begins == source.ends == 1

    artifact_path = Path(first["artifact"]["path"])
    artifact_body = artifact_path.read_bytes()
    assert first["artifact"]["sha256"] == hashlib.sha256(artifact_body).hexdigest()
    manifest = json.loads(artifact_body)
    assert manifest["schema"] == "cassi-pcsx2-gameplay-v1"
    assert [row["status"] for row in manifest["samples"]] == [
        "captured", "captured", "captured",
    ]
    assert manifest["input_source"]["pid"] == 4242
    assert source.pine_checks == [("127.0.0.1", 28011)]
    assert source.focus_checks == 3
    timeline = {row["seq"]: row for row in manifest["samples"]}
    assert all(
        row["input_monotonic_ns"] <= row["memory_monotonic_ns"]
        for row in timeline.values()
    )
    assert episode["transition_monotonic_ns"] == (
        timeline[episode["transition_seq"]]["input_monotonic_ns"]
    )
    assert episode["response_monotonic_ns"] == (
        timeline[episode["response_seq"]]["memory_monotonic_ns"]
    )
    assert episode["latency_ns"] == (
        episode["response_monotonic_ns"] - episode["transition_monotonic_ns"]
    )
    for row in manifest["samples"]:
        sha = row["snapshot"]["sha256"]
        blob = activity.data_home / "observations" / "data" / f"{sha}.bin"
        assert hashlib.sha256(blob.read_bytes()).hexdigest() == sha
    assert entity.received["payload"]["operation"] == "capture-session"
    assert entity.received["payload"]["result"]["session_id"] == first["session_id"]

    clients_before = calls["clients"]
    samples_before = source.samples
    replay = activity.run(
        "capture-session",
        {
            "address": 0x002000,
            "size": 0x40,
            "label": "press A near game state",
            "samples": 3,
            "sample_hz": 60,
        },
        program={"program_id": "program-1"},
        operation_id="gameplay-1",
    )
    assert replay == first
    assert calls["clients"] == clients_before
    assert source.samples == samples_before
    iso_body = activity.iso_path.read_bytes()
    activity.iso_path.write_bytes(b"changed-PS2-ISO")
    with pytest.raises(ActivityRefused, match="another session"):
        activity.run(
            "capture-session",
            {
                "address": 0x002000,
                "size": 0x40,
                "label": "press A near game state",
                "samples": 3,
                "sample_hz": 60,
            },
            program={"program_id": "program-1"},
            operation_id="gameplay-1",
        )
    activity.iso_path.write_bytes(iso_body)


    artifact_path.write_bytes(artifact_body + b" ")
    with pytest.raises(ActivityRefused, match="artifact digest"):
        activity.run(
            "capture-session",
            {
                "address": 0x002000,
                "size": 0x40,
                "label": "press A near game state",
                "samples": 3,
                "sample_hz": 60,
            },
            program={"program_id": "program-1"},
            operation_id="gameplay-1",
        )


@pytest.mark.parametrize(
    "gap_kwargs",
    [
        {"focus_gaps": {1}},
        {"post_read_focus_gaps": {1}},
    ],
    ids=("before-input", "after-memory"),
)
def test_capture_session_records_focus_gaps_without_input_or_memory(
    tmp_path, monkeypatch, gap_kwargs,
):
    activity, _calls, memory = _activity(tmp_path, monkeypatch)
    source = FakeGameplaySource(
        memory,
        [
            _controller_state(1),
            _controller_state(2),
            _controller_state(3, buttons=0x1000, pressed=("a",)),
        ],
        [0, 1, 2],
        **gap_kwargs,
    )
    activity._gameplay_input_source = source
    activity.attach(FakeEntity(
        tmp_path, {"program-1": _program(["capture-session"])},
    ))
    monkeypatch.setattr("cassi_entity_activities.time.sleep", lambda _seconds: None)

    result = activity.run(
        "capture-session",
        {"address": 0x002000, "size": 0x40, "samples": 3, "sample_hz": 60},
        program={"program_id": "program-1"},
        operation_id="focus-gap",
    )

    assert result["samples"]["captured"] == 2
    assert result["samples"]["focus_gaps"] == 1
    assert result["temporal_evidence"]["transition_count"] == 0
    manifest = json.loads(Path(result["artifact"]["path"]).read_text(encoding="utf-8"))
    gap = manifest["samples"][1]
    assert gap == {
        "seq": 1,
        "monotonic_ns": gap["monotonic_ns"],
        "status": "focus-gap",
    }


def test_capture_session_keeps_an_unresolved_last_transition_in_controls(
    tmp_path, monkeypatch,
):
    activity, _calls, memory = _activity(tmp_path, monkeypatch)
    source = FakeGameplaySource(
        memory,
        [
            _controller_state(1),
            _controller_state(2, buttons=0x1000, pressed=("a",)),
        ],
        [0, 1],
    )
    activity._gameplay_input_source = source
    activity.attach(FakeEntity(
        tmp_path, {"program-1": _program(["capture-session"])},
    ))
    monkeypatch.setattr("cassi_entity_activities.time.sleep", lambda _seconds: None)

    result = activity.run(
        "capture-session",
        {"address": 0x002000, "size": 0x40, "samples": 2, "sample_hz": 60},
        program={"program_id": "program-1"},
        operation_id="unresolved-last-transition",
    )

    assert result["controls"] == [{"control": "a", "events": 1}]
    assert result["episodes"] == []
    assert result["function_evidence"] == []
    assert result["temporal_evidence"]["transition_count"] == 1
    assert result["temporal_evidence"]["analyzed_episodes"] == 0
    assert result["temporal_evidence"]["unresolved_episodes"] == 1


def test_capture_session_enforces_wall_clock_deadline_and_cleans_up(
    tmp_path, monkeypatch,
):
    activity, _calls, memory = _activity(tmp_path, monkeypatch)
    source = FakeGameplaySource(
        memory,
        [_controller_state(1), _controller_state(2)],
        [0, 1],
    )
    activity._gameplay_input_source = source
    activity.attach(FakeEntity(
        tmp_path, {"program-1": _program(["capture-session"])},
    ))
    clock = iter([0, 0, 0, 0, 0, 301_000_000_000, 301_000_000_000])
    monkeypatch.setattr(
        "cassi_entity_activities.time.monotonic_ns", lambda: next(clock),
    )
    monkeypatch.setattr("cassi_entity_activities.time.sleep", lambda _seconds: None)

    with pytest.raises(ActivityRefused, match="wall-clock deadline"):
        activity.run(
            "capture-session",
            {"address": 0x002000, "size": 0x40, "samples": 2, "sample_hz": 60},
            program={"program_id": "program-1"},
            operation_id="capture-deadline",
        )

    assert source.samples == 1
    assert source.ends == 1
    assert not (
        activity.data_home / "operations" / _identity("capture-deadline") / "receipt.json"
    ).exists()
    assert not (activity.data_home / "sessions").exists()


def test_capture_session_refuses_pine_listener_owned_by_another_process(
    tmp_path, monkeypatch,
):
    activity, _calls, memory = _activity(tmp_path, monkeypatch)
    source = FakeGameplaySource(
        memory,
        [_controller_state(1), _controller_state(2)],
        [0, 1],
        pine_error=GameplayInputError("PINE listener belongs to a different process"),
    )
    activity._gameplay_input_source = source
    activity.attach(FakeEntity(
        tmp_path, {"program-1": _program(["capture-session"])},
    ))

    with pytest.raises(ActivityRefused, match="PINE ownership"):
        activity.run(
            "capture-session",
            {"address": 0x002000, "size": 0x40, "samples": 2, "sample_hz": 60},
            program={"program_id": "program-1"},
            operation_id="wrong-pine-owner",
        )

    assert source.pine_checks == [("127.0.0.1", 28011)]
    assert source.samples == 0
    assert source.ends == 1
    assert not (activity.data_home / "sessions").exists()


def test_capture_session_refuses_unbounded_parameters_before_admission(
    tmp_path, monkeypatch,
):
    activity, _calls, _memory = _activity(tmp_path, monkeypatch)
    activity.attach(FakeEntity(
        tmp_path, {"program-1": _program(["capture-session"])},
    ))
    invalid = [
        ({"samples": 1}, "too-few"),
        ({"samples": 301, "sample_hz": 1}, "too-long"),
        ({"size": 65_536, "samples": 1_025, "sample_hz": 60}, "too-large"),
        ({"process": "other.exe"}, "select-process"),
    ]
    for parameters, operation_id in invalid:
        with pytest.raises(ActivityRefused):
            activity.run(
                "capture-session", parameters,
                program={"program_id": "program-1"}, operation_id=operation_id,
            )
        assert not (
            activity.data_home / "operations" / _identity(operation_id) / "intent.json"
        ).exists()


def test_capture_session_refuses_game_switch_before_persisting_evidence(
    tmp_path, monkeypatch,
):
    switched = {**PINE_IDENTITY, "game_id": "SLUS-99999", "game_uuid": "DEADBEEF"}
    activity, _calls, memory = _activity(
        tmp_path, monkeypatch, identity_sequence=(PINE_IDENTITY, switched),
    )
    source = FakeGameplaySource(
        memory,
        [_controller_state(1), _controller_state(2)],
        [0, 1],
    )
    activity._gameplay_input_source = source
    activity.attach(FakeEntity(
        tmp_path, {"program-1": _program(["capture-session"])},
    ))
    monkeypatch.setattr("cassi_entity_activities.time.sleep", lambda _seconds: None)

    with pytest.raises(ActivityRefused, match="fixed ISO identity|changed during"):
        activity.run(
            "capture-session",
            {"address": 0x002000, "size": 0x40, "samples": 2, "sample_hz": 60},
            program={"program_id": "program-1"},
            operation_id="switched-session",
        )
    assert source.ends == 1
    assert not (activity.data_home / "sessions").exists()
    assert not (activity.data_home / "observations" / "data").exists()


def test_surface_capture_requires_scope_and_stores_bounded_evidence(tmp_path, monkeypatch):
    activity, calls, memory = _activity(tmp_path, monkeypatch)
    from surface.records import SurfaceAuthorizationError
    program = _program(["observe"])
    program["surface_scope"] = {"sources": [{
        "backend_id": "windows", "source_id": "pcsx2-view",
        "observation": ["pixels"], "operations": [],
    }]}
    entity = FakeEntity(
        tmp_path, {"program-1": program},
        binding_record={"backend_id": "windows", "source_id": "pcsx2-view",
                        "modalities": ["pixels"]},
        capture_publication={"binding_id": "bind-1", "pixels": b"\x00" * 4096,
                             "generation": 3, "source_epoch": 11},
    )
    activity.attach(entity)
    result = activity.run(
        "observe", {"address": 0x001000, "size": 0x40, "binding_id": "bind-1"},
        program={"program_id": "program-1"}, operation_id="obs-surface",
    )
    assert entity.binding_calls == [("bind-1", "program-1")]
    assert entity.capture_calls == [("bind-1", "program-1")]
    surface = result["surface"]
    assert surface["backend_id"] == "windows"
    assert surface["source_id"] == "pcsx2-view"
    assert surface["modalities"] == ["pixels"]
    assert surface["publication"]["pixels"] == hashlib.sha256(b"\x00" * 4096).hexdigest()
    assert surface["publication"]["generation"] == 3
    receipt_text = json.dumps(result, default=str)
    assert "\\x00" not in receipt_text
    assert hashlib.sha256(b"\x00" * 4096).hexdigest() in receipt_text


def test_surface_capture_refuses_unscoped_bindings_and_errors(tmp_path, monkeypatch):
    activity, _, _ = _activity(tmp_path, monkeypatch)
    entity = FakeEntity(
        tmp_path, {"program-1": _program(["observe"])},
        binding_record={"backend_id": "windows", "source_id": "other-view",
                        "modalities": ["pixels"]},
    )
    activity.attach(entity)
    with pytest.raises(ActivityRefused):
        activity.run("observe", {"binding_id": "bind-1"},
                     program={"program_id": "program-1"}, operation_id="obs-bad")
    assert entity.binding_calls == [("bind-1", "program-1")]
    assert entity.capture_calls == []

    from surface.records import SurfaceAuthorizationError
    refusing = FakeEntity(
        tmp_path, {"program-1": _program(["observe"])},
        binding_record=SurfaceAuthorizationError("no scope"),
    )
    activity.attach(refusing)
    with pytest.raises(ActivityRefused, match="surface binding refused"):
        activity.run("observe", {"binding_id": "bind-1"},
                     program={"program_id": "program-1"}, operation_id="obs-refused")

    unscoped = FakeEntity(
        tmp_path, {"program-1": _program(["observe"])},
        binding_record={"backend_id": "windows", "source_id": "src",
                        "modalities": ["audio"]},
    )
    activity.attach(unscoped)
    with pytest.raises(ActivityRefused, match="no authorized observation modality"):
        activity.run("observe", {"binding_id": "bind-1"},
                     program={"program_id": "program-1"}, operation_id="obs-audio")


def test_catalog_exports_atlas_and_sym_artifacts(tmp_path, monkeypatch):
    activity, calls, _ = _activity(tmp_path, monkeypatch)
    activity.attach(FakeEntity(tmp_path, {"program-1": _program(["catalog"])}))
    summary = activity.run("catalog", {}, program={"program_id": "program-1"},
                           operation_id="cat-1")
    assert summary["status"] == "COMPLETE"
    assert summary["catalog"]["functions"] == 2
    assert summary["atlas_identity"]["serial"] == "SLUS-20111"
    atlas_json = Path(summary["catalog"]["paths"]["atlas"])
    sym_path = Path(summary["catalog"]["paths"]["sym"])
    assert atlas_json.is_file() and sym_path.is_file()
    assert summary["artifact"]["sym_sha256"] == hashlib.sha256(sym_path.read_bytes()).hexdigest()
    assert summary["artifact"]["atlas_sha256"] == hashlib.sha256(atlas_json.read_bytes()).hexdigest()

    calls["catalog"] = 0
    replay = activity.run("catalog", {}, program={"program_id": "program-1"},
                          operation_id="cat-1")
    assert replay == summary
    assert calls["catalog"] == 0


def _observe_window(activity, operation_id, program_id):
    return activity.run(
        "observe", {"address": 0x001000, "size": 0x40, "label": operation_id},
        program={"program_id": program_id}, operation_id=operation_id,
    )


def _related_activity(tmp_path, monkeypatch):
    activity, calls, memory = _activity(tmp_path, monkeypatch)
    entity = FakeEntity(tmp_path, {"program-1": _program(["catalog", "observe", "relate"])})
    activity.attach(entity)
    memory[0x001004:0x001008] = b"\x39\x05\x00\x00"
    memory[0x001024:0x001028] = b"\x07\x00\x00\x00"
    _observe_window(activity, "obs-before", "program-1")
    memory[0x001004] = 0x40
    memory[0x001024] = 0x08
    _observe_window(activity, "obs-after", "program-1")
    return activity, calls, entity


def test_relate_ranks_functions_with_call_neighborhood(tmp_path, monkeypatch):
    activity, calls, entity = _related_activity(tmp_path, monkeypatch)
    before_id = _identity("obs-before")
    after_id = _identity("obs-after")
    summary = activity.run(
        "relate",
        {"before": before_id, "after": after_id, "label": "health write"},
        program={"program_id": "program-1"},
        operation_id="relate-1",
    )
    assert summary["status"] == "COMPLETE"
    assert summary["before"]["observation_id"] == before_id
    assert summary["after"]["sha256"] != summary["before"]["sha256"]
    changes = summary["changes"]
    assert changes["changed_range_count"] == 2
    assert {(span["start"], span["end"]) for span in changes["changed_ranges"]} == {
        (0x001004, 0x001005), (0x001024, 0x001025),
    }
    names = [row["name"] for row in summary["function_evidence"]]
    assert set(names) == {"Foo", "Bar"}
    for row in summary["function_evidence"]:
        assert row["changed_bytes"] == 1
        assert row["call_neighborhood"] == 1
        assert row["address"] in {"0x00001000", "0x00001020"}
    assert summary["function_evidence"] == sorted(
        summary["function_evidence"],
        key=lambda row: (-row["changed_bytes"], -row["call_neighborhood"], row["name"], row["address"]),
    )
    assert summary["references"] == []
    published = [row for row in [entity.received]]
    assert published and published[0]["kind"] == "hosted-activity"
    payload = published[0]["payload"]
    assert payload["activity_id"] == "pcsx2" and payload["operation"] == "relate"
    assert payload["result"]["label"] == "health write"

def test_relate_maps_changed_data_back_to_referencing_function(tmp_path, monkeypatch):
    activity, _calls, memory = _activity(tmp_path, monkeypatch)
    entity = FakeEntity(
        tmp_path,
        {"program-1": _program(["observe", "relate"])},
    )
    activity.attach(entity)
    activity.run(
        "observe", {"address": 0x002000, "size": 0x40, "label": "before"},
        program={"program_id": "program-1"}, operation_id="data-before",
    )
    memory[0x002008] = 1
    activity.run(
        "observe", {"address": 0x002000, "size": 0x40, "label": "after"},
        program={"program_id": "program-1"}, operation_id="data-after",
    )
    summary = activity.run(
        "relate",
        {
            "before": _identity("data-before"),
            "after": _identity("data-after"),
            "label": "referenced game state",
        },
        program={"program_id": "program-1"}, operation_id="data-relation",
    )
    assert summary["function_evidence"][0]["changed_bytes"] == 0
    assert summary["function_evidence"][0]["name"] == "Foo"
    assert summary["function_evidence"][0]["reference_hits"] == 1
    assert summary["references"][0]["to_address"] == 0x002008
    assert summary["function_evidence"][0]["observation_base_hits"] == 0
    assert summary["references"][0]["relation_match"] == "changed-byte"


def test_relate_excludes_a_merely_nearby_data_reference(tmp_path, monkeypatch):
    references = {
        0x002004: ({
            "kind": "data",
            "access": "address",
            "width": 0,
            "from_address": 0x001004,
            "to_address": 0x002004,
            "disasm": "addiu $a0, $a0, 0x2004",
        },),
    }
    activity, _calls, memory = _activity(
        tmp_path, monkeypatch, references=references,
    )
    activity.attach(FakeEntity(
        tmp_path, {"program-1": _program(["observe", "relate"])},
    ))
    activity.run(
        "observe", {"address": 0x002000, "size": 0x40, "label": "before"},
        program={"program_id": "program-1"}, operation_id="near-before",
    )
    memory[0x002008] = 1
    activity.run(
        "observe", {"address": 0x002000, "size": 0x40, "label": "after"},
        program={"program_id": "program-1"}, operation_id="near-after",
    )
    summary = activity.run(
        "relate",
        {
            "before": _identity("near-before"),
            "after": _identity("near-after"),
            "label": "nearby state",
        },
        program={"program_id": "program-1"}, operation_id="near-relation",
    )
    assert summary["function_evidence"] == []
    assert summary["references"] == []
    assert summary["pnach_candidate"] is None


def test_relate_labels_an_observation_base_pointer_as_a_hypothesis(tmp_path, monkeypatch):
    references = {
        0x002000: ({
            "kind": "data",
            "access": "address",
            "width": 0,
            "from_address": 0x001004,
            "to_address": 0x002000,
            "disasm": "addiu $a0, $a0, 0x2000",
        },),
    }
    activity, _calls, memory = _activity(
        tmp_path, monkeypatch, references=references,
    )
    activity.attach(FakeEntity(
        tmp_path, {"program-1": _program(["observe", "relate"])},
    ))
    activity.run(
        "observe", {"address": 0x002000, "size": 0x40, "label": "before"},
        program={"program_id": "program-1"}, operation_id="base-before",
    )
    memory[0x002008] = 1
    activity.run(
        "observe", {"address": 0x002000, "size": 0x40, "label": "after"},
        program={"program_id": "program-1"}, operation_id="base-after",
    )
    summary = activity.run(
        "relate",
        {
            "before": _identity("base-before"),
            "after": _identity("base-after"),
            "label": "object state",
        },
        program={"program_id": "program-1"}, operation_id="base-relation",
    )
    evidence = summary["function_evidence"][0]
    assert evidence["name"] == "Foo"
    assert evidence["reference_hits"] == 0
    assert evidence["observation_base_hits"] == 1
    assert summary["references"][0]["relation_match"] == "observation-base"

def test_decompile_receives_exact_data_reference_relation(tmp_path, monkeypatch):
    activity, _calls, memory = _activity(tmp_path, monkeypatch)
    brain = FakeBrain(content=json.dumps({
        "pseudocode": "void Foo(void) { update_state(); }",
        "behavioral_hypothesis": "Foo accesses the changed game-state address",
        "uncertainty": "the access direction remains unresolved",
        "evidence": ["e1"],
    }))
    entity = FakeEntity(
        tmp_path,
        {"program-1": _program(["observe", "relate", "decompile"])},
        brain=brain,
    )
    activity.attach(entity)
    activity.run(
        "observe", {"address": 0x002000, "size": 0x40, "label": "before"},
        program={"program_id": "program-1"}, operation_id="linked-before",
    )
    memory[0x002008] = 1
    activity.run(
        "observe", {"address": 0x002000, "size": 0x40, "label": "after"},
        program={"program_id": "program-1"}, operation_id="linked-after",
    )
    activity.run(
        "relate",
        {
            "before": _identity("linked-before"),
            "after": _identity("linked-after"),
            "label": "linked state",
        },
        program={"program_id": "program-1"}, operation_id="linked-relation",
    )
    activity.run(
        "decompile", {"address": 0x001000, "question": "what touches linked state?"},
        program={"program_id": "program-1"}, operation_id="linked-decompile",
    )
    prompt = brain.requests[0]["prompt"]
    assert "reference_hits=1" in prompt
    assert "0x00001004->0x00002008" in prompt
    assert "addiu $a0, $a0, 0x2008" in prompt
    assert "changed ranges: 0x00002008-0x00002009" in prompt


def test_pnach_candidate_is_deterministic_inactive_and_outside_pcsx2(tmp_path, monkeypatch):
    activity, calls, _ = _related_activity(tmp_path, monkeypatch)
    summary = activity.run(
        "relate",
        {"before": _identity("obs-before"), "after": _identity("obs-after"),
         "label": "health write"},
        program={"program_id": "program-1"}, operation_id="relate-1",
    )
    candidate = summary["pnach_candidate"]
    assert candidate["filename"] == "SLUS-20111_1A2B3C4D.pnach"
    immutable = Path(candidate["path"])
    latest = Path(candidate["latest_path"])
    body = immutable.read_text(encoding="utf-8")
    assert latest.read_bytes() == immutable.read_bytes()
    assert candidate["sha256"] == hashlib.sha256(immutable.read_bytes()).hexdigest()
    assert candidate["original_words"] == ["00000000", "00000007"]
    assert candidate["stub_address"] in {"0x00001000", "0x00001020"}
    stub = int(candidate["stub_address"], 16)
    assert f"//patch=1,EE,{stub:08X},word,03E00008" in body
    assert f"//patch=1,EE,{stub + 4:08X},word,00000000" in body
    assert "original words" in body
    for line in body.splitlines():
        if "patch=" in line:
            assert line.lstrip().startswith("//")
    assert "pcsx2" not in str(latest).lower() or str(latest).startswith(
        str(activity.data_home)
    )
    assert not any(part in ("cheats", "patches") for part in latest.parts)
    second = activity.run(
        "relate",
        {"before": _identity("obs-before"), "after": _identity("obs-after"),
         "label": "mana write"},
        program={"program_id": "program-1"}, operation_id="relate-2",
    )
    second_candidate = second["pnach_candidate"]
    assert second_candidate["sha256"] != candidate["sha256"]
    assert hashlib.sha256(immutable.read_bytes()).hexdigest() == candidate["sha256"]
    assert (
        hashlib.sha256(Path(second_candidate["path"]).read_bytes()).hexdigest()
        == second_candidate["sha256"]
    )
    assert latest.read_bytes() == Path(second_candidate["path"]).read_bytes()


@pytest.mark.parametrize("identity", [
    {key: value for key, value in PINE_IDENTITY.items() if key != "game_uuid"},
    {**PINE_IDENTITY, "game_id": "SLUS-99999"},
    {**PINE_IDENTITY, "game_uuid": "DEADBEEF"},
    {**PINE_IDENTITY, "status": 1, "status_name": "paused"},
])
def test_observe_requires_matching_complete_game_identity(tmp_path, monkeypatch, identity):
    activity, _calls, _memory = _activity(tmp_path, monkeypatch, identity=identity)
    entity = FakeEntity(tmp_path, {"program-1": _program(["observe"])})
    activity.attach(entity)
    with pytest.raises(ActivityRefused, match="game identity|fixed ISO identity|running game"):
        _observe_window(activity, "wrong-game", "program-1")
    assert not (activity.data_home / "observations").exists()

def test_observe_refuses_a_game_switch_during_capture(tmp_path, monkeypatch):
    switched = {**PINE_IDENTITY, "game_id": "SLUS-99999", "game_uuid": "DEADBEEF"}
    activity, calls, _memory = _activity(
        tmp_path, monkeypatch, identity_sequence=(PINE_IDENTITY, switched),
    )
    activity.attach(FakeEntity(tmp_path, {"program-1": _program(["observe"])}))
    with pytest.raises(ActivityRefused, match="fixed ISO identity|changed during"):
        _observe_window(activity, "switched-game", "program-1")
    assert calls["identities"] == 2
    assert not (activity.data_home / "observations").exists()


def test_relate_validates_observations_strictly(tmp_path, monkeypatch):
    activity, calls, _ = _related_activity(tmp_path, monkeypatch)
    before_id = _identity("obs-before")
    with pytest.raises(ActivityRefused):
        activity.run(
            "relate",
            {"before": before_id, "after": before_id, "label": "same"},
            program={"program_id": "program-1"}, operation_id="relate-same",
        )
    with pytest.raises(ActivityRefused):
        activity.run(
            "relate",
            {"before": before_id, "after": _identity("obs-unknown"), "label": "gone"},
            program={"program_id": "program-1"}, operation_id="relate-unknown",
        )
    metadata_path = activity.data_home / "observations" / f"{_identity('obs-after')}.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["iso_sha256"] = "0" * 64
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ActivityRefused):
        activity.run(
            "relate",
            {"before": before_id, "after": _identity("obs-after"), "label": "foreign"},
            program={"program_id": "program-1"}, operation_id="relate-foreign",
        )


def test_interpretation_context_supplies_attributed_remote_strings(tmp_path, monkeypatch):
    activity, _calls, _memory = _activity(tmp_path, monkeypatch)
    record = SimpleNamespace(
        address=0x001000,
        size=0x20,
        name="Foo",
        source="symbol",
        evidence={
            "instructions": [
                {"address": 0x001000, "word": 0x03E00008, "text": "jr $ra"},
            ],
            "strings": [
                {"address": 0x00420000, "value": "REMOTE_MENU_LABEL"},
            ],
        },
    )
    atlas = SimpleNamespace(
        callers_of=lambda _address: (),
        callees_of=lambda _address: (),
        strings_near=lambda _address, span=64: (),
    )
    context = activity._interpretation_context(atlas, record, [])
    string_id = next(
        evidence_id
        for evidence_id, text in context["evidence"].items()
        if "REMOTE_MENU_LABEL" in text
    )
    prompt, supplied = activity._interpretation_prompt(record, context, "what does it label?")
    assert (
        f"[{string_id}] referenced string at 0x00420000: REMOTE_MENU_LABEL"
        in prompt
    )
    assert string_id in supplied


def test_decompile_asks_resident_brain_and_persists_evidence(tmp_path, monkeypatch):
    activity, calls, entity = _related_activity(tmp_path, monkeypatch)
    activity.run(
        "relate",
        {"before": _identity("obs-before"), "after": _identity("obs-after"),
         "label": "health write"},
        program={"program_id": "program-1"}, operation_id="relate-1",
    )
    relation_receipt = activity.data_home / "operations" / _identity("relate-1") / "receipt.json"
    foreign = json.loads(relation_receipt.read_text(encoding="utf-8"))
    foreign["label"] = "foreign game evidence"
    foreign["atlas_identity"]["elf_sha256"] = "f" * 64
    foreign_path = activity.data_home / "operations" / "0000-foreign" / "receipt.json"
    foreign_path.parent.mkdir(parents=True)
    foreign_path.write_text(json.dumps(foreign), encoding="utf-8")
    for index in range(260):
        unrelated = activity.data_home / "operations" / f"0000-unrelated-{index:03d}" / "receipt.json"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text('{"status":"COMPLETE"}', encoding="utf-8")
    brain = FakeBrain(content=json.dumps({
        "pseudocode": "void Foo() { Bar(); }",
        "behavioral_hypothesis": "Foo forwards into Bar",
        "uncertainty": "only two functions and one call edge are known",
        "evidence": ["e1", "e3"],
    }))
    program = _program(["catalog", "observe", "relate", "decompile"])
    scoped = FakeEntity(tmp_path, {"program-1": program}, brain=brain)
    activity.attach(scoped)
    summary = activity.run(
        "decompile", {"address": 0x00001000, "question": "what writes health?"},
        program={"program_id": "program-1"}, operation_id="dc-1",
    )
    assert summary["status"] == "COMPLETE"
    assert summary["function"]["address"] == "0x00001000"
    assert summary["question"] == "what writes health?"
    interpretation = summary["interpretation"]
    assert interpretation["pseudocode"] == "void Foo() { Bar(); }"
    assert interpretation["behavioral_hypothesis"] == "Foo forwards into Bar"
    assert interpretation["evidence"] == ["e1", "e3"]
    artifact = summary["artifact"]
    assert Path(artifact["path"]).is_file()
    assert artifact["sha256"] == hashlib.sha256(Path(artifact["path"]).read_bytes()).hexdigest()
    assert len(brain.requests) == 1
    assert brain.requests[0]["max_tokens"] == 1_536
    prompt = brain.requests[0]["prompt"]
    assert "atlas function Foo at 0x00001000" in prompt
    assert "disassembly: 0x00001000: jr $ra" in prompt
    assert "function body sha256: " in prompt
    assert "Prior relation evidence" in prompt and "health write" in prompt
    assert "what writes health?" in prompt
    assert "foreign game evidence" not in prompt
    received = scoped.received
    assert received["kind"] == "hosted-activity"
    assert received["payload"]["operation"] == "decompile"
    assert received["payload"]["result"]["interpretation"]["pseudocode"].startswith("void Foo")

    replay = activity.run(
        "decompile", {"address": 0x00001000, "question": "what writes health?"},
        program={"program_id": "program-1"}, operation_id="dc-1",
    )
    assert replay == summary
    assert len(brain.requests) == 1

def test_interpretation_prompt_keeps_relation_and_contract_when_bounded(tmp_path, monkeypatch):
    activity, _calls, _memory = _activity(tmp_path, monkeypatch)
    evidence = {
        "e1": "atlas function Foo at 0x00001000",
        "e2": "Prior relation evidence: " + ("state " * 120),
        **{
            f"e{index + 3}": f"disassembly: 0x{index:08X}: " + ("instruction " * 30)
            for index in range(64)
        },
        "e67": "callers: 0x00002000",
    }
    prompt, supplied = activity._interpretation_prompt(
        _FOO, {"evidence": evidence}, "what changed?",
    )
    assert len(prompt) <= 8_000
    assert "[e2] Prior relation evidence" in prompt
    assert "[e67] callers: 0x00002000" in prompt
    assert "Return JSON with exactly the keys" in prompt
    rendered_ids = [
        line[1:line.index("] ")]
        for line in prompt.splitlines()
        if line.startswith("[") and "] " in line
        and line[1:line.index("] ")] in evidence
    ]
    assert supplied == rendered_ids
    omitted = set(evidence) - set(supplied)
    assert omitted
    artifact = activity._persist_interpretation(
        "bounded-evidence-artifact",
        _FOO,
        {"evidence": evidence},
        [{"label": "source relation", "receipt": "receipt.json"}],
        "what changed?",
        supplied,
        {
            "pseudocode": "return;",
            "behavioral_hypothesis": "",
            "uncertainty": "",
            "evidence": [],
        },
    )
    artifact_body = json.loads(Path(artifact["path"]).read_text(encoding="utf-8"))
    assert set(artifact_body["supplied_evidence"]) == set(supplied)
    assert omitted.isdisjoint(artifact_body["supplied_evidence"])
    assert artifact_body["source_relations"] == [
        {"label": "source relation", "receipt": "receipt.json"},
    ]

def test_decompile_refuses_a_truncated_brain_interpretation(tmp_path, monkeypatch):
    activity, _calls, _memory = _activity(tmp_path, monkeypatch)
    entity = FakeEntity(
        tmp_path,
        {"program-1": _program(["decompile"])},
        brain=FakeBrain(content='{"pseudocode":"partial', finish_reason="length"),
    )
    activity.attach(entity)
    with pytest.raises(ActivityRefused, match="generation bound"):
        activity.run(
            "decompile", {"address": 0x001000},
            program={"program_id": "program-1"}, operation_id="truncated-decompile",
        )


def test_decompile_parses_unstructured_brain_text(tmp_path, monkeypatch):
    activity, calls, _ = _activity(tmp_path, monkeypatch)
    brain = FakeBrain(content="int Foo(void) { return 1; } // raw guess")
    activity.attach(FakeEntity(tmp_path, {"program-1": _program(["decompile"])}, brain=brain))
    summary = activity.run("decompile", {"address": 0x001000},
                           program={"program_id": "program-1"}, operation_id="dc-raw")
    assert summary["interpretation"]["pseudocode"].startswith("int Foo(void)")
    assert summary["interpretation"]["evidence"] == []
    assert "unstructured text" in summary["interpretation"]["uncertainty"]


def test_decompile_rejects_unknown_citations_and_addresses(tmp_path, monkeypatch):
    activity, calls, _ = _activity(tmp_path, monkeypatch)
    brain = FakeBrain(content=json.dumps({
        "pseudocode": "x", "behavioral_hypothesis": "y", "uncertainty": "z",
        "evidence": ["e999"],
    }))
    activity.attach(FakeEntity(tmp_path, {"program-1": _program(["decompile"])}, brain=brain))
    with pytest.raises(ActivityRefused, match="outside the supplied ids"):
        activity.run("decompile", {"address": 0x00001000},
                     program={"program_id": "program-1"}, operation_id="dc-cite")
    with pytest.raises(ActivityRefused, match="exact atlas function"):
        activity.run("decompile", {"address": 0x00009999},
                     program={"program_id": "program-1"}, operation_id="dc-unknown")


def test_unimportable_package_refuses_operations(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "pcsx2", None)
    iso = tmp_path / "game.iso"
    iso.write_bytes(b"ISO")
    home = tmp_path / "home"
    home.mkdir()
    activity = PCSX2Activity(iso_path=iso, data_home=home)
    activity.attach(FakeEntity(tmp_path, {"program-1": _program(["catalog"])}))
    with pytest.raises(ActivityRefused, match="not importable"):
        activity.run("catalog", {}, program={"program_id": "program-1"},
                     operation_id="cat-missing")


def test_field_play_is_authorized_bounded_and_parameter_closed(tmp_path, monkeypatch):
    activity, _, _ = _activity(tmp_path, monkeypatch)
    described = activity.describe()
    assert "field-play" in described["operations"]
    assert described["native_field"]["max_play_steps"] == 64
    assert described["native_field"]["max_play_timeout_seconds"] == 600
    assert "field-play" in described["effect"]
    entity = FakeEntity(tmp_path, {"program-1": _program(["field-observe"])})
    activity.attach(entity)
    # A play programme operation is gated by the programme scope, exactly as the
    # single-step field operations are.
    with pytest.raises(ActivityRefused, match="does not authorize"):
        activity.run("field-play", {"steps": 2},
                     program={"program_id": "program-1"}, operation_id="play-scope")
    activity.attach(FakeEntity(tmp_path, {"program-1": _program(["field-play"])}))
    for parameters, message in (
        ({"steps": 0}, "step count"),
        ({"steps": 65}, "step count"),
        ({"steps": 2.5}, "step count"),
        ({"steps": 2, "samples": 4, "duration": 3}, "accepts only"),
        # A play session's fence scales with its step budget, one minute each.
        ({"steps": 2, "timeout_seconds": 121}, "0..120 seconds"),
        ({"steps": 8, "timeout_seconds": 601}, "0..480 seconds"),
    ):
        with pytest.raises(ActivityRefused, match=message):
            activity.run("field-play", parameters,
                         program={"program_id": "program-1"}, operation_id="play-bounds")
