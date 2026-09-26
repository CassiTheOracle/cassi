"""Deterministic CPU probe for the tree walk's escape-link traversal.

This is a standalone reference, not a production path. It builds a comb tree
at the configured depth limit with seven sibling leaves at every level. The
shape reaches the old 64-entry LIFO stack's generic worst case while retaining
finite storage, then compares the stackless escape walk with an unbounded
reference walk and a direct leaf-force sum. Run manually when validating a
shader change; this file is intentionally not imported by Godot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isclose, sqrt

MAX_LEVELS = 14
EPS2 = 1.0e-6
TARGET = (1.0, -0.5, 0.25)
CHILDREN = 8


@dataclass
class Node:
    com: tuple[float, float, float]
    weight: float
    children: list[int] = field(default_factory=list)
    escape: int = -1


def add_comb(nodes: list[Node], depth: int) -> int:
    """Add one internal node and its seven side leaves plus a continuation."""
    root = len(nodes)
    nodes.append(Node((0.0, 0.0, 0.0), 1.0))
    if depth == 0:
        return root
    base = len(nodes)
    nodes.extend(Node((0.1 * (c + 1), -0.05 * c, 0.02 * c), 1.0)
                 for c in range(8))
    nodes[root].children = list(range(base, base + 8))
    continuation = nodes[root].children[-1]
    add_comb_into(nodes, continuation, depth - 1)
    return root


def add_comb_into(nodes: list[Node], root: int, depth: int) -> None:
    if depth == 0:
        return
    base = len(nodes)
    nodes.extend(Node((0.2 + 0.1 * (c + 1), -0.1 * c, 0.03 * c), 1.0)
                 for c in range(8))
    nodes[root].children = list(range(base, base + 8))
    add_comb_into(nodes, nodes[root].children[-1], depth - 1)


def wire_escapes(nodes: list[Node], node: int, parent_escape: int) -> None:
    nodes[node].escape = parent_escape
    children = nodes[node].children
    for c, child in enumerate(children):
        # Existing shader order is push 0..7, then pop 7..0.
        nodes[child].escape = children[c - 1] if c > 0 else parent_escape
        wire_escapes(nodes, child, nodes[child].escape)


def contribution(node: Node) -> tuple[float, float, float]:
    dx = TARGET[0] - node.com[0]
    dy = TARGET[1] - node.com[1]
    dz = TARGET[2] - node.com[2]
    r2 = dx * dx + dy * dy + dz * dz + EPS2
    inv_r3 = 1.0 / (r2 * sqrt(r2))
    return (-node.weight * dx * inv_r3,
            -node.weight * dy * inv_r3,
            -node.weight * dz * inv_r3)


def add(a: tuple[float, float, float], b: tuple[float, float, float]):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def walk_stackless(nodes: list[Node]) -> tuple[tuple[float, float, float], int]:
    force = (0.0, 0.0, 0.0)
    interactions = 0
    node = 0
    while node >= 0:
        current = nodes[node]
        if current.children:
            node = current.children[-1]
            continue
        force = add(force, contribution(current))
        interactions += 1
        node = current.escape
    return force, interactions


def walk_reference(nodes: list[Node]) -> tuple[tuple[float, float, float], int]:
    force = (0.0, 0.0, 0.0)
    interactions = 0
    stack = [0]
    while stack:
        node = nodes[stack.pop()]
        if node.children:
            stack.extend(node.children)  # pop visits highest child first
            continue
        force = add(force, contribution(node))
        interactions += 1
    return force, interactions


def direct_reference(nodes: list[Node]) -> tuple[float, float, float]:
    force = (0.0, 0.0, 0.0)
    for node in nodes:
        if not node.children:
            force = add(force, contribution(node))
    return force


def main() -> None:
    nodes: list[Node] = []
    add_comb(nodes, MAX_LEVELS)
    wire_escapes(nodes, 0, -1)
    # Make every leaf geometrically coincident after constructing the comb;
    # this exercises the capped/coincident accepted-leaf path deterministically.
    for node in nodes:
        if not node.children:
            node.com = (0.25, -0.125, 0.0625)
    stackless, interactions = walk_stackless(nodes)
    reference, reference_interactions = walk_reference(nodes)
    direct = direct_reference(nodes)
    assert interactions == reference_interactions == (CHILDREN - 1) * MAX_LEVELS + 1
    # The previous stack's pending bound is 1 + 7*depth = 99.
    for got, want in zip(stackless, reference):
        assert isclose(got, want, rel_tol=1e-12, abs_tol=1e-12)
    for got, want in zip(stackless, direct):
        assert isclose(got, want, rel_tol=1e-12, abs_tol=1e-12)
    print(f"PASS nodes={len(nodes)} leaves={interactions} force={stackless}")


if __name__ == "__main__":
    main()
