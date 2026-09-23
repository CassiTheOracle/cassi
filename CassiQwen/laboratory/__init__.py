"""The Shifting Laboratory — a research course with real physics and real stakes.

Layout
------
`oracle`        independent CPU implementation of the qualified release equations
`stations`      briefs, evidence schemas and independent judges for the physics stations
`transactions`  durable work under contention: acknowledgment loss, revocation, capacity
`canary`        scripted competent/confused/shortcut agents that prove the judges discriminate
`rail`          the declared execution rail: honor/substitution, latency, throughput, failures
`course`        mission protocol, agent drivers, receipts, timing, resume, night shift

Level 2 adds worlds that move and stations an agent builds:

`hidden`        four candidate laws, shipped observations, held-out forecasts, write lifetimes
`shifting`      a sequence of rounds whose law changes at a declared round, and its detection
`authoring`     an agent authors a station; the judge runs the real course on it

The agent under exercise never sees a judge.  It receives a brief, forecasts,
and the judge runs the world.
"""
from __future__ import annotations

__all__ = [
    "oracle",
    "stations",
    "transactions",
    "canary",
    "rail",
    "course",
    "hidden",
    "shifting",
    "authoring",
]
