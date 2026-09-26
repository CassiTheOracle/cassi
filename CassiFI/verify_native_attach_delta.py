"""Prove changed-page attachment transfer against a real native field runtime.

The probe launches the field runtime, attaches a full owner image, then
attaches derived images whose pages are rewritten, unchanged, and appended.
Each round checks three claims: the packed digest the runtime publishes equals
the client's own digest of the image, only the changed word ranges cross the
pipe, and a base the runtime no longer holds falls back to the full transfer.
Prints one JSON receipt and exits nonzero when a claim fails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np  # noqa: E402

import cassi_field_runtime_native as native  # noqa: E402
from cassi_field_runtime_native import (  # noqa: E402
    NativeAttachBase,
    NativeFieldRuntimeClient,
)

DEFAULT_EXE = _ROOT / "native/field-runtime/build/Release/cassifi-field-runtime.exe"
PAGE_WORDS = (64 << 10) // 4
CANONICAL_WORD_BYTES = 8


class _Staging(native._StagingMapping):
    """Count the payload bytes that cross the pipe through the shared mapping."""

    staged = 0

    @classmethod
    def from_bytes(cls, data: bytes) -> "_Staging":
        cls.staged += len(data)
        return super().from_bytes(data)  # type: ignore[misc]


class _Meter:
    """Record the import kind a round opened and the payload it staged."""

    def __init__(self, client: NativeFieldRuntimeClient) -> None:
        self.kinds: list[int] = []
        self.delta_refusal: str | None = None
        self._staging = native._StagingMapping
        native._StagingMapping = _Staging
        original = client._request

        def request(kind: int, fields: object) -> object:
            self.kinds.append(kind)
            try:
                return original(kind, fields)
            except native.NativeFieldRuntimeError as error:
                if kind == native.IMPORT_IMAGE_DELTA:
                    self.delta_refusal = str(error)
                raise

        client._request = request  # type: ignore[method-assign]

    def reset(self) -> None:
        self.kinds = []
        self.delta_refusal = None
        _Staging.staged = 0

    def transferred(self) -> int:
        return _Staging.staged

    def mode(self) -> str:
        return "full" if native.IMPORT_IMAGE_INFO in self.kinds else "delta"

    def attempted_delta(self) -> bool:
        return native.IMPORT_IMAGE_DELTA in self.kinds

    def restore(self) -> None:
        native._StagingMapping = self._staging


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _page_bytes(words: np.ndarray) -> bytes:
    return np.ascontiguousarray(words, dtype="<u4").tobytes()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", default=str(DEFAULT_EXE), help="native field-runtime binary")
    parser.add_argument("--device", type=int, default=0, help="runtime device index")
    parser.add_argument("--cpu-only", action="store_true", help="launch the runtime without Vulkan")
    parser.add_argument("--pages", type=int, default=6, help="pages in the initial image")
    arguments = parser.parse_args()

    executable = Path(arguments.exe).expanduser().resolve(strict=True)
    generator = np.random.default_rng(20260926)
    pages = arguments.pages

    def random_pages(count: int) -> np.ndarray:
        return generator.integers(0, 1 << 32, size=count * PAGE_WORDS, dtype=np.uint32)

    base_words = random_pages(pages)
    shape = (1, int(base_words.size), 1)
    catalog = _digest("catalog")
    profile = _digest("profile")
    owner = "probe-owner"
    rounds: list[dict[str, object]] = []
    failed = False

    client = NativeFieldRuntimeClient.launch(
        executable,
        device_index=arguments.device,
        cpu_only=arguments.cpu_only,
    )
    meter = _Meter(client)
    try:

        def attach(
            label: str,
            words: np.ndarray,
            *,
            fence: int,
            state: str,
            base: NativeAttachBase | None,
            expect_mode: str,
            expect_transferred: int,
        ) -> dict[str, object]:
            nonlocal failed
            payload = _page_bytes(words)
            target_shape = (1, int(words.size), 1)
            meter.reset()
            started = time.perf_counter()
            try:
                attachment = client.attach_packed(
                    owner,
                    target_shape,
                    payload,
                    profile_sha256=profile,
                    state_sha256=state,
                    catalog_sha256=catalog,
                    fence=fence,
                    base=base,
                )
            except Exception as error:  # noqa: BLE001 - the receipt carries the reason
                failed = True
                record: dict[str, object] = {
                    "round": label,
                    "error": f"{type(error).__name__}: {error}",
                }
                rounds.append(record)
                return record
            expected = hashlib.sha256(payload).hexdigest()
            record = {
                "round": label,
                "mode": meter.mode(),
                "attempted_delta": meter.attempted_delta(),
                "seconds": round(time.perf_counter() - started, 3),
                "transferred_bytes": meter.transferred(),
                "image_bytes": len(payload) * 2,
                "ratio": round(meter.transferred() / (len(payload) * 2), 4),
                "packed_sha256": attachment["packed_sha256"],
                "digest_matches": attachment["packed_sha256"] == expected,
                "word_count": attachment["word_count"],
            }
            failures: list[str] = []
            if record["digest_matches"] is not True:
                failures.append("the runtime packed digest disagrees with the client image")
            if record["mode"] != expect_mode:
                if meter.delta_refusal is not None and expect_mode == "delta":
                    record["delta_refusal"] = meter.delta_refusal
                    failures.append(f"the runtime refused the delta protocol: {meter.delta_refusal}")
                else:
                    failures.append(f"the runtime took the {record['mode']} transfer")
            if meter.transferred() != expect_transferred:
                failures.append(
                    f"carried {meter.transferred()} bytes, expected {expect_transferred}"
                )
            if failures:
                failed = True
                record["failure"] = "; ".join(failures)
            rounds.append(record)
            return record

        base = attach(
            "base-full",
            base_words,
            fence=1,
            state=_digest("state-1"),
            base=None,
            expect_mode="full",
            expect_transferred=int(base_words.size) * CANONICAL_WORD_BYTES,
        )
        first_image = base_words

        # Two rewritten pages, in place, so the digest can only match when the
        # runtime keeps every untouched page.
        rewritten = base_words.copy()
        rewritten[2 * PAGE_WORDS : 3 * PAGE_WORDS] = random_pages(1)
        rewritten[4 * PAGE_WORDS : 5 * PAGE_WORDS] = random_pages(1)
        attach(
            "rewritten-pages",
            rewritten,
            fence=2,
            state=_digest("state-2"),
            base=NativeAttachBase(
                payload=_page_bytes(first_image),
                shape=shape,
                fence=1,
                state_sha256=_digest("state-1"),
            ),
            expect_mode="delta",
            expect_transferred=2 * PAGE_WORDS * CANONICAL_WORD_BYTES,
        )

        # An identical image carries the open and finish only.
        attach(
            "identical-image",
            rewritten,
            fence=3,
            state=_digest("state-3"),
            base=NativeAttachBase(
                payload=_page_bytes(rewritten),
                shape=shape,
                fence=2,
                state_sha256=_digest("state-2"),
            ),
            expect_mode="delta",
            expect_transferred=0,
        )

        # Growth: one appended page of words, one appended page of zeros.
        grown = np.concatenate(
            [rewritten, random_pages(1), np.zeros(PAGE_WORDS, dtype=np.uint32)]
        )
        attach(
            "appended-pages",
            grown,
            fence=4,
            state=_digest("state-4"),
            base=NativeAttachBase(
                payload=_page_bytes(rewritten),
                shape=shape,
                fence=3,
                state_sha256=_digest("state-3"),
            ),
            expect_mode="delta",
            expect_transferred=PAGE_WORDS * CANONICAL_WORD_BYTES,
        )

        # A base the runtime never held is refused and answered with the full image.
        attach(
            "absent-base",
            grown,
            fence=5,
            state=_digest("state-5"),
            base=NativeAttachBase(
                payload=_page_bytes(rewritten),
                shape=shape,
                fence=99,
                state_sha256=_digest("never-attached"),
            ),
            expect_mode="full",
            expect_transferred=int(grown.size) * CANONICAL_WORD_BYTES,
        )
        receipt = {
            "executable": str(executable),
            "cpu_only": arguments.cpu_only,
            "pages": pages,
            "rounds": rounds,
            "failed": failed,
        }
    finally:
        meter.restore()
        client.shutdown()

    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
