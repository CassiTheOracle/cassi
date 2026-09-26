import pytest

from pcsx2 import (
    GameplayFocusLost,
    GameplayInputError,
    XInputSource,
    meaningful_transitions,
)


_BUTTONS = (
    (0x0001, "dpad_up"),
    (0x0002, "dpad_down"),
    (0x0004, "dpad_left"),
    (0x0008, "dpad_right"),
    (0x0010, "start"),
    (0x0020, "back"),
    (0x0040, "left_thumb"),
    (0x0080, "right_thumb"),
    (0x0100, "left_shoulder"),
    (0x0200, "right_shoulder"),
    (0x1000, "a"),
    (0x2000, "b"),
    (0x4000, "x"),
    (0x8000, "y"),
)


def raw_state(**updates):
    state = {
        "packet_number": 7,
        "buttons": 0,
        "left_trigger": 0,
        "right_trigger": 0,
        "left_stick_x": 0,
        "left_stick_y": 0,
        "right_stick_x": 0,
        "right_stick_y": 0,
    }
    state.update(updates)
    return state


def state(buttons=0, **updates):
    raw = raw_state(buttons=buttons, **updates)
    raw["pressed"] = [name for mask, name in _BUTTONS if buttons & mask]
    return raw


class FakeAPI:
    def __init__(self, focuses=(), reads=(), listener_pids=(4812,)):
        self.focuses = list(focuses)
        self.reads = list(reads)
        self.listener_pids = listener_pids
        self.current_focus = self.focuses[0] if self.focuses else None
        self.events = []

    def foreground_process(self):
        self.events.append("focus")
        if self.focuses:
            self.current_focus = self.focuses.pop(0)
        return self.current_focus

    def read_xinput(self, slot):
        self.events.append(("poll", slot))
        result = self.reads.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def tcp_listener_pids(self, port):
        self.events.append(("listeners", port))
        if isinstance(self.listener_pids, Exception):
            raise self.listener_pids
        return self.listener_pids


def focused(pid=4812, name="pcsx2-qt.exe"):
    return name, pid


def test_sample_decodes_ranges_and_orders_pressed_buttons():
    buttons = 0x0002 | 0x0100 | 0x1000 | 0x8000
    api = FakeAPI(
        focuses=[focused(), focused(), focused()],
        reads=[raw_state(
            packet_number=0xFFFFFFFF,
            buttons=buttons,
            left_trigger=255,
            right_trigger=16,
            left_stick_x=-32768,
            left_stick_y=32767,
            right_stick_x=-1,
            right_stick_y=1,
        )],
    )
    source = XInputSource(slot=2, api=api)
    identity = source.begin_session()
    result = source.sample()

    assert identity == {
        "backend": "windows-xinput",
        "slot": 2,
        "process": "pcsx2-qt.exe",
        "pid": 4812,
    }
    assert result == {
        "packet_number": 0xFFFFFFFF,
        "buttons": buttons,
        "pressed": ["dpad_down", "left_shoulder", "a", "y"],
        "left_trigger": 255,
        "right_trigger": 16,
        "left_stick_x": -32768,
        "left_stick_y": 32767,
        "right_stick_x": -1,
        "right_stick_y": 1,
    }
    assert api.events == ["focus", "focus", ("poll", 2), "focus"]


def test_sample_never_polls_when_foreground_process_is_not_bound_pid():
    api = FakeAPI(
        focuses=[focused(), ("pcsx2-qt.exe", 9901)],
        reads=[raw_state()],
    )
    source = XInputSource(api=api)
    source.begin_session()

    with pytest.raises(GameplayFocusLost):
        source.sample()

    assert api.events == ["focus", "focus"]
    assert len(api.reads) == 1


def test_pid_switch_after_poll_discards_state():
    api = FakeAPI(
        focuses=[focused(), focused(), ("pcsx2-qt.exe", 9901)],
        reads=[raw_state(buttons=0x1000)],
    )
    source = XInputSource(api=api)
    source.begin_session()

    with pytest.raises(GameplayFocusLost):
        source.sample()

    assert api.events == ["focus", "focus", ("poll", 0), "focus"]
    assert source.describe()["pid"] == 4812


def test_process_name_switch_after_poll_discards_state():
    api = FakeAPI(
        focuses=[focused(), focused(), ("other.exe", 4812)],
        reads=[raw_state(buttons=0x1000)],
    )
    source = XInputSource(api=api)
    source.begin_session()

    with pytest.raises(GameplayFocusLost):
        source.sample()

    assert api.events == ["focus", "focus", ("poll", 0), "focus"]

