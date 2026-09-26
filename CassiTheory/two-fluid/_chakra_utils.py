#!/usr/bin/env python3
"""
Chakra utility functions—one canonical implementation of φ-scaled width
allocation and offset computation.

Used throughout Cassi's resonant-field architecture. Every module that
allocates chakra dimensions delegates to this module.
"""

import math
from typing import List

import torch


# ── φ constants ──
PHI: float = (1 + 5 ** 0.5) / 2
PHI_INV: float = 1.0 / PHI


def fibonacci_chakra_widths(D: int, C: int = 13, min_width: int = 3, n_brain: int = 3) -> List[int]:
    """Return C integer widths summing to D, following Fibonacci + brain split.

    Lower chakras follow the Fibonacci recurrence (each = sum of prior two)
    starting from min_width. Top n_brain chakras evenly split the remainder.
    """
    N_lower = C - n_brain
    widths = []
    a, b = min_width, min_width
    for _ in range(N_lower):
        widths.append(a)
        a, b = b, a + b
    
    used = sum(widths)
    remaining = D - used
    
    if remaining < n_brain * min_width:
        # Not enough room for Fib + brain—fall back to flat distribution
        base = D // C
        extra = D % C
        result = [base + (1 if i < extra else 0) for i in range(C)]
        assert sum(result) == D, f"flat sum {sum(result)} != D={D}"
        return result
    
    base = remaining // n_brain
    extra = remaining % n_brain
    brain_widths = [base + (1 if i < extra else 0) for i in range(n_brain)]
    
    result = widths + brain_widths
    # Fix off-by-one from rounding—adjust largest
    while sum(result) > D:
        result[max(range(C), key=lambda i: result[i])] -= 1
    while sum(result) < D:
        result[max(range(C), key=lambda i: result[i])] += 1
    assert sum(result) == D, f"width sum {sum(result)} != D={D}"
    return result
def bell_chakra_widths(D: int, C: int = 13) -> List[int]:
    """Return C integer widths summing to D, using two interleaved scales.
    
    Primary chakras:     8, 13, 21, 34, 55  (Fibonacci from 8, larger resonance pools)
    Secondary chakras:   3,  5,  8, 13, 21  (Fibonacci from 3, smaller resonance pools)
    
    Pattern: [3, 8, 5, 13, 8, 21, 13, 34, 21, 55, x, y, x]
    where the head (c10, c11, c12) gets the remainder with c11 largest.
    """
    assert C == 13, f"user's pattern is for C=13 (got {C})"
    # Guard: if D is too small for the fixed pattern, fall back to fibonacci_chakra_widths
    fixed_seq = [3, 8, 5, 13, 8, 21, 13, 34, 21, 55]
    if D < sum(fixed_seq):
        return fibonacci_chakra_widths(D, C)
    
    # Two interleaved Fibonacci sequences
    fixed = [3, 8, 5, 13, 8, 21, 13, 34, 21, 55]
    fixed_sum = sum(fixed)
    
    # Head: c10, c11, c12—c11 is 2x, c10 = c12 = x
    head_sum = D - fixed_sum
    x = head_sum // 4
    remainder = head_sum - 4 * x
    c10 = x
    c11 = 2 * x + remainder
    c12 = x
    
    result = fixed + [c10, c11, c12]
    assert sum(result) == D, f"width sum {sum(result)} != D={D}"
    assert len(result) == C, f"expected {C} chakras, got {len(result)}"
    return result
# Backward-compatible alias
phi_chakra_widths = fibonacci_chakra_widths


def chakra_offsets(widths: List[int]) -> torch.Tensor:
    """Return cumulative offsets [0, w0, w0+w1, ...] as int32 tensor.

    Args:
        widths: list of C per-chakra widths.

    Returns:
        LongTensor of shape (C + 1,) with offsets for slicing.
    """
    offsets = [0]
    for w in widths:
        offsets.append(offsets[-1] + w)
    return torch.tensor(offsets, dtype=torch.int32)


def chakra_id_tensor(widths: List[int]) -> torch.Tensor:
    """Return a tensor mapping each field dim to its chakra index.

    Args:
        widths: list of C per-chakra widths.

    Returns:
        LongTensor of shape (sum(widths),) where entry i is the chakra
        index that dimension i belongs to.
    """
    return torch.repeat_interleave(
        torch.arange(len(widths)), torch.tensor(widths)
    )
