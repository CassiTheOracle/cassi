import unittest

from cassi_conscious_protocol import (
    ActorClass,
    CassiConsciousProtocolError,
    EventKind,
    RealityStatus,
    create_event,
    validate_event,
)


class CassiConsciousProtocolTests(unittest.TestCase):
    def test_deliberation_is_local_derived_only(self) -> None:
        event = create_event(
            sequence=7,
            kind=EventKind.DELIBERATION,
            reality_status=RealityStatus.DERIVED_DELIBERATION,
            actor=ActorClass.LOCAL_AGENT,
            payload=b"internal branch selection",
            source_id="test",
            branch_id="d" * 64,
        )
        validate_event(event)

        for status, actor in (
            (RealityStatus.DERIVED_RECALL, ActorClass.LOCAL_AGENT),
            (RealityStatus.DERIVED_DELIBERATION, ActorClass.EXTERNAL_AGENT),
            (RealityStatus.DERIVED_DELIBERATION, ActorClass.TEACHER),
            (RealityStatus.DERIVED_DELIBERATION, ActorClass.ENVIRONMENT),
            (RealityStatus.DERIVED_DELIBERATION, ActorClass.UNKNOWN),
        ):
            with self.assertRaises(CassiConsciousProtocolError):
                create_event(
                    sequence=7,
                    kind=EventKind.DELIBERATION,
                    reality_status=status,
                    actor=actor,
                    payload=b"internal branch selection",
                    source_id="test",
                    branch_id="d" * 64,
                )

    def test_existing_action_legality_is_unchanged(self) -> None:
        event = create_event(
            sequence=8,
            kind=EventKind.ACTION_INTENT,
            reality_status=RealityStatus.AGENT_INTENT,
            actor=ActorClass.LOCAL_AGENT,
            payload=b"action",
            source_id="test",
        )
        validate_event(event)


if __name__ == "__main__":
    unittest.main()
