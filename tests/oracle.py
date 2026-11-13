"""Brute-force BMP oracle and the correctness-gate graphs of docs/ExperimentContract.md, shared by every method's workflow tests.

The oracle enumerates permutations and computes the objective from the edges itself, so it shares no code with any model or with the shared checker.
"""

import itertools
import random

Edge = tuple[int, int]

ORACLE_MAX_VERTICES: int = 8


def bruteForceBandwidth(numVertices: int, edges: list[Edge]) -> int:
    """Return the optimal bandwidth by trying all n! position assignments."""
    if numVertices > ORACLE_MAX_VERTICES:
        raise ValueError(f"the oracle enumerates n! permutations and is limited to n <= {ORACLE_MAX_VERTICES}")
    return min(
        max((abs(positions[u - 1] - positions[v - 1]) for u, v in edges), default=0)
        for positions in itertools.permutations(range(1, numVertices + 1))
    )


def _path(numVertices: int) -> list[Edge]:
    return [(v, v + 1) for v in range(1, numVertices)]


def _cycle(numVertices: int) -> list[Edge]:
    return sorted(_path(numVertices) + [(1, numVertices)])


def _complete(numVertices: int) -> list[Edge]:
    return list(itertools.combinations(range(1, numVertices + 1), 2))


def _randomGraph(numVertices: int, edgeProbability: float, seed: int) -> list[Edge]:
    generator: random.Random = random.Random(seed)
    return [edge for edge in _complete(numVertices) if generator.random() < edgeProbability]


# (case id, n, edges sorted with u < v). Vertex numbers are shuffled in some cases so that the identity labeling is not already optimal.
CORRECTNESS_CASES: list[tuple[str, int, list[Edge]]] = [
    ("single_vertex", 1, []),
    ("edgeless_5", 5, []),
    ("path_6", 6, _path(6)),
    ("path_shuffled_6", 6, [(1, 4), (2, 4), (2, 6), (3, 5), (5, 6)]),
    ("cycle_7", 7, _cycle(7)),
    ("complete_5", 5, _complete(5)),
    ("star_7", 7, [(1, v) for v in range(2, 8)]),
    ("disconnected_8", 8, [(1, 8), (2, 7), (3, 6)]),
    ("isolated_and_triangle_6", 6, [(2, 5), (2, 6), (5, 6)]),
    ("random_8_a", 8, _randomGraph(8, 0.35, 17)),
    ("random_8_b", 8, _randomGraph(8, 0.5, 23)),
]


def colText(numVertices: int, edges: list[Edge]) -> str:
    """Write a graph in the shared .col format."""
    return f"p edge {numVertices} {len(edges)}\n" + "".join(f"e {u} {v}\n" for u, v in edges)