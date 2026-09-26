"""Agents authoring stations, judged by whether the station discriminates.

The last station of the course turns the instrument around.  Instead of
answering a station, the agent *builds* one: it names a law to hide, chooses
the observations that must betray it and the writes whose lifetimes the station
will ask about.  The judge does not read the proposal as prose.  It builds the
world the proposal describes, runs the real course on it with three readers,
and accepts the station only when the honest reader passes and both failing
readers are refused:

``honest``
    identifies by simulation, so a station it cannot pass is a station whose
    declared parts do not decide anything.

``misattributing``
    identifies honestly and then names the runner-up law.  Its measurement is
    real and its forecast is a real forecast of the wrong law, so a station
    that cannot catch it is not testing attribution at all.

``unexecuted``
    guesses without running anything.

A proposal can therefore be *rejected for a reason it can be told*: too little
separation, an instrument that cannot read its own observation, a menu whose
lifetimes do not carry the law, or a canary that slips through.  Everything is
declared: the vocabulary of parts, the laws, and the acceptance rule.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Mapping, Sequence

from laboratory import hidden as hidden_module
from laboratory import stations as stations_module
from laboratory.course import Course, ScriptedAgent
from laboratory.hidden import HiddenWorld
from laboratory.stations import LaboratoryError, Station

PROPOSAL_SCHEMA = "cassi.laboratory.station-proposal.v1"
AUTHORING_CANARY_SCHEMA = "cassi.laboratory.authoring-canary.v1"
AUTHORING_SCHEMA = "cassi.laboratory.authoring.v1"

AUTHOR_READERS: tuple[str, ...] = ("honest", "misattributing", "unexecuted")

# --------------------------------------------------------------------------- #
# declared vocabulary of parts
# --------------------------------------------------------------------------- #

AUTHOR_OBSERVATIONS: tuple[dict[str, Any], ...] = (
    {
        "recipe_id": "uniform-pair",
        "family": "uniform-pair",
        "parameters": {"psi_y": 1.2, "psi_i": 0.4},
        "steps_observed": 600,
        "sample_every": 50,
        "full_field": False,
    },
    {
        "recipe_id": "gaussian-pair",
        "family": "gaussian-pair",
        "parameters": {
            "psi_y_amplitude": 0.9, "psi_y_center": 8.0, "psi_y_width": 1.5,
            "psi_i_amplitude": 0.25, "psi_i_center": 10.5, "psi_i_width": 2.0,
        },
        "steps_observed": 600,
        "sample_every": 50,
        "full_field": True,
    },
    {
        "recipe_id": "counterflow-packet",
        "family": "counterflow-packet",
        "parameters": {"amplitude": 0.8, "width": 2.5, "center": 11.5, "speed": 0.4},
        "steps_observed": 600,
        "sample_every": 50,
        "full_field": True,
    },
    {
        "recipe_id": "conversion-blob",
        "family": "conversion-blob",
        "parameters": {"amplitude": 1.0, "width": 2.0, "center": 11.5},
        "steps_observed": 600,
        "sample_every": 50,
        "full_field": True,
    },
)

AUTHOR_MENU: tuple[dict[str, Any], ...] = hidden_module.DEFAULT_RETENTION_MENU


def _vocabulary_document(parts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **hidden_module.recipe_document(part["recipe_id"], part["family"], part["parameters"]),
            **{
                key: part[key]
                for key in ("steps_observed", "sample_every", "full_field")
                if key in part
            },
        }
        for part in parts
    ]


def observation_vocabulary() -> list[dict[str, Any]]:
    return _vocabulary_document(AUTHOR_OBSERVATIONS)


def menu_vocabulary() -> list[dict[str, Any]]:
    return _vocabulary_document(AUTHOR_MENU)


def _part(parts: Sequence[Mapping[str, Any]], recipe_id: str, *, kind: str) -> dict[str, Any]:
    for part in parts:
        if str(part["recipe_id"]) == str(recipe_id):
            return dict(part)
    declared = [str(part["recipe_id"]) for part in parts]
    raise LaboratoryError(f"unknown {kind} {recipe_id!r}; declared parts are {declared}")


# --------------------------------------------------------------------------- #
# proposals
# --------------------------------------------------------------------------- #


def parse_proposal(proposal: Mapping[str, Any]) -> dict[str, Any]:
    """Read a proposal against the declared vocabulary."""

    if not isinstance(proposal, Mapping):
        raise LaboratoryError("a proposal must be an object")
    law_id = str(proposal.get("law_id", "")).strip()
    hidden_module.law_by_id(hidden_module.LAW_MENU, law_id)
    observation_ids = proposal.get("observation_recipe_ids")
    menu_ids = proposal.get("retention_menu_ids")
    if not isinstance(observation_ids, Sequence) or isinstance(observation_ids, (str, bytes)):
        raise LaboratoryError("observation_recipe_ids must be a list")
    if not isinstance(menu_ids, Sequence) or isinstance(menu_ids, (str, bytes)):
        raise LaboratoryError("retention_menu_ids must be a list")
    if not observation_ids:
        raise LaboratoryError("a station needs at least one observation recipe")
    if not menu_ids:
        raise LaboratoryError("a station needs at least one write in its menu")
    observations = [_part(AUTHOR_OBSERVATIONS, str(item), kind="observation recipe") for item in observation_ids]
    menu = [_part(AUTHOR_MENU, str(item), kind="menu recipe") for item in menu_ids]
    return {
        "title": str(proposal.get("title", "")).strip() or "an authored station",
        "law_id": law_id,
        "reason": str(proposal.get("reason", "")).strip(),
        "observations": observations,
        "menu": menu,
    }


def build_authored_world(base: HiddenWorld, parsed: Mapping[str, Any]) -> HiddenWorld:
    """The world the proposal describes, with the base world's laws and chain."""

    digest = hashlib.sha256(
        json.dumps(
            {
                "law_id": parsed["law_id"],
                "observations": [item["recipe_id"] for item in parsed["observations"]],
                "menu": [item["recipe_id"] for item in parsed["menu"]],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:8]
    return hidden_module.hidden_world(
        true_law_id=str(parsed["law_id"]),
        laws=base.laws,
        node_count=base.complex.node_count,
        dt=base.dt,
        variant=f"authored-{str(parsed['law_id']).split('-')[0]}-{digest}",
        observations=parsed["observations"],
        retention_menu=parsed["menu"],
        retention=base.retention,
        forecast_steps=base.forecast_steps,
    )


# --------------------------------------------------------------------------- #
# readers used to test an authored station
# --------------------------------------------------------------------------- #


def authoring_answerer(name: str) -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    if name == "honest":
        return hidden_module.competent_agent()
    if name == "misattributing":
        return hidden_module.misattributing_agent()
    if name == "unexecuted":
        return hidden_module.shortcut_agent()
    raise LaboratoryError(f"unknown authoring reader {name!r}")


def run_authored_station(
    world: HiddenWorld,
    *,
    receipt_dir: str | None = None,
    deadline_s: float = 900.0,
) -> dict[str, Any]:
    """Run the authored world's own course with one scripted reader per canary."""

    runs: dict[str, Any] = {}
    for name in AUTHOR_READERS:
        agent = ScriptedAgent(answerer=authoring_answerer(name), kind=f"authoring-{name}")
        receipt = Course(
            world,
            world.stations(),
            level="hidden",
            world_block=world.declared_world(),
            title=world.title(),
        ).run(
            agent,
            receipt_path=None if receipt_dir is None else f"{receipt_dir}/{world.variant}-{name}.json",
            deadline_s=deadline_s,
        )
        failures = {
            item["station"]: [
                check["name"] for check in item.get("checks", []) if not check.get("ok")
            ]
            for item in receipt["stations"]
            if item.get("verdict") != "pass"
        }
        controls = {
            item["station"]: [
                {"name": control["name"], "ok": bool(control["ok"])}
                for control in item.get("controls", [])
            ]
            for item in receipt["stations"]
        }
        runs[name] = {
            "verdict": receipt["verdict"],
            "station_verdicts": receipt["station_verdicts"],
            "failed_checks": failures,
            "controls": controls,
            "digest": receipt["digest"],
        }
    return runs


# --------------------------------------------------------------------------- #
# the judge
# --------------------------------------------------------------------------- #


def judge_authoring(base: HiddenWorld, proposal: Mapping[str, Any]) -> dict[str, Any]:
    """Build the proposed station, test it with three readers, accept or reject."""

    checks: list[dict[str, Any]] = []
    try:
        parsed = parse_proposal(proposal)
    except LaboratoryError as error:
        checks.append(
            {
                "name": "the proposal uses only declared parts",
                "ok": False,
                "detail": str(error),
                "numbers": {},
            }
        )
        return stations_module._report(
            "authoring",
            "fail",
            checks,
            [],
            {"declared_laws": [law["law_id"] for law in base.laws]},
            ["a proposal that is not made of declared parts cannot be built at all"],
        )

    checks.append(
        {
            "name": "the proposal uses only declared parts",
            "ok": True,
            "detail": json.dumps(
                {
                    "law_id": parsed["law_id"],
                    "observations": [item["recipe_id"] for item in parsed["observations"]],
                    "menu": [item["recipe_id"] for item in parsed["menu"]],
                },
                sort_keys=True,
            ),
            "numbers": {"observation_count": len(parsed["observations"]), "menu_count": len(parsed["menu"])},
        }
    )

    world = build_authored_world(base, parsed)
    runs = run_authored_station(world)

    honest = runs["honest"]
    checks.append(
        {
            "name": "the authored station accepts the honest reader",
            "ok": honest["verdict"] == "pass",
            "detail": (
                "an honest reader identifies by simulation and forecasts from the law it named; "
                f"its failed checks were {json.dumps(honest['failed_checks'], sort_keys=True)}"
            ),
            "numbers": {"station_verdicts": honest["station_verdicts"]},
        }
    )
    for name, label in (
        ("misattributing", "refuses the reader that names the runner-up law"),
        ("unexecuted", "refuses the reader that runs nothing"),
    ):
        checks.append(
            {
                "name": f"the authored station {label}",
                "ok": runs[name]["verdict"] != "pass",
                "detail": json.dumps(runs[name]["failed_checks"], sort_keys=True),
                "numbers": {"station_verdicts": runs[name]["station_verdicts"]},
            }
        )

    # the design controls are claim-free by construction, so the honest reader's
    # report is the authored world's own statement about itself
    design_controls = [
        control
        for station_id in ("identification", "retention")
        for control in runs["honest"]["controls"].get(station_id, [])
    ]
    failing_controls = [item for item in design_controls if not item["ok"]]
    checks.append(
        {
            "name": "the authored world's own controls hold",
            "ok": not failing_controls,
            "detail": json.dumps(failing_controls, sort_keys=True),
            "numbers": {"failing_controls": len(failing_controls)},
        }
    )

    verdict = "pass" if all(bool(item["ok"]) for item in checks) else "fail"
    return stations_module._report(
        "authoring",
        verdict,
        checks,
        [
            {
                "name": "the station is tested by running it, not by reading it",
                "ok": True,
                "detail": (
                    "the judge builds the proposed world and runs the real course on it with "
                    "three scripted readers"
                ),
            }
        ],
        {
            "proposal": {
                "title": parsed["title"],
                "law_id": parsed["law_id"],
                "observation_recipe_ids": [item["recipe_id"] for item in parsed["observations"]],
                "retention_menu_ids": [item["recipe_id"] for item in parsed["menu"]],
                "reason": parsed["reason"],
            },
            "authored_world": {
                "variant": world.variant,
                "fixture_id": world.fixture_id(),
                "measured_recipe_id": world.measurement_recipe_id,
                "true_lifetimes": world.retention_lifetimes(),
            },
            "readers": runs,
            "design_controls": design_controls,
        },
        [
            "an authored station is accepted only when it can tell an honest reader from a wrong one",
            "every rejection reason is a check in this report",
        ],
    )


# --------------------------------------------------------------------------- #
# the station
# --------------------------------------------------------------------------- #


def proposal_shape() -> dict[str, Any]:
    return {
        "schema": PROPOSAL_SCHEMA,
        "title": "a short name for the station",
        "law_id": "one declared candidate law",
        "observation_recipe_ids": ["one or more declared observation recipes"],
        "retention_menu_ids": ["one or more declared menu recipes"],
        "reason": "why this station should discriminate",
    }


def brief_authoring(base: HiddenWorld) -> dict[str, Any]:
    return {
        "station": "authoring",
        "level": "authoring",
        "fixture_id": base.fixture_id(),
        "world": base.declared_world(),
        "vocabulary": {
            "observation_recipes": observation_vocabulary(),
            "retention_menu": menu_vocabulary(),
            "note": (
                "the first observation recipe is the one the declared instrument measures, so "
                "its shipped series has to be a single tone"
            ),
        },
        "question": (
            "Author one station of your own: name the law to hide, choose the observation "
            "recipes that must betray it and the writes whose lifetimes the station will ask "
            "about. The judge builds your world, runs the real course on it, and accepts the "
            "station only when an honest reader passes while a reader that names the runner-up "
            "law and a reader that runs nothing are both refused."
        ),
        "evidence": proposal_shape(),
        "acceptance": (
            "accept = honest reader passes, both failing readers are refused, and the authored "
            "world's own controls (a readable instrument, separated candidates, distinct "
            "lifetimes that carry the law) all hold"
        ),
    }


def authoring_station(base: HiddenWorld) -> Station:
    def bound(context: Any, evidence: Mapping[str, Any]) -> dict[str, Any]:
        return judge_authoring(context.fixture, evidence)

    return Station(
        "authoring",
        "A station of your own",
        PROPOSAL_SCHEMA,
        brief_authoring(base),
        bound,
        kind="authoring",
    )


def authoring_mission(base: HiddenWorld) -> dict[str, Any]:
    return stations_module.mission_document(
        base,
        (authoring_station(base),),
        level="authoring",
        world=base.declared_world(),
        title=f"The Shifting Laboratory — authoring on {base.variant}",
    )


# --------------------------------------------------------------------------- #
# reference proposals and the authoring canary
# --------------------------------------------------------------------------- #


def reference_proposals() -> dict[str, dict[str, Any]]:
    """One station that should be accepted and one that should not."""

    return {
        "good": {
            "schema": PROPOSAL_SCHEMA,
            "title": "two views of one law",
            "law_id": "L3-native-w49",
            "observation_recipe_ids": ["uniform-pair", "gaussian-pair"],
            "retention_menu_ids": ["R1-uniform-pair", "R3-narrow-packet", "R4-counterflow"],
            "reason": (
                "the uniform pair gives the instrument a single tone to fit and the gaussian "
                "pair shows the same law on a localized write; the menu spans a fast and a slow "
                "write, and the counterflow packet is the eps == 0 control inside the menu"
            ),
        },
        "blind": {
            "schema": PROPOSAL_SCHEMA,
            "title": "a packet that hides the law",
            "law_id": "L3-native-w49",
            "observation_recipe_ids": ["counterflow-packet"],
            "retention_menu_ids": ["R1-uniform-pair", "R4-counterflow"],
            "reason": "a counterflow packet keeps eps identically zero, so it looks the same under every candidate law",
        },
    }


def authoring_canary_report(
    base: HiddenWorld | None = None,
    *,
    receipt_dir: str | None = None,
    deadline_s: float = 900.0,
) -> dict[str, Any]:
    """Run both reference proposals through the real authoring station."""

    declared = base or hidden_module.hidden_world(variant="authoring-base")
    station = authoring_station(declared)
    root = (
        None
        if receipt_dir is None
        else str(receipt_dir)
    )
    runs: dict[str, Any] = {}
    for name, proposal in reference_proposals().items():
        agent = ScriptedAgent(answerer=lambda _exchange, item=proposal: dict(item), kind=f"author-{name}")
        receipt = Course(
            declared,
            (station,),
            level="authoring",
            world_block=declared.declared_world(),
            title=f"The Shifting Laboratory — authoring on {declared.variant}",
        ).run(
            agent,
            receipt_path=None if root is None else f"{root}/authoring-{name}.json",
            deadline_s=deadline_s,
        )
        report = receipt["stations"][0]
        runs[name] = {
            "verdict": report["verdict"],
            "checks": [
                {"name": check["name"], "ok": bool(check["ok"]), "detail": check["detail"]}
                for check in report["checks"]
            ],
            "measurements": report.get("measurements", {}),
            "digest": receipt["digest"],
        }
    accepted = runs["good"]["verdict"] == "pass"
    rejected = runs["blind"]["verdict"] != "pass"
    return {
        "schema": AUTHORING_CANARY_SCHEMA,
        "base_variant": declared.variant,
        "runs": runs,
        "discriminates": bool(accepted and rejected),
    }


__all__ = [
    "PROPOSAL_SCHEMA",
    "AUTHORING_SCHEMA",
    "AUTHORING_CANARY_SCHEMA",
    "AUTHOR_OBSERVATIONS",
    "AUTHOR_MENU",
    "AUTHOR_READERS",
    "observation_vocabulary",
    "menu_vocabulary",
    "parse_proposal",
    "build_authored_world",
    "authoring_answerer",
    "run_authored_station",
    "judge_authoring",
    "proposal_shape",
    "brief_authoring",
    "authoring_station",
    "authoring_mission",
    "reference_proposals",
    "authoring_canary_report",
]
