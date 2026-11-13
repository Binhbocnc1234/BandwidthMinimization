"""The BMP ILP formulation, written once over a builder interface so that CPLEX and Gurobi solve the identical model.

The formulation and its correctness argument are in docs/ILPModel.md.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

Edge = tuple[int, int]

MODEL_NAME: str = "ilp_assignment_positions"


class ModelBuilder(Protocol):
    """The few backend operations the formulation needs. Expressions use the backend's own + * == <= operators."""

    def binaryMatrix(self, size: int, name: str) -> dict[tuple[int, int], Any]:
        """Binary variables keyed (row, column), both 1..size."""

    def continuousList(self, size: int, lower: float, upper: float, name: str) -> list[Any]:
        """Continuous variables; element i-1 belongs to index i."""

    def integerVariable(self, lower: int, upper: int, name: str) -> Any:
        """One integer variable."""

    def linearSum(self, terms: Iterable[Any]) -> Any:
        """Sum of linear terms."""

    def addConstraint(self, constraint: Any) -> None:
        """Add a linear constraint built with the backend's operators."""

    def minimize(self, objective: Any) -> None:
        """Set a minimization objective."""


@dataclass(frozen=True)
class BandwidthModelVariables:
    """Variables needed to read a solution back and to give the solver a start."""

    assignment: dict[tuple[int, int], Any]  # assignment[v, k] is 1 when vertex v takes position k
    position: list[Any]  # position[v - 1] equals the position of vertex v
    bandwidth: Any


def buildBandwidthModel(builder: ModelBuilder, numVertices: int, edges: list[Edge], lowerBound: int, upperBound: int) -> BandwidthModelVariables:
    """Add the BMP ILP to `builder`. [lowerBound, upperBound] must contain the optimum: the common lower bound and the identity bandwidth do."""
    vertices: range = range(1, numVertices + 1)
    assignment: dict[tuple[int, int], Any] = builder.binaryMatrix(numVertices, "assign")
    position: list[Any] = builder.continuousList(numVertices, 1, numVertices, "position")
    bandwidth: Any = builder.integerVariable(lowerBound, upperBound, "bandwidth")

    for v in vertices:
        builder.addConstraint(builder.linearSum(assignment[v, k] for k in vertices) == 1)
    for k in vertices:
        builder.addConstraint(builder.linearSum(assignment[v, k] for v in vertices) == 1)
    # Position variables keep each edge row at 3 nonzeros; writing the sums into the edge rows instead would cost 2n nonzeros per edge.
    for v in vertices:
        builder.addConstraint(position[v - 1] == builder.linearSum(k * assignment[v, k] for k in vertices))
    for u, v in edges:
        builder.addConstraint(position[u - 1] - position[v - 1] <= bandwidth)
        builder.addConstraint(position[v - 1] - position[u - 1] <= bandwidth)
    builder.minimize(bandwidth)

    return BandwidthModelVariables(assignment, position, bandwidth)


class GurobiBuilder:
    """ModelBuilder over a gurobipy Model."""

    def __init__(self, model: Any) -> None:
        import gurobipy

        self.gurobipy = gurobipy
        self.model = model

    def binaryMatrix(self, size: int, name: str) -> dict[tuple[int, int], Any]:
        return self.model.addVars(range(1, size + 1), range(1, size + 1), vtype=self.gurobipy.GRB.BINARY, name=name)

    def continuousList(self, size: int, lower: float, upper: float, name: str) -> list[Any]:
        variables = self.model.addVars(range(1, size + 1), lb=lower, ub=upper, vtype=self.gurobipy.GRB.CONTINUOUS, name=name)
        return [variables[i] for i in range(1, size + 1)]

    def integerVariable(self, lower: int, upper: int, name: str) -> Any:
        return self.model.addVar(lb=lower, ub=upper, vtype=self.gurobipy.GRB.INTEGER, name=name)

    def linearSum(self, terms: Iterable[Any]) -> Any:
        return self.gurobipy.quicksum(terms)

    def addConstraint(self, constraint: Any) -> None:
        self.model.addLConstr(constraint)

    def minimize(self, objective: Any) -> None:
        self.model.setObjective(objective, self.gurobipy.GRB.MINIMIZE)


class DocplexBuilder:
    """ModelBuilder over a docplex.mp Model, which CPLEX solves."""

    def __init__(self, model: Any) -> None:
        self.model = model

    def binaryMatrix(self, size: int, name: str) -> dict[tuple[int, int], Any]:
        return self.model.binary_var_matrix(range(1, size + 1), range(1, size + 1), name=name)

    def continuousList(self, size: int, lower: float, upper: float, name: str) -> list[Any]:
        return self.model.continuous_var_list(size, lb=lower, ub=upper, name=name)

    def integerVariable(self, lower: int, upper: int, name: str) -> Any:
        return self.model.integer_var(lb=lower, ub=upper, name=name)

    def linearSum(self, terms: Iterable[Any]) -> Any:
        return self.model.sum(terms)

    def addConstraint(self, constraint: Any) -> None:
        self.model.add_constraint(constraint)

    def minimize(self, objective: Any) -> None:
        self.model.minimize(objective)