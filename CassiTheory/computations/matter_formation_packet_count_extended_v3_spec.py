"""Declarative schedule for the overlap-repaired packet extension."""
from __future__ import annotations

import math

from matter_formation_packet_count_extended_spec import (  # noqa: F401
    ARM_SPECS,
    ARMS,
    CANDIDATE_ARMS,
    COMPARISON_OBSERVABLES,
    CONTROL_ARMS,
    GRID_SPECS,
    INITIAL_CORE_FRACTION_MAX,
    INITIAL_OVERLAP_MAX,
    LATE_START,
    LOWER_PRIMARY_RECEIPT_SHA256,
    LOWER_VERIFICATION_RECEIPT_SHA256,
    RETAINED_FRACTION,
    SAMPLE_DT,
    SHARE_TOL,
    SNAPSHOT_TIMES,
    T_FINAL,
    TOTAL_CHARGE,
    WAVE_NUMBER,
    WIDTH,
    BINDING_RATIO_MAX,
)

R0 = 32.0
PACKET_COUNT_CANDIDATES = (4, 5, 6)


def semicircle_geometry(count: int) -> tuple[tuple[float, float], ...]:
    return tuple(
        (
            R0 * abs(math.cos(-math.pi / 2.0 + j * math.pi / (count - 1))),
            R0 * math.sin(-math.pi / 2.0 + j * math.pi / (count - 1)),
        )
        for j in range(count)
    )


GEOMETRIES = {count: semicircle_geometry(count) for count in PACKET_COUNT_CANDIDATES}