@pytest.mark.parametrize(
    "field,value",
    [
        ("packet_number", -1),
        ("packet_number", 0x1_0000_0000),
        ("buttons", 0x1_0000),
        ("left_trigger", 256),
        ("right_trigger", -1),
        ("left_stick_x", -32769),
        ("left_stick_y", 32768),
        ("right_stick_x", True),
        ("right_stick_y", True),
        ("missing", "right_stick_y"),
    ],
)
def test_malformed_or_disconnected_poll_fails_after_focus_fence(field, value):
    raw = raw_state()
    if field == "missing":
        del raw[value]
    else:
        raw[field] = value
    api = FakeAPI(
        focuses=[focused(), focused(), focused()],
        reads=[raw],
    )
    source = XInputSource(api=api)
    source.begin_session()

    with pytest.raises(GameplayInputError):
        source.sample()

    assert api.events == ["focus", "focus", ("poll", 0), "focus"]


def test_disconnected_controller_is_fenced_and_rejected():
    api = FakeAPI(
        focuses=[focused(), focused(), focused()],
        reads=[None],
    )
    source = XInputSource(api=api)
    source.begin_session()

    with pytest.raises(GameplayInputError, match="disconnected"):
        source.sample()

    assert api.events == ["focus", "focus", ("poll", 0), "focus"]


def test_lifecycle_binds_once_and_end_clears_pid():
    api = FakeAPI(focuses=[focused(), focused()])
    source = XInputSource(api=api)

    assert source.describe() == {
        "backend": "windows-xinput",
        "process": "pcsx2-qt.exe",
        "slot": 0,
        "pid": None,
    }
    with pytest.raises(GameplayInputError, match="No XInput session"):
        source.sample()
    identity = source.begin_session()
    assert identity["pid"] == 4812
    with pytest.raises(GameplayInputError, match="already active"):
        source.begin_session()
    source.assert_foreground()
    source.end_session()
    source.end_session()
    assert source.describe()["pid"] is None
    with pytest.raises(GameplayInputError, match="No XInput session"):
        source.sample()
    with pytest.raises(GameplayInputError, match="No XInput session"):
        source.assert_foreground()


def test_begin_session_rejects_wrong_process_without_polling():
    api = FakeAPI(focuses=[("other.exe", 4812)])
    source = XInputSource(api=api)

    with pytest.raises(GameplayFocusLost):
        source.begin_session()

    assert api.events == ["focus"]
    assert source.describe()["pid"] is None


def test_constructor_bounds_slot_and_process_basename():
    for slot in (-1, 4, True):
        with pytest.raises(ValueError):
            XInputSource(slot=slot, api=FakeAPI())
    for process in ("", "C:\\Games\\pcsx2-qt.exe", "x" * 256, "bad\0name"):
        with pytest.raises(ValueError):
            XInputSource(expected_process=process, api=FakeAPI())


def test_pine_endpoint_requires_loopback_listener_owned_by_bound_pid():
    api = FakeAPI(focuses=[focused(), focused(), focused()])
    source = XInputSource(api=api)
    source.begin_session()

    source.assert_pine_endpoint("127.0.0.1", 28011)

    assert api.events == ["focus", "focus", ("listeners", 28011), "focus"]


@pytest.mark.parametrize(
    "host,owners,error",
    [
        ("192.0.2.1", (4812,), "IPv4 loopback"),
        ("localhost", (4812,), "IPv4 loopback"),
        ("127.0.0.1", (), "not owned"),
        ("127.0.0.1", (9901,), "not owned"),
        ("127.0.0.1", (4812, 9901), "not owned"),
    ],
)
def test_pine_endpoint_refuses_unverifiable_or_different_owner(host, owners, error):
    api = FakeAPI(
        focuses=[focused(), focused(), focused()],
        listener_pids=owners,
    )
    source = XInputSource(api=api)
    source.begin_session()

    with pytest.raises(GameplayInputError, match=error):
        source.assert_pine_endpoint(host, 28011)


def test_meaningful_transitions_orders_edges_then_quantized_analog_changes():
    previous = state(
        buttons=0x1000 | 0x0001,
        left_trigger=15,
        right_trigger=10,
        left_stick_x=4095,
        left_stick_y=-4097,
    )
    current = state(
        buttons=0x1000 | 0x0002,
        left_trigger=16,
        right_trigger=15,
        left_stick_x=4096,
        left_stick_y=-4096,
    )

    assert meaningful_transitions(None, current) == []
    assert meaningful_transitions(previous, None) == []
    assert meaningful_transitions(previous, current) == [
        {"control": "dpad_up", "kind": "release", "previous": 1, "current": 0},
        {"control": "dpad_down", "kind": "press", "previous": 0, "current": 1},
        {"control": "left_trigger", "kind": "change", "previous": 15, "current": 16},
        {"control": "left_stick_x", "kind": "change", "previous": 4095, "current": 4096},
        {"control": "left_stick_y", "kind": "change", "previous": -4097, "current": -4096},
    ]


def test_analog_jitter_inside_same_bin_does_not_create_transition():
    previous = state(left_trigger=0, right_trigger=31, left_stick_x=-1, right_stick_y=4095)
    current = state(left_trigger=15, right_trigger=16, left_stick_x=-4096, right_stick_y=0)

    assert meaningful_transitions(previous, current) == []
