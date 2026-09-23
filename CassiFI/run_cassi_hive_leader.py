"""Run the persistent Cassi Hive leader promotion loop.

The loop is intentionally small and deterministic: capsules are already
content-addressed, reviewers explicitly publish verdicts, and each pass only
promotes candidates that meet the configured independent-support threshold.
"""

from __future__ import annotations

import argparse
import json
import threading
from pathlib import Path

from cassi_hive_promotion import PromotionLoop
from cassi_hive_store import DEFAULT_HIVE_HOME, LocalHiveStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hive-home", type=Path, default=DEFAULT_HIVE_HOME)
    parser.add_argument("--hive-id", default="main")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--leader-instance-id", default="leader")
    parser.add_argument("--minimum-support-reviews", type=int, default=2)
    parser.add_argument("--interval-seconds", type=float, default=1.0)
    parser.add_argument("--once", action="store_true")
    arguments = parser.parse_args(argv)

    store = LocalHiveStore(
        arguments.hive_home,
        hive_id=arguments.hive_id,
        branch=arguments.branch,
    )
    loop = PromotionLoop(
        store,
        leader_instance_id=arguments.leader_instance_id,
        minimum_support_reviews=arguments.minimum_support_reviews,
    )
    try:
        if arguments.once:
            print(json.dumps(loop.run_once().as_dict(), indent=2, sort_keys=True))
            return 0

        stop_event = threading.Event()
        try:
            loop.run_forever(stop_event, interval_seconds=arguments.interval_seconds)
        except KeyboardInterrupt:
            stop_event.set()
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
