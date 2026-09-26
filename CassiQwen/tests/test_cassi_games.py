"""The game seam: perception, vocabulary, and the decision contract.

These are the parts of a game's world that break silently — a screen that is
read before it is drawn, a status line parsed from the wrong row, a decision
parsed one step too literally.  NetHack itself is not started here; the seam is
driven with the frames a real life actually produced.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence

import numpy as np

from games import Action, Observation, available_games, create_world, register_world
from games.fieldmemory import EQUILIBRIUM, INTENTS, WALKED_COST, DungeonField, LevelField
from games.livingmemory import (
    DEFAULT_PRIORITY,
    NO_MEMORY,
    SEEK_LIMIT,
    Asking,
    standing_of,
    OFFER_LIMIT,
    GameMemory,
    Lesson,
    Memories,
    Recollection,
    Situation,
    _lesson_text,
    briefing_prompt,
    standing_of,
)
from games.nethack import NetHackWorld
from run_cassi_game import (
    ask_the_field,
    campaign_line,
    campaign_row,
    life_label,
    longest_stall,
)
from games.player import (
    BrainPlayer,
    BrainRequiredError,
    ReflectedLesson,
    ROUTE_REFUSALS_BEFORE_LOOK,
    ROUTE_STEPS_BEFORE_LOOK,
    ScriptedExplorer,
    _memory_number,
    _reflected_lessons,
    monsters_beside,
    route_wake,
)
from run_cassi_game import (
    close_life,
    hopeless_lessons,
    lesson_use,
    life_outcome,
    life_story,
    situation_context,
)
from games.screen import ScreenWorld
from games.terminal import ScreenFrame
from games.view import WatchView, render_screen
from games.world import WorldError

# A real 80x24 frame captured from a live life (runs/20260920-232329): a room
# with the pet, the stairs, the gold, and the two status lines NetHack draws.
LIVE_SCREEN: tuple[str, ...] = (
    "",
    "",
    "",
    "         ┌────────┐",
    "         │........+",
    "         │@...d..<│",
    "         │........│",
    "         │.......$.",
    "         │........│",
    "         └───────.┘",
    "", "", "", "", "", "", "", "", "", "", "", "",
    "Cassi the Stripling            St:18 Dx:11 Co:20 In:8 Wi:11 Ch:7 Lawful",
    "Dlvl:1 $:0 HP:18(18) Pw:1(1) AC:6 Xp:1/0",
)


def frame(lines: Sequence[str], revision: int = 1) -> ScreenFrame:
    return ScreenFrame(lines=tuple(lines), cursor=(0, 0), revision=revision, quiet=1.0)


class _FakeSession:
    """A terminal that shows whatever the test decides, and remembers keys."""

    def __init__(self, screens: Sequence[Sequence[str]]) -> None:
        self._screens = [tuple(screen) for screen in screens]
        self.sent: list[str] = []
        self.closed = False
        self._index = 0

    def frame(self) -> ScreenFrame:
        index = min(self._index, len(self._screens) - 1)
        return frame(self._screens[index], revision=self._index + 1)

    def send(self, keys: str, **_: Any) -> ScreenFrame:
        self.sent.append(keys)
        self._index += 1
        return self.frame()

    def close(self) -> None:
        self.closed = True

    def error(self) -> None:
        return None


class _StubWorld(ScreenWorld):
    """A screen world with no game behind it: the seam under test."""

    name = "stub"

    def __init__(self, screens: Sequence[Sequence[str]]) -> None:
        super().__init__()
        self._screens = [tuple(screen) for screen in screens]
        self.session = _FakeSession(self._screens)

    def reset(self) -> Observation:
        """A fresh life with a fake terminal instead of a process."""
        self.close()
        self.session = _FakeSession(self._screens)
        return self.observe()

    def vocabulary(self, screen: ScreenFrame) -> tuple[Action, ...]:
        return (
            Action(key="h", keys="h", label="move west"),
            Action(key="l", keys="l", label="move east"),
        )


def moved_screen(column: int) -> tuple[str, ...]:
    row = "".join("@" if index == column else "." for index in range(20))
    return (row, "", "Cassi the Stripling", "Dlvl:1 HP:1(1)")


class ScreenSeamTest(unittest.TestCase):
    def test_self_position_reports_movement(self) -> None:
        world = _StubWorld([moved_screen(5), moved_screen(6), moved_screen(6)])
        world.reset()
        first = world.act(Action(key="l", keys="l", label="move east"))
        self.assertIs(first.observation.summary.get("moved"), True)
        second = world.act(Action(key="l", keys="l", label="move east"))
        self.assertIs(second.observation.summary.get("moved"), False)
        self.assertEqual(second.note, "you did not move")
        world.close()

    def test_unknown_world_is_refused(self) -> None:
        self.assertIn("nethack", available_games())
        with self.assertRaises(WorldError):
            create_world("no-such-game")

    def test_a_registered_world_is_reachable_by_name(self) -> None:
        @register_world("test-stub")
        class _Registered(_StubWorld):
            pass

        self.assertIsInstance(create_world("test-stub", screens=[()]), _Registered)


class NetHackReadingTest(unittest.TestCase):
    def test_status_lines_are_read_from_a_real_frame(self) -> None:
        summary = NetHackWorld._status(frame(LIVE_SCREEN))
        self.assertEqual(summary["depth"], 1)
        self.assertEqual(summary["hp"], 18)
        self.assertEqual(summary["hp_max"], 18)
        self.assertEqual(summary["armor"], 6)
        self.assertEqual(summary["character"], "Cassi the Stripling")
        self.assertEqual(summary["alignment"], "Lawful")
        self.assertEqual(summary["stats"]["St"], 18)

    def test_a_story_screen_is_not_playable_and_a_map_is(self) -> None:
        story = list(LIVE_SCREEN)
        story[3] = "It is written in the Book of Tyr:"
        self.assertFalse(NetHackWorld._playable(frame(story)))
        self.assertTrue(NetHackWorld._playable(frame(LIVE_SCREEN)))
        self.assertFalse(NetHackWorld._playable(frame(["--More--", "@", "Dlvl:1"])))

    def test_the_vocabulary_is_the_games_own_verbs(self) -> None:
        world = NetHackWorld(program="nethack.exe", write_config=False)
        actions = world.vocabulary(frame(LIVE_SCREEN))
        keys = {action.key for action in actions}
        self.assertTrue({"h", "j", "k", "l", "y", "u", "b", "n"} <= keys)
        self.assertTrue({".", "s", ",", ">", "<"} <= keys)
        self.assertNotIn("5", keys)  # movement is the letters, never the keypad
        self.assertEqual(len(keys), len(actions))
        world.close()

    def test_a_more_prompt_offers_reading_on(self) -> None:
        world = NetHackWorld(program="nethack.exe", write_config=False)
        pager = list(LIVE_SCREEN)
        pager[0] = "--More--"
        actions = world.vocabulary(frame(pager))
        self.assertEqual([action.key for action in actions], ["continue", "stop-reading"])

    def test_a_death_is_read_from_the_screen(self) -> None:
        world = NetHackWorld(program="nethack.exe", write_config=False)
        tomb = list(LIVE_SCREEN)
        tomb[0] = "You die..."
        tomb[3] = "DYWYPI --More--"
        tomb[4] = "Do you want your possessions identified? [ynq]"
        reading = world.read(frame(tomb))
        self.assertTrue(reading["done"])
        self.assertEqual(reading["prompt"], "[ynq]")
        self.assertFalse(world.read(frame(LIVE_SCREEN)).get("done", False))

    def test_a_direction_prompt_offers_only_directions(self) -> None:
        world = NetHackWorld(program="nethack.exe", write_config=False)
        asking = list(LIVE_SCREEN)
        asking[0] = "In what direction?"
        actions = world.vocabulary(frame(asking))
        self.assertEqual(
            [action.key for action in actions],
            ["k", "j", "h", "l", "y", "u", "b", "n"],
        )
        self.assertEqual(world._prompt(frame(asking), "In what direction?"), "In what direction?")
        self.assertIsNone(world._prompt(frame(LIVE_SCREEN), ""))


class PlayerAnswerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.actions = (
            Action(key="h", keys="h", label="move west"),
            Action(key="j", keys="j", label="move south"),
            Action(key=">", keys=">", label="go down the stairs (only works standing on '>')"),
        )

    def resolve(self, parsed: dict[str, Any]) -> Action | None:
        return BrainPlayer._resolve(parsed, self.actions)

    def test_a_key_is_taken_literally(self) -> None:
        self.assertEqual(self.resolve({"action": "j"}).key, "j")  # type: ignore[union-attr]

    def test_a_named_action_is_understood(self) -> None:
        self.assertEqual(self.resolve({"action": "move west"}).key, "h")  # type: ignore[union-attr]
        self.assertEqual(self.resolve({"action": "move", "direction": "west"}).key, "h")  # type: ignore[union-attr]
        self.assertEqual(self.resolve({"action": "west"}).key, "h")  # type: ignore[union-attr]

    def test_an_invented_action_is_refused(self) -> None:
        self.assertIsNone(self.resolve({"action": "dance"}))
        self.assertIsNone(self.resolve({"action": "move"}))

    def test_a_fenced_json_reply_is_parsed(self) -> None:
        parsed = BrainPlayer._parse('Sure.\n```json\n{"action": "h", "reason": "west"}\n```')
        self.assertEqual(parsed, {"action": "h", "reason": "west"})
        self.assertIsNone(BrainPlayer._parse("no json here"))

    def test_the_scripted_walker_answers_a_menu(self) -> None:
        observation = Observation(
            screen=LIVE_SCREEN,
            summary={},
            events=(),
            prompt="[yn]",
            done=False,
            score=0.0,
            turn=1,
        )
        decision = ScriptedExplorer().decide(
            observation=observation,
            actions=(Action(key="yes", keys="y", label="answer yes"), Action(key="no", keys="n", label="answer no")),
            recent=(),
        )
        self.assertEqual(decision.action.key, "no")
        self.assertEqual(decision.source, "scripted")


class _ScriptedBrain(BrainPlayer):
    """The brain, with a fixed list of answers instead of a model."""

    def __init__(
        self,
        answers: Sequence[tuple[str, str]],
        used: Sequence[int] = (),
        wants: Sequence[str] = (),
    ) -> None:
        super().__init__(url="http://unused")
        self._answers = list(answers)
        self._used = list(used)
        self._wants = list(wants)
        self.asked: list[str] = []
        self.remembered: list[str] = []

    def _ask(  # type: ignore[override]
        self, *, observation, actions, recent, nudge="", memory="", remembered=""
    ):
        self.asked.append(nudge or memory)
        self.remembered.append(remembered)
        key, reason = self._answers.pop(0)
        used = self._used.pop(0) if self._used else 0
        want = self._wants.pop(0) if self._wants else ""
        chosen = BrainPlayer._resolve({"action": key}, actions)
        if chosen is None:
            return None, reason, f'"{key}" is not an available action', used, want
        return chosen, reason, "", used, want


class CampaignTest(unittest.TestCase):
    """A campaign reads its own lives back: depth, ending, stalling, lessons.

    The log is what makes an indefinite run legible -- a life per row, so a run
    that never descends and a run that keeps dying to the same thing both say so
    out loud instead of disappearing into a screen that is gone.
    """

    def receipt(self, **overrides: Any) -> dict:
        receipt: dict[str, Any] = {
            "final": {"done": True, "depth": 2, "hp": 0, "hp_max": 18, "message": "You die..."},
            "journal": [
                {"turn": 1, "depth": 1, "moved": True},
                {"turn": 2, "depth": 2, "moved": False},
                {"turn": 3, "depth": 2, "moved": False},
                {"turn": 4, "depth": 2, "moved": False},
                {"turn": 5, "depth": 2, "moved": True},
            ],
            "living": {
                "written": ["a locked door costs a turn, not a life"],
                "standing": {"games:nethack:lesson:abc": {"verdicts": 2, "priority": 0.6}},
                "verdicts": [{"source_id": "games:nethack:lesson:abc", "verdicts": 2}],
            },
            "started_at": "2026-09-22T09:00:00+00:00",
            "wall_seconds": 610.0,
            "receipt": "games/runs/campaign-smoke/life-0003/receipt.json",
        }
        receipt.update(overrides)
        return receipt

    def row(self, **overrides: Any) -> dict:
        return campaign_row(self.receipt(**overrides), 3, "campaign-smoke-L0003", 12_300_000)

    def test_a_row_keeps_the_life_that_happened(self) -> None:
        row = self.row()
        self.assertEqual(row["life"], 3)
        self.assertEqual(row["turns"], 5)
        self.assertEqual(row["depth"], 2)
        self.assertEqual(row["deepest"], 2)
        self.assertTrue(row["died"])
        self.assertEqual((row["hp"], row["hp_max"]), (0, 18))
        self.assertEqual(row["message"], "You die...")
        self.assertEqual(row["lessons"], ["a locked door costs a turn, not a life"])
        self.assertEqual(row["standing"]["games:nethack:lesson:abc"]["verdicts"], 2)
        self.assertEqual(row["home_bytes"], 12_300_000)
        self.assertEqual(row["receipt"], "games/runs/campaign-smoke/life-0003/receipt.json")

    def test_stalling_is_the_longest_run_of_not_moving(self) -> None:
        self.assertEqual(self.row()["stall"], 3)
        self.assertEqual(longest_stall([]), 0)
        self.assertEqual(
            longest_stall([{"moved": True}, {"moved": False}, {"moved": True}]), 1
        )

    def test_a_life_that_never_started_is_still_a_row(self) -> None:
        row = self.row(final={"done": False, "depth": None}, journal=[], living={})
        self.assertEqual(row["turns"], 0)
        self.assertIsNone(row["deepest"])
        self.assertFalse(row["died"])
        self.assertEqual(row["lessons"], [])

    def test_a_life_played_again_gets_a_label_of_its_own(self) -> None:
        """The field refuses a label that means two things, so a restart renames.

        This is not hypothetical: a campaign restarted after a kill replayed its
        first life under the same name, and the field rejected the second
        attempt -- "semantic operation identity changed request content".
        """
        first = life_label("campaign-1", 4, "090000")
        again = life_label("campaign-1", 4, "091500")
        self.assertNotEqual(first, again)
        self.assertTrue(first.startswith("campaign-1-L0004"), first)
        self.assertTrue(again.startswith("campaign-1-L0004"), again)
        self.assertEqual(life_label("campaign-1", 4, "090000"), first)

    def test_a_campaign_does_not_offer_a_way_to_quit_it(self) -> None:
        """`S` means save and stop: a give-up action in a life that runs until stopped.

        Measured in the field: one brain proposed saving 45 times in 341 turns,
        each proposal costing a turn to open the prompt and another to decline.
        """
        screen = frame(LIVE_SCREEN)
        plain = NetHackWorld(program="nethack.exe", write_config=False)
        campaign = NetHackWorld(
            program="nethack.exe", write_config=False, allow_save=False
        )
        ordinary = {action.key for action in plain.vocabulary(screen)}
        running = {action.key for action in campaign.vocabulary(screen)}
        self.assertIn("S", ordinary)              # a single run may still end this way
        self.assertNotIn("S", running)            # a campaign may not
        self.assertEqual(ordinary - {"S"}, running)  # nothing else was taken away
        self.assertIn(">", running)               # and the way down is still offered

    def test_a_win_is_not_a_death(self) -> None:
        """The campaign exists to answer one question, so the log has to tell it."""
        ascended = campaign_row(
            self.receipt(
                final={
                    "done": True, "depth": -5, "hp": 40, "hp_max": 40,
                    "message": "You have ascended almighty!",
                    "screen_tail": ["You have ascended", " to the status of Demigoddess"],
                }
            ),
            9, "campaign-smoke-L0009", 0,
        )
        self.assertTrue(ascended["won"])
        self.assertTrue(ascended["died"])          # the character's life is over
        self.assertIn("WON", campaign_line(ascended))
        # an ordinary death carries no win marker
        self.assertFalse(self.row()["won"])
        self.assertNotIn("WON", campaign_line(self.row()))

    def test_a_line_reads_like_a_life(self) -> None:
        line = campaign_line(self.row())
        self.assertIn("life   3", line)
        self.assertIn("deepest 2", line)
        self.assertIn("died", line)
        self.assertIn("turns 5", line)
        self.assertIn("10.2 min", line)
        self.assertIn("HP 0/18", line)
        self.assertIn("lessons 1", line)
        self.assertIn("earning 1", line)
        self.assertIn("stall 3", line)
        self.assertIn("12.3 MB", line)
        self.assertIn("You die...", line)
        stopped = campaign_line(self.row(final={"done": False, "depth": 1}, wall_seconds=59.0))
        self.assertIn("stopped", stopped)
        self.assertIn("1.0 min", stopped)


class StandingTest(unittest.TestCase):
    """A verdict counts for the memory it names, however the memory is named.

    The field files a lesson under its own identity and binds it under a binding
    id that carries that identity, so both spellings are the same memory -- and a
    caller that reads the whole autobiography view has to see the same verdicts
    as one that reads its episode list.
    """

    LESSON = "games:nethack:lesson:abc123"
    BINDING = "field-qwen:binding:games:nethack:lesson:abc123"

    def episode(self, ref_id: str, usefulness: float) -> dict:
        return {
            "use": {"payload": {"selected_refs": [{"id": ref_id, "kind": "Binding"}]}},
            "assessment": {"payload": {"usefulness": usefulness}},
        }

    def test_one_memory_counts_once_however_it_is_named(self) -> None:
        view = {
            "episodes": [
                self.episode(self.BINDING, 0.25),
                {"use": {"payload": {"selected_refs": []}}, "assessment": {"payload": {}}},
            ]
        }
        for identity in (self.LESSON, self.BINDING):
            by_list = standing_of(identity, view["episodes"])
            self.assertEqual(by_list["verdicts"], 1, identity)
            self.assertEqual(by_list["usefulness"], 0.25, identity)
            self.assertEqual(standing_of(identity, view), by_list, identity)

    def test_a_memory_no_verdict_names_is_heard_at_the_middle(self) -> None:
        view = {"episodes": [self.episode("games:nethack:lesson:other", 1.0)]}
        standing = standing_of(self.LESSON, view)
        self.assertEqual(standing["verdicts"], 0)
        self.assertEqual(standing["priority"], DEFAULT_PRIORITY)

    def test_an_unsettled_use_is_not_a_verdict(self) -> None:
        view = {"episodes": [{"use": {"payload": {"selected_refs": [{"id": self.BINDING}]}}}]}
        self.assertEqual(standing_of(self.LESSON, view)["verdicts"], 0)


class SeekBoundTest(unittest.TestCase):
    """A life's questions are looked up once each, and only as often as allowed.

    The brain has no restraint -- a live life asked the same thing on nearly
    every turn -- so the field bounds the asking: one look per question per
    life, and a fixed allowance of looks.
    """

    def setUp(self) -> None:
        self.looks: list[str] = []

        class Field:
            def recall(inner, concern, label=""):
                self.looks.append(concern)
                return Recollection(
                    concern=concern,
                    status="supported",
                    episode={"id": f"memory:recall:{len(self.looks)}"},
                    lessons=(
                        Lesson(
                            source_id=f"games:nethack:lesson:{len(self.looks)}",
                            text=f"what the field knows about {concern}",
                            ref={"id": f"field-qwen:binding:{len(self.looks)}"},
                        ),
                    ),
                )

        self.field = Field()
        self.asked: dict[str, Asking] = {}
        self.seeks: list[tuple[str, Recollection]] = []
        self.refused: list[dict[str, str]] = []

    def ask(self, question: str) -> Asking:
        return ask_the_field(
            question,
            living=self.field,
            asked=self.asked,
            seeks=self.seeks,
            refused=self.refused,
            label="life-1:ask",
        )

    def test_the_same_question_is_looked_up_once(self) -> None:
        first = self.ask("anything about doors")
        again = self.ask("Anything   About Doors")
        self.assertEqual(len(self.looks), 1)
        self.assertEqual(again.status, "repeated")
        self.assertEqual(again.question, "anything about doors")
        # the answer it already has is still shown, marked as asked before
        self.assertEqual(again.lessons, first.lessons)
        memories = Memories(
            Recollection(concern="about to play", status="supported", episode={}, lessons=()),
            asking=again,
        )
        self.assertIn("You asked the field that already", memories.prompt())
        self.assertIn(first.lessons[0].text, memories.prompt())
        self.assertEqual(memories.cited(1).source_id, first.lessons[0].source_id)

    def test_the_allowance_runs_out_and_the_life_decides(self) -> None:
        for index in range(SEEK_LIMIT):
            ask = self.ask(f"question {index}")
            self.assertEqual(ask.status, "supported")
        spent = self.ask("one more thing")
        self.assertTrue(spent.exhausted())
        self.assertEqual(len(self.looks), SEEK_LIMIT)
        self.assertEqual(len(self.seeks), SEEK_LIMIT)
        self.assertEqual(self.refused, [{"question": "one more thing", "why": "asked all it can this life"}])
        # and the decision stands on what the life already has
        woken = Lesson(
            source_id="games:nethack:lesson:woken",
            text="the stairs down are usually past the door",
            ref={"id": "field-qwen:binding:woken"},
        )
        memories = Memories(
            Recollection(concern="about to play", status="supported", episode={}, lessons=()),
            Situation(situations=("explore",), lessons=(woken,), status="supported"),
            asking=spent,
        )
        text = memories.prompt()
        self.assertIn("asked the field all you can", text)
        self.assertIn(woken.text, text)
        self.assertNotIn("question 0", text)
        self.assertEqual(memories.cited(1).source_id, "games:nethack:lesson:woken")


class BrainAskTest(unittest.TestCase):
    """The mind's own question reaches the seam from the model's answer."""

    ACTIONS = (Action(key="l", keys="l", label="move east"),)

    def brain(self, reply: str) -> BrainPlayer:
        class Fixed(BrainPlayer):
            def _request(self, messages, *, max_tokens=0):  # type: ignore[override]
                return reply

        return Fixed(url="http://unused")

    def observation(self) -> Observation:
        return Observation(
            screen=(), summary={}, events=(), prompt=None, done=False, score=0.0, turn=1
        )

    def asked(self, reply: str) -> tuple[str, str]:
        chosen, _reason, _complaint, _used, want = self.brain(reply)._ask(
            observation=self.observation(), actions=self.ACTIONS, recent=()
        )
        return (chosen.key if chosen is not None else ""), want

    def test_the_question_the_model_asked_is_read_and_tidied(self) -> None:
        key, want = self.asked(
            '{"action": "l", "reason": "look around", "want": "  anything   about doors "}'
        )
        self.assertEqual(key, "l")
        self.assertEqual(want, "anything about doors")
        # the other words a model may reach for are read too
        for field in ("ask", "question", "recall"):
            _key, want = self.asked(f'{{"action": "l", "reason": "r", "{field}": "keys"}}')
            self.assertEqual(want, "keys", field)

    def test_an_answer_without_a_question_asks_nothing(self) -> None:
        self.assertEqual(self.asked('{"action": "l", "reason": "look"}')[1], "")
        self.assertEqual(self.asked('{"action": "l", "reason": "look", "want": "   "}')[1], "")
        self.assertEqual(self.asked('{"action": "l", "reason": "look", "want": 7}')[1], "")
        # a question is not asked on behalf of an answer that cannot be played
        self.assertEqual(self.asked('{"action": "zz", "reason": "r", "want": "doors"}'), ("", "doors"))

    def test_a_reply_in_plain_words_is_read_for_its_action(self) -> None:
        """JSON is the shape the brain is offered, not a toll it must pay."""
        chosen, reason, complaint, used, want = self.brain(
            "The corridor looks safe.\nAction: l"
        )._ask(observation=self.observation(), actions=self.ACTIONS, recent=())
        assert chosen is not None
        self.assertEqual(chosen.key, "l")
        self.assertIn("read from your words", reason)
        self.assertEqual(complaint, "")
        self.assertEqual((used, want), (0, ""))
        # a bare move in words, and a bare key on the last line, are read too
        self.assertEqual(self.asked("go east")[0], "l")
        self.assertEqual(self.asked("Walls of rock all around.\nl")[0], "l")

    def test_a_reply_that_names_no_action_at_all_gives_nothing(self) -> None:
        # the walker takes the turn only when the words hold no action either
        self.assertEqual(self.asked("The torch gutters and the dark is long.")[0], "")


class BrainNudgeTest(unittest.TestCase):
    ACTIONS = (
        Action(key="l", keys="l", label="move east"),
        Action(key="j", keys="j", label="move south"),
    )

    def observation(self) -> Observation:
        return Observation(
            screen=LIVE_SCREEN, summary={}, events=(), prompt=None, done=False, score=0.0, turn=4
        )

    def blocked(self) -> list[dict[str, Any]]:
        return [{"turn": 3, "key": "l", "label": "move east", "moved": False, "note": "you did not move"}]

    def test_a_blocked_repeat_is_asked_again_in_words(self) -> None:
        brain = _ScriptedBrain([("l", "east looks good"), ("j", "south instead")])
        decision = brain.decide(
            observation=self.observation(), actions=self.ACTIONS, recent=self.blocked()
        )
        self.assertEqual(decision.action.key, "j")
        self.assertEqual(len(brain.asked), 2)
        self.assertIn("blocked", brain.asked[1])
        self.assertEqual(brain.nudges, 1)
        self.assertIn("blocked", decision.reason)
        self.assertTrue(decision.nudged)
        self.assertTrue(decision.as_dict()["nudged"])

    def test_the_walker_takes_the_turn_if_the_brain_will_not_move(self) -> None:
        brain = _ScriptedBrain([("l", "east"), ("l", "east again")])
        decision = brain.decide(
            observation=self.observation(), actions=self.ACTIONS, recent=self.blocked()
        )
        self.assertEqual(len(brain.asked), 2)
        self.assertEqual(decision.source, "brain-fallback")
        self.assertIn("kept choosing a blocked move", decision.reason)
        self.assertTrue(decision.nudged)

    def test_a_required_brain_never_hands_a_blocked_retry_to_the_walker(self) -> None:
        brain = _ScriptedBrain([("l", "east"), ("l", "east again")])
        brain.require_brain = True
        with self.assertRaises(BrainRequiredError):
            brain.decide(
                observation=self.observation(), actions=self.ACTIONS, recent=self.blocked()
            )
        self.assertEqual(len(brain.asked), 2)

    def test_a_required_brain_answers_small_game_prompts_itself(self) -> None:
        brain = _ScriptedBrain([("no", "keep the scroll")])
        brain.require_brain = True
        question = Observation(
            screen=LIVE_SCREEN, summary={}, prompt="Read this scroll?",
            events=(), done=False, score=0.0, turn=4,
        )
        choices = (Action(key="yes", keys="y", label="yes"), Action(key="no", keys="n", label="no"))
        decision = brain.decide(observation=question, actions=choices, recent=[])
        self.assertEqual(decision.action.key, "no")
        self.assertEqual(decision.source, "brain")
        self.assertEqual(len(brain.asked), 1)


    def test_a_first_move_is_taken_at_once(self) -> None:
        brain = _ScriptedBrain([("j", "south looks open")])
        decision = brain.decide(
            observation=self.observation(), actions=self.ACTIONS, recent=[]
        )
        self.assertEqual(decision.action.key, "j")
        self.assertEqual(len(brain.asked), 1)
        self.assertEqual(decision.source, "brain")
        self.assertFalse(decision.nudged)


class FieldMemoryTest(unittest.TestCase):
    """The level memory: a two-fluid field, read back as a map."""

    def field(self, **kwargs: Any) -> LevelField:
        return LevelField(rows=21, cols=80, **kwargs)

    def test_what_is_seen_is_read_back(self) -> None:
        field = self.field()
        field.observe({(3, 4): "solid", (3, 5): "open", (4, 5): "down"})
        reading = field.read()
        self.assertTrue(reading["terrain"][3, 4])
        self.assertLess(reading["terrain_sign"][3, 4], 0.0)
        self.assertTrue(reading["terrain"][3, 5])
        self.assertGreater(reading["terrain_sign"][3, 5], 0.0)
        self.assertTrue(reading["goal"][4, 5])
        self.assertEqual(field.goals(), [(4, 5, "down")])
        lines = field.render().splitlines()
        self.assertEqual(lines[3][4], "#")
        self.assertEqual(lines[3][5], ".")
        self.assertEqual(lines[4][5], ">")

    def test_a_memory_fades_by_the_fields_own_law(self) -> None:
        field = self.field(half_life=20.0)
        field.observe({(2, 2): "open"})
        fresh = field.content("terrain")[2, 2]
        self.assertAlmostEqual(fresh, (1.0 - EQUILIBRIUM) * field.write, places=6)
        field.step(int(20.0))
        half = field.content("terrain")[2, 2]
        # One half-life is one half-life: the realized decay is checked against
        # the analytic law rather than trusted to the integrator.
        self.assertAlmostEqual(half / fresh, 0.5, places=2)
        field.step(int(20.0))
        self.assertLess(abs(field.content("terrain")[2, 2]), field.threshold)
        self.assertFalse(field.read()["terrain"][2, 2])

    def test_looking_again_restores_a_memory(self) -> None:
        field = self.field(half_life=10.0)
        field.observe({(5, 5): "open"})
        field.step(60)
        self.assertFalse(field.read()["terrain"][5, 5])
        field.observe({(5, 5): "open"})
        self.assertTrue(field.read()["terrain"][5, 5])
        self.assertGreater(field.content("terrain")[5, 5], field.threshold)

    def test_a_refusal_is_remembered_with_its_kind(self) -> None:
        field = self.field()
        field.observe({}, position=(6, 6), blocked=(6, 7, "door"))
        field.observe({}, position=(7, 6), blocked=(8, 6, "blocked"))
        self.assertEqual(field.blocked_cells(), [(6, 7, "door"), (8, 6, "blocked")])
        lines = field.render().splitlines()
        self.assertEqual(lines[6][7], "+")
        self.assertEqual(lines[8][6], "x")
        self.assertIn("1 door that would not open", field.summary())

    def test_the_trail_marks_where_the_player_has_been(self) -> None:
        field = self.field()
        field.observe({}, position=(1, 1))
        self.assertTrue(field.read()["trail"][1, 1])
        field.observe({}, position=(1, 2))
        lines = field.render().splitlines()
        self.assertEqual(lines[1][2], "@")
        self.assertEqual(lines[1][1], "\u00b7")
        self.assertIn("you have walked 2 cells", field.summary())

    def test_the_field_says_where_the_player_is(self) -> None:
        field = self.field()
        field.observe({}, position=(18, 63))
        self.assertEqual(field.here(), (18, 63))
        self.assertIn("you are at column 63, row 18", field.summary())

    def test_the_field_gives_the_bearing_to_what_it_holds(self) -> None:
        field = self.field()
        field.observe({(18, 54): "down"}, position=(18, 63))
        self.assertIn("(9 columns west of you)", field.summary())
        field.observe({}, position=(18, 54))
        self.assertIn("(you are standing on it)", field.summary())

    def test_the_summary_names_a_way_down(self) -> None:
        field = self.field()
        field.observe({(7, 34): "down", (2, 3): "up"})
        summary = field.summary()
        self.assertIn("way down at column 34, row 7", summary)
        self.assertIn("way up at column 3, row 2", summary)

    def test_the_block_tells_the_player_the_legend_and_the_map(self) -> None:
        field = self.field()
        field.observe({(0, 0): "open", (0, 1): "solid"})
        block = field.block()
        self.assertIn("What you remember of this level", block)
        self.assertIn("'.' open, '#' solid", block)
        self.assertIn("count from 0", block)
        self.assertIn("\n 0 .#", block)
        self.assertIn("you have walked 0 cells and know 2 of the level's cells (1 solid)", block)

    def test_the_field_is_deterministic(self) -> None:
        cells = {(row, col): "open" for row in range(3) for col in range(3)}
        first, second = self.field(), self.field()
        for field in (first, second):
            field.observe(cells, position=(1, 1))
            field.observe({}, position=(1, 2), blocked=(1, 3, "blocked"))
        self.assertEqual(first.state()["digest"], second.state()["digest"])
        first.step()
        self.assertNotEqual(first.state()["digest"], second.state()["digest"])

    def test_a_screen_reads_as_cells_the_memory_can_keep(self) -> None:
        world = NetHackWorld(program="nethack.exe", write_config=False)
        cells = world.level_cells(frame(LIVE_SCREEN))
        # The capture draws its room at screen rows 3-9; the map area starts one
        # row below the message line, so the room is at map rows 2-8.  Its walls
        # are the symset's box drawing, not ASCII '-'.
        self.assertEqual(cells[(2, 9)], "solid")     # the room's top-left corner
        self.assertEqual(cells[(3, 9)], "solid")     # its left wall
        self.assertEqual(cells[(3, 10)], "open")     # its floor
        self.assertEqual(cells[(3, 18)], "door")     # the door in its east wall
        self.assertEqual(cells[(4, 17)], "up")       # the '<' stairs in the room
        self.assertEqual(cells[(4, 14)], "open")     # the pet stands on floor
        self.assertEqual(cells[(6, 17)], "gold")     # the gold is a cell the memory keeps
        self.assertNotIn((0, 0), cells)              # blank is not knowledge
        self.assertEqual(world.map_cell((3, 10)), (2, 10))

    def test_a_glyph_the_map_does_not_name_is_ground_and_a_blank_is_not(self) -> None:
        world = NetHackWorld(program="nethack.exe", write_config=False)
        cells = world.level_cells(frame(("a message", "..@░ ", "  | ") + ("",) * 19))
        self.assertEqual(cells[(0, 0)], "open")      # floor
        self.assertEqual(cells[(0, 2)], "open")      # the player stands on ground
        self.assertEqual(cells[(0, 3)], "open")      # the shade glyph is ground too
        self.assertNotIn((0, 4), cells)              # blank: unlit or unexplored
        self.assertEqual(cells[(1, 2)], "solid")     # walls still walls

    def test_a_blocked_step_blames_the_cell_it_tried_to_enter(self) -> None:
        world = NetHackWorld(program="nethack.exe", write_config=False)
        world.last_note = "The door is locked."
        blocked = world.blocked_cell(
            (5, 9), Action(key="l", keys="l", label="move east"), moved=False
        )
        self.assertEqual(blocked, (5, 10, "door"))
        world.last_note = "There is a wall there."
        blocked = world.blocked_cell(
            (5, 9), Action(key="k", keys="k", label="move north"), moved=False
        )
        self.assertEqual(blocked, (4, 9, "blocked"))
        self.assertIsNone(
            world.blocked_cell((5, 9), Action(key="l", keys="l", label="move east"), moved=True)
        )

    def test_a_failed_action_that_is_not_a_step_blames_no_cell(self) -> None:
        world = NetHackWorld(program="nethack.exe", write_config=False)
        world.last_note = "You find nothing."
        self.assertIsNone(
            world.blocked_cell((5, 9), Action(key="s", keys="s", label="search"), moved=False)
        )
        # Standing on a door that will not open is about the cell it stands on.
        world.last_note = "This door is locked."
        self.assertEqual(
            world.blocked_cell((5, 9), Action(key="o", keys="o", label="open"), moved=False),
            (5, 9, "door"),
        )

    def test_a_creature_in_the_way_is_not_a_wall(self) -> None:
        world = NetHackWorld(program="nethack.exe", write_config=False)
        world.last_note = "You stop.  Your kitten is in the way!"
        self.assertEqual(
            world.blocked_cell((5, 9), Action(key="l", keys="l", label="move east"), moved=False),
            (5, 10, "creature"),
        )

    def test_the_memory_reaches_the_brains_question(self) -> None:
        brain = _ScriptedBrain([("l", "east")])
        brain.decide(
            observation=Observation(
                screen=LIVE_SCREEN,
                summary={},
                events=(),
                prompt=None,
                done=False,
                score=0.0,
                turn=1,
            ),
            actions=(Action(key="l", keys="l", label="move east"),),
            recent=(),
            memory="What you remember of this level: (nothing yet)",
        )
        question = brain._question(
            observation=Observation(
                screen=LIVE_SCREEN,
                summary={},
                events=(),
                prompt=None,
                done=False,
                score=0.0,
                turn=1,
            ),
            actions=(Action(key="l", keys="l", label="move east"),),
            recent=(),
            memory="What you remember of this level: (nothing yet)",
        )
        self.assertIn("What you remember of this level", question)
        self.assertIn("the route's first step is the move to make", question)
        with_memories = brain._question(
            observation=Observation(
                screen=LIVE_SCREEN,
                summary={},
                events=(),
                prompt=None,
                done=False,
                score=0.0,
                turn=1,
            ),
            actions=(Action(key="l", keys="l", label="move east"),),
            recent=(),
            remembered="What you remember about playing:\n  1. the kitten blocks corridors",
        )
        self.assertIn("the kitten blocks corridors", with_memories)
        plain = brain._question(
            observation=Observation(
                screen=LIVE_SCREEN,
                summary={},
                events=(),
                prompt=None,
                done=False,
                score=0.0,
                turn=1,
            ),
            actions=(Action(key="l", keys="l", label="move east"),),
            recent=(),
        )
        self.assertNotIn("the route's first step is the move to make", plain)


class RouteFieldTest(unittest.TestCase):
    """The route: a distance field relaxed over what the memory holds."""

    def room(self, **kwargs: Any) -> LevelField:
        """A 3x9 room, open everywhere except a wall in the middle of the bottom row."""
        field = LevelField(rows=3, cols=9, **kwargs)
        cells = {(row, col): "open" for row in range(3) for col in range(9)}
        cells[(1, 4)] = "solid"
        cells[(1, 5)] = "solid"
        cells[(1, 8)] = "down"
        field.observe(cells, position=(1, 0))
        return field

    def test_the_route_runs_from_where_the_player_stands_to_the_stairs(self) -> None:
        field = self.room()
        field.head("down")
        route = field.route(steps=8)
        self.assertEqual(route.target, (1, 8))
        self.assertTrue(route.reachable)
        self.assertFalse(route.arrived)
        self.assertEqual(route.moves, 8)
        self.assertEqual(route.directions[0], "northeast")  # the wall makes two routes equal
        self.assertEqual(route.directions[-1], "southeast")
        self.assertIn("the route from where you stand runs northeast", field.block())

    def test_the_route_goes_around_a_cell_that_refused_the_player(self) -> None:
        plain = self.room()
        plain.head("down")
        straight = plain.route(steps=8)
        refused = self.room()
        refused.observe({}, position=(1, 0), blocked=(1, 3, "blocked"))
        refused.head("down")
        around = refused.route(steps=8)
        self.assertTrue(around.reachable)
        self.assertEqual(around.target, (1, 8))
        self.assertGreaterEqual(around.length, straight.length)
        walked, cell = [refused.here()], refused.here()
        cost = refused.cost_map()
        while cell is not None:
            cell = refused._descent(cell, cost, refused.distance)
            if cell is None:
                break
            walked.append(cell)
        self.assertNotIn((1, 3), walked)  # the route leaves the refusal out
        self.assertEqual(walked[-1], (1, 8))

    def test_the_route_can_aim_at_ground_the_player_has_not_seen(self) -> None:
        # A remembered room with one opening in its east wall; beyond the
        # opening nothing has been seen, so that is where knowledge ends.
        field = LevelField(rows=5, cols=12)
        cells = {(row, col): "solid" for row in range(5) for col in range(6)}
        for row in range(1, 4):
            for col in range(1, 5):
                cells[(row, col)] = "open"
        cells[(2, 5)] = "open"
        field.observe(cells, position=(2, 2))
        self.assertEqual(field.frontier(), [(2, 5)])
        field.head("unseen")
        route = field.route()
        self.assertTrue(route.reachable)
        self.assertFalse(route.arrived)
        self.assertEqual(route.directions[0], "east")
        self.assertIn("edge of what you know", route.sentence())
        self.assertEqual(field.next_step(), (0, 1))
        field.observe({}, position=(2, 5))
        field.head("unseen")
        self.assertEqual(field.next_step(), (0, 1))  # the step is into the unseen
        self.assertIn("ground you have not seen lies east", field.route().sentence())

    def test_a_room_that_is_all_known_has_no_frontier(self) -> None:
        field = LevelField(rows=3, cols=9)
        cells = {(row, col): "open" for row in range(3) for col in range(9)}
        field.observe(cells, position=(1, 4))
        self.assertEqual(field.frontier(), [])
        field.head("unseen")
        self.assertIn("seen everything you can reach", field.route().sentence())

    def test_a_bumped_door_is_still_the_way_out_of_a_sealed_room(self) -> None:
        # A room seen completely, its one doorway seen as rock and then refused
        # as a door.  Reading that refusal as rock left the field with no
        # frontier at all: it stood in the room taking no step, told it had seen
        # everything, while unseen ground lay beyond the door.
        field = LevelField(rows=5, cols=12)
        cells = {(row, col): "open" for row in range(1, 4) for col in range(1, 5)}
        for row in range(5):
            for col in range(6):
                cells.setdefault((row, col), "solid")
        field.observe(cells, position=(2, 2))
        field.observe({}, position=(2, 2), blocked=(2, 5, "door"))
        self.assertEqual(field.frontier(), [(2, 5)])  # the door is where knowledge continues
        field.head("unseen")
        self.assertEqual(field.next_step(), (0, 1))  # the route leaves through it
        self.assertIn("the edge of what you know", field.route().sentence())
        # A refusal from rock is still rock: the wall keeps its cost at nothing.
        field.observe({}, position=(2, 2), blocked=(2, 4, "blocked"))
        self.assertFalse(np.isfinite(field.cost_map()[2, 4]))

    def test_a_player_heading_nowhere_is_told_where_the_unknown_is(self) -> None:
        field = LevelField(rows=3, cols=9)
        cells = {(row, col): "open" for row in range(3) for col in range(5)}
        field.observe(cells, position=(1, 0))
        self.assertIn("the edge of what you know is 4 moves away, and the first step is east",
                      field.no_aim_sentence())
        self.assertIn("Nothing is being headed for", field.block())
        field.observe({}, position=(1, 4))
        self.assertIn("ground you have not seen lies east", field.no_aim_sentence())
        field.head("unseen")
        self.assertEqual(field.no_aim_sentence(), "")

    def test_the_route_starts_from_where_the_player_stands(self) -> None:
        field = LevelField(rows=3, cols=9)
        cells = {(row, col): "open" for row in range(3) for col in range(9)}
        cells[(1, 8)] = "down"
        field.observe(cells, position=(1, 0))
        # The memory is wrong about the player's own cell (a wall searched, a
        # creature blamed); the route still starts there.
        field.observe({}, position=(1, 0), blocked=(1, 0, "blocked"))
        field.head("down")
        self.assertEqual(field.next_step(), (0, 1))
        self.assertEqual(field.route().directions[0], "east")

    def test_the_step_reason_says_what_the_route_is_doing(self) -> None:
        field = self.room()
        field.head("down")
        self.assertEqual(
            field.route().step_reason(), "the route field steps northeast (8 moves to the way down)"
        )

    def test_gold_is_a_place_the_route_can_head_for(self) -> None:
        field = LevelField(rows=3, cols=9)
        cells = {(row, col): "open" for row in range(3) for col in range(9)}
        cells[(1, 5)] = "gold"
        field.observe(cells, position=(1, 0))
        self.assertEqual(field.valuable_cells(), [(1, 5, "gold")])
        self.assertTrue(field.can_reach("value"))
        field.head("value")
        self.assertEqual(field.next_step(), (0, 1))  # east, toward the pile
        self.assertIn("gold or goods", field.route().sentence())
        self.assertIn("gold or goods", field.route().step_reason())
        lines = field.render().splitlines()
        self.assertEqual(lines[1][5], "$")  # the remembered map keeps the pile

    def test_the_route_prefers_ground_the_player_has_not_walked(self) -> None:
        field = LevelField(rows=3, cols=9)
        cells = {(row, col): "open" for row in range(3) for col in range(9)}
        cells[(1, 8)] = "down"
        field.observe(cells, position=(1, 0))
        for col in range(1, 5):
            field.observe({}, position=(1, col))
        field.observe({}, position=(1, 0))
        field.head("down")
        route = field.route()
        self.assertEqual(route.directions[0], "northeast")  # up out of the walked row
        self.assertLess(route.length, 8 * WALKED_COST)

    def test_a_creature_that_refuses_a_step_is_not_a_wall(self) -> None:
        field = LevelField(rows=3, cols=9)
        cells = {(row, col): "open" for row in range(3) for col in range(9)}
        cells[(1, 8)] = "down"
        field.observe(cells, position=(1, 0))
        field.observe({}, position=(1, 0), blocked=(1, 1, "creature"))
        self.assertEqual(field.blocked_cells(), [])
        field.head("down")
        self.assertEqual(field.next_step(), (0, 1))  # the route still steps there
        field.observe({}, position=(1, 0), blocked=(1, 1, "blocked"))
        self.assertEqual([cell[:2] for cell in field.blocked_cells()], [(1, 1)])

    def test_the_route_reaches_the_stairs_from_every_cell_it_remembers(self) -> None:
        field = self.room()
        field.head("down")
        cost = field.cost_map()
        for row, col in np.argwhere(np.isfinite(cost)):
            cell = (int(row), int(col))
            walked, steps = cell, 0
            while steps < 50 and field._descent(walked, cost, field.distance) is not None:
                walked = field._descent(walked, cost, field.distance)  # type: ignore[assignment]
                steps += 1
            self.assertEqual(walked, (1, 8), f"the route from {cell} ended at {walked}")

    def test_the_route_is_gone_when_the_way_to_it_is_forgotten(self) -> None:
        field = LevelField(rows=3, cols=9, half_life=8.0)
        field.observe({(1, 8): "down"}, position=(1, 0))
        self.assertFalse(field.can_reach("down"))
        field.head("down")
        route = field.route()
        self.assertFalse(route.reachable)
        self.assertIn("not a way to reach it any more", route.sentence())

    def test_the_route_is_deterministic(self) -> None:
        first, second = self.room(), self.room()
        for field in (first, second):
            field.head("down")
        self.assertEqual(first.route().as_dict(), second.route().as_dict())
        self.assertTrue(np.array_equal(first.distance, second.distance, equal_nan=True))

    def test_a_step_becomes_the_games_own_move(self) -> None:
        world = NetHackWorld(program="nethack.exe", write_config=False)
        for step, key in (
            ((-1, 0), "k"), ((0, 1), "l"), ((1, 0), "j"), ((0, -1), "h"),
            ((-1, 1), "u"), ((1, -1), "b"), ((-1, -1), "y"), ((1, 1), "n"),
        ):
            action = world.move_action(step)
            self.assertIsNotNone(action)
            self.assertEqual(action.key, key)  # type: ignore[union-attr]


class DungeonFieldTest(unittest.TestCase):
    """The dungeon: one memory per level, each still fading while away."""

    def dungeon(self, **kwargs: Any) -> DungeonField:
        return DungeonField(rows=3, cols=9, **kwargs)

    def test_each_level_keeps_its_own_memory(self) -> None:
        dungeon = self.dungeon(half_life=40.0)
        dungeon.visit(1)
        dungeon.observe({(1, 2): "open"}, position=(1, 2))
        dungeon.visit(2)
        dungeon.observe({(0, 0): "open"}, position=(0, 0))
        self.assertEqual(len(dungeon.levels), 2)
        self.assertEqual(dungeon.state()["visited"], [1, 2])
        back = dungeon.visit(1)
        self.assertTrue(back.read()["terrain"][1, 2])
        self.assertFalse(back.read()["terrain"][0, 0])

    def test_a_level_left_behind_keeps_fading(self) -> None:
        dungeon = self.dungeon(half_life=10.0)
        dungeon.visit(1)
        dungeon.observe({(1, 2): "open"}, position=(1, 2))
        fresh = dungeon.levels[1].content("terrain")[1, 2]
        dungeon.visit(2)
        for _ in range(10):
            dungeon.observe({}, position=(0, 0))
        faded = dungeon.levels[1].content("terrain")[1, 2]
        self.assertAlmostEqual(faded / fresh, 0.5, places=2)

    def test_the_dungeon_says_where_the_player_came_from(self) -> None:
        dungeon = self.dungeon()
        dungeon.visit(1)
        self.assertIn("nowhere else", dungeon.heading())
        dungeon.visit(2)
        self.assertIn("came down here from level 1", dungeon.heading())
        dungeon.visit(1)
        self.assertIn("came up here from level 2", dungeon.heading())

    def test_an_intention_is_offered_only_when_it_can_act(self) -> None:
        dungeon = self.dungeon()
        dungeon.visit(1)
        self.assertEqual(dungeon.intent_actions(), ())
        cells = {(row, col): "open" for row in range(3) for col in range(9)}
        cells[(1, 8)] = "down"
        dungeon.observe(cells, position=(1, 0))
        self.assertEqual(dungeon.intent_actions(), (("head-down", INTENTS["head-down"]),))
        dungeon.aim("down")
        offered = dict(dungeon.intent_actions())
        self.assertIn("head-down", offered)
        self.assertIn("wander", offered)
        dungeon.observe({}, position=(1, 8))
        dungeon.aim("down")
        offered = dict(dungeon.intent_actions())
        self.assertNotIn("head-down", offered)  # standing on it: the stairs are the action
        self.assertEqual(dungeon.next_step(), None)

    def test_a_finished_intention_is_retired_when_the_brain_steps_in(self) -> None:
        dungeon = self.dungeon()
        dungeon.visit(1)
        cells = {(row, col): "open" for row in range(3) for col in range(9)}
        cells[(1, 8)] = "down"
        dungeon.observe(cells, position=(1, 0))
        dungeon.aim("down")
        dungeon.retire_aim()
        self.assertEqual(dungeon.route().aim, "down")  # still something to do
        dungeon.observe({}, position=(1, 8))
        dungeon.aim("down")
        dungeon.retire_aim()
        self.assertIsNone(dungeon.route().aim)  # arrived: the intention is done

    def test_the_way_up_is_not_offered_from_the_top_level(self) -> None:
        dungeon = self.dungeon()
        dungeon.visit(1)
        cells = {(row, col): "open" for row in range(3) for col in range(9)}
        cells[(1, 8)] = "down"
        cells[(1, 0)] = "up"
        dungeon.observe(cells, position=(1, 4))
        offered = dict(dungeon.intent_actions())
        self.assertIn("head-down", offered)
        self.assertNotIn("head-up", offered)  # up from level 1 leaves the dungeon
        dungeon.visit(2)
        dungeon.observe(cells, position=(1, 4))
        self.assertIn("head-up", dict(dungeon.intent_actions()))

    def test_the_next_step_follows_the_route_the_field_holds(self) -> None:
        dungeon = self.dungeon()
        dungeon.visit(1)
        cells = {(row, col): "open" for row in range(3) for col in range(9)}
        cells[(1, 8)] = "down"
        dungeon.observe(cells, position=(1, 0))
        dungeon.aim("down")
        self.assertEqual(dungeon.next_step(), (0, 1))
        self.assertEqual(dungeon.route().moves, 8)
        self.assertEqual(dungeon.turn_state()["route"]["moves"], 8)

    def test_the_gold_is_offered_as_an_intention(self) -> None:
        dungeon = self.dungeon()
        dungeon.visit(1)
        cells = {(row, col): "open" for row in range(3) for col in range(9)}
        cells[(1, 5)] = "gold"
        dungeon.observe(cells, position=(1, 0))
        self.assertIn("head-value", dict(dungeon.intent_actions()))
        self.assertTrue(dungeon.can_reach("value"))
        dungeon.aim("value")
        self.assertEqual(dungeon.next_step(), (0, 1))
        # nothing worth taking: the intention is not offered for nothing
        empty = self.dungeon()
        empty.visit(1)
        empty.observe(
            {(row, col): "open" for row in range(3) for col in range(9)}, position=(1, 0)
        )
        self.assertNotIn("head-value", dict(empty.intent_actions()))


class WalkingPolicyTest(unittest.TestCase):
    """When the route walks by itself, and when the brain is asked again."""

    def route(self, aim: str = "down", **kwargs: Any) -> Any:
        field = LevelField(rows=3, cols=9, **kwargs)
        cells = {(row, col): "open" for row in range(3) for col in range(9)}
        cells[(1, 8)] = "down"
        field.observe(cells, position=(1, 0))
        field.head(aim)
        return field.route()

    @staticmethod
    def observation(**summary: Any) -> Observation:
        return Observation(screen=("x",), summary=dict(summary))

    def test_a_laid_route_walks_by_itself(self) -> None:
        self.assertEqual(route_wake(self.observation(), (), self.route(), (0, 1)), "")

    def test_a_route_that_cannot_step_means_the_brain_decides(self) -> None:
        self.assertIn("no route", route_wake(self.observation(), (), None, (0, 1)))
        self.assertIn("nowhere", route_wake(self.observation(), (), self.route(), None))

    def test_a_question_from_the_game_wakes_the_brain(self) -> None:
        asked = Observation(screen=("x",), summary={}, prompt="Do you want your possessions identified?")
        self.assertIn("asking a question", route_wake(asked, (), self.route(), (0, 1)))

    def test_arriving_at_the_stairs_wakes_the_brain(self) -> None:
        field = LevelField(rows=3, cols=9)
        cells = {(row, col): "open" for row in range(3) for col in range(9)}
        cells[(1, 8)] = "down"
        field.observe(cells, position=(1, 8))
        field.head("down")
        self.assertIn("arrived", route_wake(self.observation(), (), field.route(), None))

    def test_reaching_the_edge_of_knowledge_does_not_wake_the_brain(self) -> None:
        field = LevelField(rows=3, cols=9)
        cells = {(row, col): "open" for row in range(3) for col in range(5)}
        field.observe(cells, position=(1, 4))
        field.head("unseen")
        route = field.route()
        self.assertTrue(route.arrived)
        self.assertEqual(route_wake(self.observation(), (), route, (0, 1)), "")

    def test_a_refused_step_is_absorbed_until_it_keeps_happening(self) -> None:
        once = ({"source": "route", "moved": False},)
        self.assertEqual(route_wake(self.observation(), once, self.route(), (0, 1)), "")
        twice = once * 2
        self.assertEqual(route_wake(self.observation(), twice, self.route(), (0, 1)), "")
        thrice = once * ROUTE_REFUSALS_BEFORE_LOOK
        self.assertIn("refused", route_wake(self.observation(), thrice, self.route(), (0, 1)))
        # A refusal the brain caused itself is not the route's to absorb.
        by_brain = ({"source": "brain", "moved": False},)
        self.assertEqual(route_wake(self.observation(), by_brain, self.route(), (0, 1)), "")

    def test_what_the_game_says_wakes_the_brain(self) -> None:
        said = self.observation(message="The kitten bites!  You die...")
        self.assertIn("the game said", route_wake(said, (), self.route(), (0, 1)))
        swapping = self.observation(message="You swap places with your kitten.")
        self.assertEqual(route_wake(swapping, (), self.route(), (0, 1)), "")

    def test_a_change_in_state_wakes_the_brain(self) -> None:
        recent = ({"source": "route", "moved": True, "hp": 18, "armor": 6, "gold": 0, "depth": 1},)
        hurt = self.observation(hp=16, armor=6, gold=0, depth=1)
        self.assertIn("health changed", route_wake(hurt, recent, self.route(), (0, 1)))
        deeper = self.observation(hp=18, armor=6, gold=0, depth=2)
        self.assertIn("level changed", route_wake(deeper, recent, self.route(), (0, 1)))

    def test_a_long_walk_ends_in_a_look_at_the_screen(self) -> None:
        recent = tuple({"source": "route", "moved": True, "hp": 18, "armor": 6, "gold": 0, "depth": 1}
                       for _ in range(ROUTE_STEPS_BEFORE_LOOK))
        self.assertIn("walked", route_wake(self.observation(hp=18, armor=6, gold=0, depth=1),
                                          recent, self.route(), (0, 1)))


class WatchPageTest(unittest.TestCase):
    def test_the_screen_is_escaped_and_coloured(self) -> None:
        html = render_screen(("<script>alert(1)</script>", "@|.$"))
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;", html)
        self.assertIn('class="me"', html)
        self.assertIn('class="wall"', html)
        self.assertIn('class="stairs"', html)  # the '>' of a redirection
        self.assertEqual(html.count("<div"), 2)

    def test_a_declared_prose_row_is_words_not_glyphs(self) -> None:
        html = render_screen(("You see a d and a $ here.", "@d$"), prose_rows=(0,))
        first_row = html.split("</div>")[0]
        self.assertNotIn("<span", first_row)
        self.assertIn("You see a d and a $ here.", first_row)
        self.assertIn('class="monster"', html)  # the map row is still glyphs

    def test_a_second_run_on_the_same_port_is_refused(self) -> None:
        first = WatchView(port=0, title="first")
        first.start()
        try:
            with self.assertRaises(RuntimeError) as raised:
                WatchView(port=first.port, title="second").start()
            self.assertIn("already held", str(raised.exception))
        finally:
            first.stop()
        second = WatchView(port=first.port, title="second")
        second.start()
        second.stop()


TOY_GAME = r'''
# A twenty-line terminal game: the seam's second world, so the seam can be
# exercised end to end without NetHack installed and without a real life.
import msvcrt
import sys

WIDTH, HEIGHT = 20, 6
PLAYER = [2, 2]
GOLD = [[3, 5], [4, 12]]
SCORE = 0
MOVES = 0


def draw(message):
    rows = []
    for y in range(HEIGHT):
        row = []
        for x in range(WIDTH):
            if [y, x] == PLAYER:
                row.append("@")
            elif [y, x] in GOLD:
                row.append("$")
            elif y in (0, HEIGHT - 1) or x in (0, WIDTH - 1):
                row.append("#")
            else:
                row.append(".")
        rows.append("".join(row))
    while len(rows) < 16:
        rows.append("")
    sys.stdout.write("\x1b[H" + message.ljust(78) + "\n")
    sys.stdout.write("\n".join(rows) + "\n")
    sys.stdout.write("Dlvl:1 Gold:%d Moves:%d" % (SCORE, MOVES))
    sys.stdout.write("\x1b[J")
    sys.stdout.flush()


draw("Welcome to the toy dungeon.")
while True:
    key = msvcrt.getch().decode("ascii", "replace")
    message = ""
    if key == "q":
        draw("Goodbye.")
        break
    if key in "hjkl":
        dy, dx = {"h": (0, -1), "l": (0, 1), "k": (-1, 0), "j": (1, 0)}[key]
        ny, nx = PLAYER[0] + dy, PLAYER[1] + dx
        if 0 < ny < HEIGHT - 1 and 0 < nx < WIDTH - 1:
            PLAYER[0], PLAYER[1] = ny, nx
            MOVES += 1
        if PLAYER in GOLD:
            GOLD.remove(list(PLAYER))
            SCORE += 1
            message = "You take the gold."
    elif key == ",":
        message = "There is nothing here to pick up."
    draw(message)
'''


class _ToyWorld(ScreenWorld):
    """A second game, in twenty lines, on the same seam as NetHack."""

    name = "toy"
    goal = "collect the gold"

    def __init__(self, program: Path) -> None:
        super().__init__(quiet=0.25, idle=3.0)
        self.program = program

    def argv(self) -> Sequence[str]:
        return [sys.executable, "-X", "utf8", str(self.program)]

    def handshake(self, session) -> None:
        session.wait_for("Gold:", timeout=20.0)

    def read(self, frame: ScreenFrame) -> Mapping[str, Any]:
        text = frame.text
        found = re.search(r"Gold:(\d+) Moves:(\d+)", text)
        return {
            "message": self.message_line(frame),
            "summary": {
                "gold": int(found.group(1)) if found else 0,
                "moves": int(found.group(2)) if found else 0,
            },
            "score": float(found.group(1)) if found else 0.0,
        }

    def vocabulary(self, frame: ScreenFrame) -> tuple[Action, ...]:
        return (
            Action(key="h", keys="h", label="move west"),
            Action(key="l", keys="l", label="move east"),
            Action(key="k", keys="k", label="move north"),
            Action(key="j", keys="j", label="move south"),
            Action(key=",", keys=",", label="pick up what is here"),
        )


@unittest.skipUnless(sys.platform == "win32", "the pseudoconsole is a Windows one")
class LivingMemoryTest(unittest.TestCase):
    """What Cassi remembers between lives, and which memory it says it used."""

    ACTIONS = (
        Action(key="l", keys="l", label="move east"),
        Action(key="j", keys="j", label="move south"),
    )

    @staticmethod
    def _observation(turn: int = 1) -> Observation:
        return Observation(
            screen=LIVE_SCREEN,
            summary={},
            events=(),
            prompt=None,
            done=False,
            score=0.0,
            turn=turn,
        )

    @staticmethod
    def _recollection() -> Recollection:
        return Recollection(
            concern="about to play",
            status="supported",
            episode={"id": "memory:recall:one"},
            lessons=(
                Lesson(
                    source_id="games:nethack:lesson:1",
                    text="the kitten blocks corridors",
                    ref={"id": "field-qwen:binding:1"},
                ),
                Lesson(
                    source_id="games:nethack:lesson:2",
                    text="stairs down sit near the edge",
                    ref={"id": "field-qwen:binding:2"},
                ),
            ),
        )

    def test_a_recollection_numbers_what_it_remembers_and_reads_it_back(self) -> None:
        recollection = self._recollection()
        text = recollection.prompt()
        self.assertIn("1. the kitten blocks corridors", text)
        self.assertIn("2. stairs down sit near the edge", text)
        self.assertIn('"used"', text)
        self.assertEqual(recollection.cited(2).source_id, "games:nethack:lesson:2")
        self.assertIsNone(recollection.cited(0))
        self.assertIsNone(recollection.cited(3))
        self.assertEqual(
            recollection.refs(), ({"id": "field-qwen:binding:1"}, {"id": "field-qwen:binding:2"})
        )

    def test_a_recollection_nobody_used_has_nothing_to_say(self) -> None:
        empty = Recollection(
            concern="about to play", status="support-gap", episode={"id": "e"}, lessons=()
        )
        self.assertEqual(empty.prompt(), "")
        self.assertIsNone(empty.cited(1))

    def test_no_memory_remembers_nothing_and_never_invents_a_use(self) -> None:
        recollection = NO_MEMORY.recall("about to play")
        self.assertEqual(recollection.status, "no-memory")
        self.assertEqual(recollection.lessons, ())
        self.assertEqual(recollection.prompt(), "")
        self.assertIsNone(NO_MEMORY.used(recollection, consumer={}))
        self.assertIsNone(NO_MEMORY.settle(episode=None, outcome_id="x", consequence={}, usefulness=1.0))
        self.assertEqual(NO_MEMORY.autobiography()["episodes"], [])
        self.assertFalse(NO_MEMORY.as_dict()["enabled"])

    def test_the_number_the_brain_names_is_the_memory_it_used(self) -> None:
        self.assertEqual(_memory_number({"used": 2}), 2)
        self.assertEqual(_memory_number({"used": "3 - the kitten"}), 3)
        self.assertEqual(_memory_number({"used": "none of them"}), 0)
        self.assertEqual(_memory_number({"used": 0}), 0)
        self.assertEqual(_memory_number({}), 0)

    def test_the_brain_is_told_what_cassi_remembers_and_answers_with_what_it_used(self) -> None:
        brain = _ScriptedBrain([("l", "east, past the kitten")], used=[1])
        recollection = self._recollection()
        decision = brain.decide(
            observation=self._observation(),
            actions=self.ACTIONS,
            recent=(),
            remembered=recollection.prompt(),
        )
        self.assertEqual(brain.remembered[0], recollection.prompt())
        self.assertEqual(decision.used, 1)
        self.assertEqual(recollection.cited(decision.used).text, "the kitten blocks corridors")
        # a brain that names no memory uses none, and the recollection says so
        quiet = _ScriptedBrain([("j", "south")])
        silent = quiet.decide(
            observation=self._observation(),
            actions=self.ACTIONS,
            recent=(),
            remembered=recollection.prompt(),
        )
        self.assertEqual(silent.used, 0)
        self.assertIsNone(recollection.cited(silent.used))

    def test_a_life_says_how_deep_it_got_and_whether_that_was_down(self) -> None:
        journal = [
            {"turn": 1, "depth": 1, "label": "move east", "cell": [4, 5], "note": ""},
            {"turn": 2, "depth": 1, "label": "move east", "cell": [4, 6], "note": ""},
            {"turn": 3, "depth": 2, "label": "descend", "cell": [4, 7], "note": ""},
        ]
        ending, reached, descended, turns = life_outcome(None, journal, 1)
        self.assertEqual((reached, descended, turns), (2, True, 3))
        self.assertIn("stopped before the life did", ending)
        # a life that never left its level did not descend
        flat = [row for row in journal if row["depth"] == 1]
        _ending, reached_flat, descended_flat, _turns = life_outcome(None, flat, 1)
        self.assertEqual((reached_flat, descended_flat), (1, False))
        story = life_story(
            journal,
            {
                "1": {"known_cells": 40, "walked_cells": 9, "goals": [[8, 25, "down"]], "blocked_cells": [[5, 9, "door"]]},
                "2": {"known_cells": 12, "walked_cells": 3, "goals": [], "blocked_cells": []},
            },
            ending=ending,
            reached=reached,
        )
        self.assertIn("level 1: you saw 40 cells", story)
        self.assertIn("a way down at 8,25", story)
        self.assertIn("no way onward found", story)

    def test_the_situation_is_read_from_what_a_player_can_see(self) -> None:
        screen = ("#####", "#@d.#", "#>..#", "#####")
        observation = Observation(
            screen=screen,
            summary={"hp": 7, "hp_max": 18, "depth": 2},
            events=(),
            prompt=None,
            done=False,
            score=0.0,
            turn=9,
        )
        context, situations = situation_context(observation, [{"moved": False, "depth": 2}])
        self.assertTrue(context["blocked"])
        self.assertTrue(context["monster"])
        self.assertTrue(context["hurt"])
        self.assertTrue(context["new_level"])
        self.assertFalse(context["exploring"])
        self.assertIn("blocked", situations)
        self.assertIn("monster", situations)
        self.assertEqual(monsters_beside(screen), ("d",))
        # a healthy player on ground it knows, with nothing beside it
        calm = Observation(
            screen=("#####", "#@..#", "#####"),
            summary={"hp": 18, "hp_max": 18, "depth": 2},
            events=(),
            prompt=None,
            done=False,
            score=0.0,
            turn=40,
        )
        calm_context, calm_situations = situation_context(
            calm, [{"moved": True, "depth": 2}] * 9
        )
        self.assertTrue(calm_context["exploring"])
        self.assertFalse(calm_context["hurt"])
        self.assertNotIn("new-level", calm_situations)
        self.assertIn("always", calm_situations)

    def test_a_decision_is_shown_what_applies_now_and_nothing_else(self) -> None:
        """The field decides what a decision is shown, and its list is short.

        A lesson is heard when its moment comes; the life's whole recollection
        stands in only when the field did not answer at all, because a memory
        that cannot be matched is still better than silence.
        """

        recollection = self._recollection()
        situation = Situation(
            situations=("blocked",),
            lessons=(
                Lesson(
                    source_id="games:nethack:lesson:2",
                    text="stairs down sit near the edge",
                    ref={"id": "field-qwen:binding:2"},
                ),
            ),
            status="supported",
        )
        memories = Memories(recollection, situation)
        lessons = memories.lessons()
        # the recollection's copy is not added to what the field woke
        self.assertEqual(
            [lesson.source_id for lesson in lessons], ["games:nethack:lesson:2"]
        )
        self.assertEqual(memories.woken(), 1)
        text = memories.prompt()
        self.assertIn("1. stairs down sit near the edge", text)
        self.assertNotIn("the kitten blocks corridors", text)
        self.assertIn("what is happening right now", text)
        self.assertEqual(memories.cited(1).text, "stairs down sit near the edge")
        self.assertIsNone(memories.cited(2))
        self.assertEqual(memories.as_dict()["situation"]["situations"], ["blocked"])
        self.assertEqual(memories.as_dict()["woken"], 1)

        # a set-aside memory is offered as its cue, and says so
        cue = Memories(
            recollection,
            Situation(
                situations=("blocked",),
                lessons=(
                    Lesson(
                        source_id="games:nethack:lesson:3",
                        text="do not push a locked door",
                        ref={"id": "field-qwen:binding:3"},
                        cue=True,
                    ),
                ),
                status="supported",
            ),
        )
        self.assertIn("(set aside earlier, kept as a cue)", cue.prompt())

        # nothing woken: the recollection stands in, so a decision is never blind
        fallback = Memories(recollection, Situation(situations=(), lessons=(), status="unresolved"))
        self.assertEqual(
            [lesson.source_id for lesson in fallback.lessons()],
            ["games:nethack:lesson:1", "games:nethack:lesson:2"],
        )
        self.assertEqual(fallback.woken(), 0)
        self.assertIn("from your own earlier lives", fallback.prompt())

        # and the list is capped, so judgement can select
        many = tuple(
            Lesson(
                source_id=f"games:nethack:lesson:{index}",
                text=f"lesson {index}",
                ref={"id": f"field-qwen:binding:{index}"},
            )
            for index in range(1, 9)
        )
        capped = Memories(
            recollection, Situation(situations=("blocked",), lessons=many, status="supported")
        )
        self.assertEqual(len(capped.lessons()), OFFER_LIMIT)

    def test_a_memory_is_as_loud_as_the_lives_that_acted_on_it(self) -> None:
        """What actually happened decides which memories are heard first.

        A verdict lives on the life that earned it: the field records which
        memories a use selected and how that use was assessed.  A memory never
        acted on is heard at the middle; one that has served rises, and one
        that led nowhere sinks.
        """

        def life(selected: tuple[str, ...], usefulness: float | None) -> dict:
            view: dict = {
                "use": {"payload": {"selected_refs": [{"id": key} for key in selected]}},
            }
            if usefulness is not None:
                view["assessment"] = {"payload": {"usefulness": usefulness}}
            return view

        episodes = [
            life(("lesson:1", "lesson:2"), 1.0),
            life(("lesson:1",), 1.0),
            life(("lesson:1",), 0.25),
            life(("lesson:3",), None),
        ]
        earned = standing_of("lesson:1", episodes)
        self.assertEqual(earned["verdicts"], 3)
        self.assertEqual(earned["usefulness"], 0.75)
        self.assertEqual(earned["priority"], 0.7)
        self.assertGreater(earned["priority"], DEFAULT_PRIORITY)

        # a lesson that only ever led nowhere sinks, and is heard last
        failed = standing_of("lesson:2", episodes)
        self.assertEqual(failed["verdicts"], 1)
        self.assertEqual(failed["usefulness"], 1.0)  # it was in a life that worked
        sunk = standing_of("lesson:4", [life(("lesson:4",), 0.0)])
        self.assertLess(sunk["priority"], DEFAULT_PRIORITY)

        # never acted on: heard at the middle, not assumed good or bad
        self.assertEqual(standing_of("lesson:9", episodes)["priority"], DEFAULT_PRIORITY)
        self.assertIsNone(standing_of("lesson:9", episodes)["usefulness"])
        # an unsettled life is not a verdict
        self.assertEqual(standing_of("lesson:3", episodes)["verdicts"], 0)

    def test_a_life_opens_with_the_lives_before_it(self) -> None:
        """The lives are read back, so a life knows where it stands."""

        text = briefing_prompt(
            {"lives": 8, "deepest": 2, "lessons": 4, "recent": ["a life against a kitten"]}
        )
        self.assertIn("life number 9", text)
        self.assertIn("deepest was level 2", text)
        self.assertIn("4 lessons", text)
        self.assertIn("a life against a kitten", text)
        self.assertEqual(briefing_prompt({"lives": 0, "lessons": 0}), "")
        self.assertEqual(briefing_prompt(None), "")

    def test_a_question_the_mind_asked_is_answered_first(self) -> None:
        """The mind may reach for a memory, and the answer leads the list.

        A question the mind asked itself is the most specific thing it knows
        about what it needs, so the field's answer is shown before the memories
        the moment woke -- and the numbering still lets it say which one decided
        the action.
        """

        recollection = self._recollection()
        asked = Lesson(
            source_id="games:nethack:lesson:7",
            text="a door you cannot open is worth a key, not a shoulder",
            ref={"id": "field-qwen:binding:7"},
        )
        waking = Lesson(
            source_id="games:nethack:lesson:8",
            text="the stairs down sit near the edge",
            ref={"id": "field-qwen:binding:8"},
        )
        memories = Memories(
            recollection,
            Situation(situations=("blocked",), lessons=(waking,), status="supported"),
            asking=Asking(question="anything about doors", lessons=(asked,), status="supported"),
        )
        self.assertEqual(memories.sought(), 1)
        self.assertEqual(memories.lessons()[0].source_id, asked.source_id)
        self.assertEqual(memories.lessons()[1].source_id, waking.source_id)
        text = memories.prompt()
        self.assertIn('You asked the field: "anything about doors"', text)
        self.assertIn("the first 1 memory below", text)
        self.assertLess(text.index(asked.text), text.index(waking.text))
        self.assertEqual(memories.cited(1).source_id, asked.source_id)

        # the field had nothing: the mind is told, and is shown what it has
        empty = Memories(
            recollection,
            Situation(situations=("blocked",), lessons=(waking,), status="supported"),
            asking=Asking(question="anything about doors", status="unresolved"),
        )
        self.assertEqual(empty.sought(), 0)
        self.assertIn("It had nothing about that", empty.prompt())
        self.assertEqual(empty.lessons(), (waking,))

    def test_a_set_aside_memory_comes_back_as_its_cue(self) -> None:
        """A demoted memory is still usable: the words are kept as a cue."""

        text, cue = _lesson_text({"lesson": "step around the kitten"})
        self.assertEqual((text, cue), ("step around the kitten", False))
        text, cue = _lesson_text(
            {"memory_summary": {"cue": "do not push a locked door", "kind": "lesson"}}
        )
        self.assertEqual((text, cue), ("do not push a locked door", True))
        self.assertEqual(_lesson_text({}), ("", False))

    def test_a_lesson_that_led_nowhere_twice_is_set_aside(self) -> None:
        autobiography = {
            "episodes": [
                {
                    "use": {"payload": {"selected_refs": [{"id": "b1"}, {"id": "b2"}]}},
                    "assessment": {"payload": {"usefulness": 0.0}},
                },
                {
                    "use": {"payload": {"selected_refs": [{"id": "b1"}]}},
                    "assessment": {"payload": {"usefulness": 0.0}},
                },
                {
                    "use": {"payload": {"selected_refs": [{"id": "b2"}]}},
                    "assessment": {"payload": {"usefulness": 1.0}},
                },
                {
                    "use": {"payload": {"selected_refs": [{"id": "b3"}]}},
                    "assessment": {"payload": {"usefulness": 0.0}},
                },
            ]
        }
        self.assertEqual(hopeless_lessons(autobiography), ["b1"])
        self.assertEqual(hopeless_lessons(autobiography, threshold=1), ["b1", "b2", "b3"])

    def test_the_reflection_reads_a_lesson_with_or_without_its_moment(self) -> None:
        bare = _reflected_lessons({"lessons": ["bump walls less often"]})
        self.assertEqual(bare[0].text, "bump walls less often")
        self.assertEqual(bare[0].when, ("always",))
        named = _reflected_lessons(
            {
                "lessons": [
                    {"lesson": "step around the pet", "when": ["blocked", "monster"]},
                    {"lesson": "drink when hurt", "when": "hurt"},
                    {"lesson": "nonsense moment", "when": ["whenever"]},
                ]
            }
        )
        self.assertEqual(named[0].when, ("blocked", "monster"))
        self.assertEqual(named[1].when, ("hurt",))
        self.assertEqual(named[2].when, ("always",))
        self.assertEqual(_reflected_lessons({"lessons": []}), ())
        self.assertEqual(_reflected_lessons({}), ())

    def test_the_lessons_a_life_cited_are_counted_once_each(self) -> None:
        journal = [
            {"turn": 1, "used": 1, "used_id": "lesson:kitten", "used_text": "the kitten blocks corridors"},
            {"turn": 2, "used": 0, "used_id": "", "used_text": ""},
            {"turn": 3, "used": 1, "used_id": "lesson:kitten", "used_text": "the kitten blocks corridors"},
            {"turn": 4, "used": 2, "used_id": "lesson:stairs", "used_text": "stairs down sit near the edge"},
        ]
        self.assertEqual(
            lesson_use(journal),
            [
                ("lesson:kitten", "the kitten blocks corridors"),
                ("lesson:stairs", "stairs down sit near the edge"),
            ],
        )
        # a citation that names no memory is not a citation
        self.assertEqual(lesson_use([{"turn": 1, "used": 1, "used_text": "something"}]), [])

    def test_a_life_without_a_field_still_settles_its_outcome(self) -> None:
        journal = [
            {"turn": 1, "depth": 1, "label": "move east", "cell": [4, 5], "note": ""},
            {"turn": 2, "depth": 2, "label": "descend", "cell": [4, 7], "note": ""},
        ]
        section = close_life(
            memory=NO_MEMORY,
            recollection=NO_MEMORY.recall("about to play"),
            journal=journal,
            observation=self._observation(turn=2),
            dungeon=None,
            player=ScriptedExplorer(),
            life="life-1",
            start_depth=1,
        )
        self.assertEqual(section["mode"], "none")
        self.assertEqual(len(section["uses"]), 1)
        self.assertFalse(section["uses"][0]["settled"])
        self.assertEqual(section["written"], {"lessons": [], "life": None})
        self.assertTrue(section["outcome"]["descended"])
        self.assertEqual(section["usefulness"], 1.0)


def _field_unavailable() -> str:
    """Why the real field cannot be used here, or nothing when it can.

    A skip that does not say why is a hole in the suite, so the reason travels
    with it: a missing workbench and a broken one are different facts.
    """
    try:
        import cassi_field_qwen_workbench  # noqa: F401
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return ""


_FIELD_GAP = _field_unavailable()


@unittest.skipIf(_FIELD_GAP, f"the field workbench is unavailable ({_FIELD_GAP})")
class LivingFieldTest(unittest.TestCase):
    """The seam against the real field: remembered, recalled, used, settled."""

    def test_a_lesson_survives_a_restart_and_settles_with_its_outcome(self) -> None:
        with TemporaryDirectory() as directory:
            home = Path(directory) / "field-home"
            memory = GameMemory(home)
            try:
                memory.remember_lesson(
                    "the kitten blocks corridors; step around it", depth=1, life="life-1"
                )
                recollection = memory.recall("about to play", label="life-1:recall")
                self.assertEqual(recollection.status, "supported")
                self.assertEqual(len(recollection.lessons), 1)
                self.assertIn("kitten", recollection.lessons[0].text)
                used = recollection.cited(1)
                self.assertIsNotNone(used)
                episode = memory.used(
                    recollection,
                    consumer={"kind": "nethack-life", "life": "life-1"},
                    lessons=[used],
                    label="life-1:use",
                )
                self.assertIsNotNone(episode)
            finally:
                memory.close()
            # the outcome is settled by the next session, as the design intends
            again = GameMemory(home)
            try:
                settled = again.settle(
                    episode=episode,
                    outcome_id="life-1:outcome",
                    consequence={"kind": "life-ended", "depth": 2},
                    usefulness=1.0,
                    renewal={"strength": 1.0, "reason": "the lesson held"},
                    label="life-1:outcome",
                )
                self.assertTrue(settled["lifecycle"]["settled"])
                autobiography = again.autobiography(limit=4)
                self.assertEqual(len(autobiography["episodes"]), 1)
                self.assertEqual(autobiography["unresolved"], 0)
                written = again.remember_life(
                    "life-1 went down a level and died on level 2",
                    life="life-1",
                    depth=2,
                    turns=143,
                )
                self.assertTrue(written)
            finally:
                again.close()

    def test_a_lesson_wakes_when_its_situation_holds_and_stays_quiet_when_it_does_not(self) -> None:
        with TemporaryDirectory() as directory:
            memory = GameMemory(Path(directory) / "field-home")
            try:
                memory.remember_lesson("step around the pet instead of bumping it", depth=1)
                lesson = memory.recall("after the lesson", label="words").lessons[0]
                self.assertTrue(lesson.ref)
                self.assertEqual(memory.register_lesson(lesson, ("blocked",), label="when"), 1)
                blocked = memory.match(
                    context={"blocked": True},
                    situations=("blocked",),
                    event_id="turn:1",
                    label="turn:1",
                )
                self.assertEqual(blocked.status, "supported")
                self.assertEqual([row.text for row in blocked.lessons], [lesson.text])
                # the same condition, in a situation it is not about
                calm = memory.match(
                    context={"blocked": False},
                    situations=("exploring",),
                    event_id="turn:2",
                    label="turn:2",
                )
                self.assertEqual(calm.lessons, ())
                self.assertEqual(calm.candidates, 1)
                # and the memory still knows its own state afterwards
                awareness = memory.awareness(label="after")
                self.assertTrue(awareness)
                maintenance = memory.maintain(purpose="test", label="test")
                self.assertTrue(maintenance)
            finally:
                memory.close()

    def test_a_filed_situation_wakes_after_reopening_the_field(self) -> None:
        with TemporaryDirectory() as directory:
            home = Path(directory) / "field-home"
            memory = GameMemory(home)
            try:
                memory.remember_lesson("explore beyond the first room", depth=1)
                reading = memory.recall("file exploration", label="file-exploration")
                lesson = reading.lessons[0]
                memory.unused(reading, reason="filed for later", label="file-exploration:read")
                memory.register_lesson(lesson, ("exploring",), label="when-exploring")
            finally:
                memory.close()
            again = GameMemory(home)
            try:
                matched = again.match(
                    context={"always": True, "exploring": True},
                    situations=("always", "exploring"),
                    event_id="next-life:first-turn",
                    label="next-life:first-turn",
                )
                self.assertEqual(
                    [row.source_id for row in matched.lessons],
                    [lesson.source_id],
                    repr(matched),
                )
            finally:
                again.close()


    def test_situational_memory_used_without_global_startup_recall(self) -> None:
        """A woken lesson alone can earn a settled life verdict."""
        with TemporaryDirectory() as directory:
            memory = GameMemory(Path(directory) / "field-home")
            try:
                memory.remember_lesson("step around the pet", depth=1)
                initial = memory.recall("file the lesson", label="file-lesson")
                lesson = initial.lessons[0]
                memory.unused(initial, reason="only read to file", label="file-lesson:read")
                memory.register_lesson(lesson, ("blocked",), label="when-blocked")
                matched = memory.match(
                    context={"blocked": True},
                    situations=("blocked",),
                    event_id="first-block",
                    label="first-block",
                )
                self.assertEqual([row.source_id for row in matched.lessons], [lesson.source_id])
                journal = [
                    {
                        "turn": turn, "depth": 1, "label": "move west",
                        "cell": [4, turn], "note": "",
                        "used": 1 if turn == 1 else 0,
                        "used_id": lesson.source_id if turn == 1 else "",
                        "used_text": lesson.text if turn == 1 else "",
                    }
                    for turn in range(1, 6)
                ]
                section = close_life(
                    memory=memory,
                    recollection=NO_MEMORY.recall("before the life"),
                    situational_lessons=matched.lessons,
                    journal=journal,
                    observation=None,
                    dungeon=None,
                    player=ScriptedExplorer(),
                    life="matched-life",
                    start_depth=1,
                )
                self.assertEqual(section["uses"][-1]["lessons"], [lesson.source_id])
                self.assertTrue(section["uses"][-1]["settled"])
                self.assertEqual(section["verdicts"][0]["source_id"], lesson.source_id)
                self.assertEqual(section["verdicts"][0]["earned"], 0.25)
                self.assertEqual(memory.autobiography(limit=4)["unresolved"], 0)
                self.assertFalse(any(row["when"] == ["always"] for row in section["conditions_registered"]))
            finally:
                memory.close()

    def test_every_lesson_a_life_acted_on_is_credited_in_the_one_verdict(self) -> None:
        """The recollection accepts one use, and the field credits every lesson.

        The use a life's outcome settles carries all the lessons it acted on,
        so the per-lesson detail lives in the field's own verdict: after the
        life is settled, each lesson it leaned on shows a verdict of its own,
        with the count of decisions that leaned on it.
        """

        with TemporaryDirectory() as directory:
            memory = GameMemory(Path(directory) / "field-home")
            try:
                memory.remember_lesson("step around the pet instead of bumping it", depth=1)
                memory.remember_lesson("the stairs down sit near the edge", depth=1)
                recollection = memory.recall("about to play", label="life-1:recall")
                first, second = recollection.lessons
                journal = [
                    {"turn": 1, "depth": 1, "label": "move east", "cell": [4, 5], "note": ""},
                    {"turn": 2, "depth": 1, "label": "move east", "cell": [4, 6], "note": ""},
                    {"turn": 3, "depth": 1, "label": "move south", "cell": [4, 7], "note": ""},
                    {"turn": 4, "depth": 1, "label": "move south", "cell": [5, 7], "note": ""},
                    {"turn": 5, "depth": 1, "label": "move south", "cell": [6, 7], "note": ""},
                ]
                for row in journal[:2]:
                    row["used"], row["used_text"], row["used_id"] = 1, first.text, first.source_id
                journal[2]["used"], journal[2]["used_text"], journal[2]["used_id"] = (
                    2,
                    second.text,
                    second.source_id,
                )
                section = close_life(
                    memory=memory,
                    recollection=recollection,
                    journal=journal,
                    observation=None,
                    dungeon=None,
                    player=ScriptedExplorer(),
                    life="life-1",
                    start_depth=1,
                )
                self.assertEqual(len(section["uses"]), 1)
                self.assertTrue(section["uses"][0]["settled"])
                self.assertEqual(
                    section["uses"][0]["lessons"], [first.source_id, second.source_id]
                )
                verdicts = section["verdicts"]
                self.assertEqual(len(verdicts), 2)
                # a citation is a decision the lesson was said to decide, and
                # repeating the same decision is the same citation
                self.assertEqual(
                    {row["source_id"]: row["cited"] for row in verdicts},
                    {first.source_id: 1, second.source_id: 1},
                )
                self.assertTrue(all(row["settled"] for row in verdicts))
                self.assertTrue(all(row["verdicts"] == 1 for row in verdicts))
                self.assertTrue(all(row["earned"] == 0.25 for row in verdicts))
                # and the field's own reading of each lesson agrees
                for lesson in (first, second):
                    earned = memory.standing(lesson)
                    self.assertEqual(earned["verdicts"], 1, lesson.source_id)
                    self.assertEqual(earned["usefulness"], 0.25)
            finally:
                memory.close()

    def test_a_lesson_that_served_is_offered_before_one_that_did_not(self) -> None:
        """Standing decides the order, so what worked is heard first.

        Two lives lean on two lessons: the first goes nowhere, the second
        reaches further.  The lesson that served was written second, so a field
        that ignored what happened would offer the failed lesson first.
        """

        def live(memory: GameMemory, life: str, number: int, turns: int) -> Mapping[str, Any]:
            recollection = memory.recall("about to play", label=f"{life}:recall")
            lesson = recollection.cited(number)

            class Reflecting(ScriptedExplorer):
                """A walker that looks back and says what the life taught."""

                def reflect(self, *, story, outcome, depth, turns, remembered=""):
                    return (
                        tuple(
                            ReflectedLesson(row.text, ("blocked",), 0)
                            for row in recollection.lessons
                        ),
                        f"{life} ended at depth {depth}",
                    )

            journal = [
                {
                    "turn": turn,
                    "depth": 1,
                    "label": "move east",
                    "cell": [4, 4 + turn],
                    "note": "",
                    "used": number,
                    "used_text": lesson.text,
                    "used_id": lesson.source_id,
                }
                for turn in range(1, turns + 1)
            ]
            return close_life(
                memory=memory,
                recollection=recollection,
                journal=journal,
                observation=None,
                dungeon=None,
                player=Reflecting(),
                life=life,
                start_depth=1,
            )

        with TemporaryDirectory() as directory:
            memory = GameMemory(Path(directory) / "field-home")
            try:
                memory.remember_lesson("bump into the pet and get nowhere", depth=1)
                memory.remember_lesson("the kitten blocks corridors; step around it", depth=1)
                looking = memory.recall("about to play", label="life-0:recall")
                failed, served = looking.lessons[0], looking.lessons[1]
                self.assertLess(failed.source_id, served.source_id)
                # a life that barely started, leaning on the first lesson
                first = live(memory, "life-1", 1, turns=3)
                self.assertEqual(first["verdicts"][0]["earned"], 0.0)
                # a life that moved, leaning on the second
                second = live(memory, "life-2", 2, turns=6)
                self.assertEqual(second["verdicts"][0]["earned"], 0.25)
                self.assertLess(
                    first["standing"][failed.source_id]["priority"],
                    second["standing"][served.source_id]["priority"],
                )
                # both are filed against a moment, and the field says which
                # of them it wakes first when that moment comes
                woken = memory.match(
                    context={"blocked": True},
                    situations=("blocked",),
                    event_id="life-3:turn:1",
                    label="life-3:turn:1",
                )
                self.assertEqual(woken.status, "supported")
                self.assertGreaterEqual(len(woken.lessons), 2)
                self.assertEqual(
                    woken.lessons[0].source_id,
                    served.source_id,
                    "the lesson that served is heard first",
                )
            finally:
                memory.close()

    def test_a_memory_the_mind_asked_for_earns_its_verdict(self) -> None:
        """What was asked for is credited like anything else that was used.

        The life asked a question and acted on the answer, so the seek is its
        own recollection with its own verdict -- and the recollection the life
        was handed, which no decision cited, is settled as unused rather than
        left open or credited for work it did not do.
        """

        with TemporaryDirectory() as directory:
            memory = GameMemory(Path(directory) / "field-home")
            try:
                memory.remember_lesson("a door you cannot open is worth a key", depth=1)
                memory.remember_lesson("the kitten blocks the corridors you need", depth=1)
                handed = memory.recall("about to play", label="life-1:recall")
                asked = memory.recall("anything about doors", label="life-1:ask")
                lesson = asked.lessons[0]

                journal = [
                    {
                        "turn": turn,
                        "depth": 1,
                        "label": "move east",
                        "cell": [4, 4 + turn],
                        "note": "",
                        "used": 1,
                        "used_text": lesson.text,
                        "used_id": lesson.source_id,
                    }
                    for turn in range(1, 6)
                ]
                section = close_life(
                    memory=memory,
                    recollection=handed,
                    journal=journal,
                    seeks=(("anything about doors", asked),),
                    observation=None,
                    dungeon=None,
                    player=ScriptedExplorer(),
                    life="life-1",
                    start_depth=1,
                )
                self.assertEqual(len(section["uses"]), 2)
                sought, unused = section["uses"]
                # what the mind asked for is credited first, and earns its
                # verdict; what it was handed carried nothing this life used
                self.assertIn("anything about doors", str(sought["what"]))
                self.assertEqual(sought["lessons"], [lesson.source_id])
                self.assertTrue(sought["settled"])
                self.assertTrue(sought["episode_id"])
                self.assertEqual(unused["what"], "what the life was handed")
                self.assertEqual(unused["lessons"], [])
                self.assertFalse(unused["settled"])
                self.assertIn("credited", str(unused.get("unused")))
                # the sought lesson earned the verdict, and only once
                verdicts = section["verdicts"]
                self.assertEqual([row["source_id"] for row in verdicts], [lesson.source_id])
                self.assertEqual(verdicts[0]["verdicts"], 1)
                self.assertEqual(verdicts[0]["earned"], 0.25)
                # the life cited the one lesson, in five decisions
                self.assertEqual(verdicts[0]["cited"], 1)
                # and the question itself is in the receipt
                self.assertEqual(
                    [row["question"] for row in section["seeks"]], ["anything about doors"]
                )
                self.assertIn(lesson.text[:160], section["seeks"][0]["lessons"])
            finally:
                memory.close()

    def test_a_life_leaves_no_recollection_open(self) -> None:
        """A life reads the field twice and settles both readings.

        An unsettled recollection is unresolved work the mind carries for the
        rest of its life, so every look the game takes has to end in a use or a
        set-aside -- including the look it takes to file what it just learned.
        """

        class ReflectingWalker(ScriptedExplorer):
            """A walker that can look back, so a life writes a lesson."""

            def reflect(self, *, story, outcome, depth, turns, remembered=""):
                return (
                    (ReflectedLesson("step around the kitten rather than into it", ("monster",), 0),),
                    "a short life against a kitten",
                )

        with TemporaryDirectory() as directory:
            memory = GameMemory(Path(directory) / "field-home")
            try:
                memory.remember_lesson(
                    "the kitten blocks corridors; step around it", depth=1, life="life-1"
                )
                memory.remember_life("life-0 got nowhere", life="life-0", depth=1, turns=4)
                # the run's own order: where the lives stand, then what is known
                memory.briefing(label="life-1:briefing")
                recollection = memory.recall("about to play", label="life-1:recall")
                section = close_life(
                    memory=memory,
                    recollection=recollection,
                    journal=[
                        {"turn": 1, "depth": 1, "label": "move east", "cell": [4, 5], "note": ""},
                        {"turn": 2, "depth": 1, "label": "move east", "cell": [4, 6], "note": ""},
                    ],
                    observation=None,
                    dungeon=None,
                    player=ReflectingWalker(),
                    life="life-1",
                    start_depth=1,
                )
                self.assertEqual(len(section["written"]["lessons"]), 1)
                # every reading settled: the one the life acted on, the one the
                # briefing took of the lives, and the one it took afterwards to
                # file the new lesson against its moment
                self.assertEqual(memory.autobiography(limit=4)["unresolved"], 0)
                self.assertGreaterEqual(section["counters"]["cancels"], 2)
            finally:
                memory.close()


class SecondWorldTest(unittest.TestCase):
    """A game that is not NetHack drives the whole seam, watch page included."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._dir = TemporaryDirectory()
        cls.program = Path(cls._dir.name) / "toy_game.py"
        cls.program.write_text(TOY_GAME, encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._dir.cleanup()

    def test_a_life_in_another_game(self) -> None:
        world = _ToyWorld(self.program)
        try:
            observation = world.reset()
            self.assertIn("@", "\n".join(observation.screen))
            self.assertEqual(observation.summary["gold"], 0)
            self.assertEqual(observation.summary["moves"], 0)

            stepped = world.act(Action(key="l", keys="l", label="move east"))
            self.assertIs(stepped.observation.summary["moved"], True)
            self.assertEqual(stepped.observation.summary["moves"], 1)

            world.act(Action(key="j", keys="j", label="move south"))
            for _ in range(2):
                taken = world.act(Action(key="l", keys="l", label="move east"))
            self.assertEqual(taken.observation.summary["gold"], 1)
            self.assertEqual(taken.note, "You take the gold.")

            html = render_screen(taken.observation.screen, _ToyWorld.PROSE_ROWS)
            self.assertIn('class="me"', html)
            self.assertIn("item gold", html)
            self.assertIn("You take the gold.", html)
        finally:
            world.close()

    def test_the_toy_game_can_be_watched_by_the_same_page(self) -> None:
        world = _ToyWorld(self.program)
        view = WatchView(port=0, title="toy")
        try:
            observation = world.reset()
            url = view.start()
            view.publish(
                screen=observation.screen,
                stats={"gold": observation.summary["gold"]},
                message=str(observation.summary["message"]),
                status="toy",
                decision={"label": "wait", "reason": "testing the page"},
                journal=[{"turn": 1, "label": "wait", "reason": "testing the page"}],
            )
            served = urllib.request.urlopen(f"{url}state", timeout=10).read().decode("utf-8")
            payload = json.loads(served)
            self.assertEqual(payload["stats"]["gold"], 0)
            self.assertIn("toy", payload["title"])
        finally:
            view.stop()
            world.close()


if __name__ == "__main__":
    unittest.main()

