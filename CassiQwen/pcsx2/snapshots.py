"""Exact byte-level comparison between labeled memory moments."""

from __future__ import annotations


def compare_snapshots(before: bytes, after: bytes, *, base_address: int,
                      page_size: int = 4096) -> dict:
    """Return exact changed byte ranges and page coverage, JSON-safe.

    `before` and `after` must have the same length. `changed_ranges` holds
    maximal spans of consecutive differing bytes with their old/new bytes
    hex-encoded. `changed_pages` holds the snapshot-relative page index and
    the absolute [start, end) window of every page containing a change.
    """
    if not isinstance(before, (bytes, bytearray)) or not isinstance(after, (bytes, bytearray)):
        raise ValueError("snapshots must be bytes")
    if len(before) != len(after):
        raise ValueError(
            f"snapshot lengths differ: {len(before)} before, {len(after)} after")
    if isinstance(page_size, bool) or not isinstance(page_size, int) or page_size <= 0:
        raise ValueError("page_size must be a positive integer")
    if isinstance(base_address, bool) or not isinstance(base_address, int) or base_address < 0:
        raise ValueError("base_address must be a non-negative integer")

    before = bytes(before)
    after = bytes(after)
    length = len(before)
    changed_ranges: list[dict] = []
    changed_bytes = 0
    index = 0
    while index < length:
        if before[index] == after[index]:
            index += 1
            continue
        start = index
        while index < length and before[index] != after[index]:
            index += 1
        span_before = before[start:index]
        span_after = after[start:index]
        changed_bytes += index - start
        changed_ranges.append({
            "start": base_address + start,
            "end": base_address + index,
            "bytes_before": span_before.hex(),
            "bytes_after": span_after.hex(),
        })
    pages: list[dict] = []
    if changed_ranges and length:
        dirty: set[int] = set()
        for change in changed_ranges:
            first = (change["start"] - base_address) // page_size
            last = (change["end"] - base_address - 1) // page_size
            dirty.update(range(first, last + 1))
        for page in sorted(dirty):
            page_start = base_address + page * page_size
            pages.append({
                "page": page,
                "start": page_start,
                "end": page_start + page_size,
            })
    return {
        "base_address": base_address,
        "page_size": page_size,
        "changed_ranges": changed_ranges,
        "changed_pages": pages,
        "changed_byte_count": changed_bytes,
    }
