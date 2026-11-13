"""Independent labeling checker and common bounds, following docs/ExperimentContract.md.

The checker reads only the input edges and the labeling, never a solver model, so that every method's output is judged the same way.
"""

from collections.abc import Sequence

Edge = tuple[int, int]


class LabelingError(ValueError):
    """A labeling is not a permutation of 1..n; the run that produced it is ERROR, never feasible."""


def checkLabeling(numVertices: int, edges: Sequence[Edge], labeling: Sequence[int]) -> int:
    """Verify that labeling[v - 1], the position of vertex v, is a permutation of 1..n, and return its bandwidth.

    An edgeless graph has bandwidth 0, the team convention in docs/Problem.md.
    """
    if len(labeling) != numVertices:
        raise LabelingError(f"labeling has {len(labeling)} positions for {numVertices} vertices")
    # bool is a subclass of int, and a JSON true must not pass as position 1.
    if any(type(position) is not int for position in labeling):
        raise LabelingError("labeling holds a value that is not an integer")
    if sorted(labeling) != list(range(1, numVertices + 1)):
        raise LabelingError("labeling is not a permutation of 1..n")
    return max((abs(labeling[u - 1] - labeling[v - 1]) for u, v in edges), default=0)


def identityLabeling(numVertices: int) -> list[int]:
    """The common initial incumbent: vertex v at position v."""
    return list(range(1, numVertices + 1))


def commonLowerBound(edges: Sequence[Edge]) -> int:
    """The common initial lower bound: 1 for a graph with an edge, otherwise 0."""
    return 1 if edges else 0