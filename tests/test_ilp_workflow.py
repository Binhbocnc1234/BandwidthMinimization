"""ILP workflow tests: the real formulation, solved by each backend, checked against the brute-force oracle."""

from pathlib import Path

import pytest

from scripts.ilp.ilpSolver import ILPSolver
from scripts.shared.graphInput import loadColFile
from scripts.shared.labeling import checkLabeling, identityLabeling
from tests.oracle import CORRECTNESS_CASES, bruteForceBandwidth, colText


@pytest.fixture(scope="module", params=["gurobi", "cplex"])
def backend(request: pytest.FixtureRequest) -> str:
    if request.param == "gurobi":
        import gurobipy

        try:
            gurobipy.Env(params={"OutputFlag": 0}).dispose()
        except gurobipy.GurobiError as error:
            pytest.skip(f"no Gurobi license: set GRB_LICENSE_FILE to the license file ({error})")
    return request.param


@pytest.mark.parametrize("name,numVertices,edges", CORRECTNESS_CASES, ids=[case[0] for case in CORRECTNESS_CASES])
def test_solve_reaches_the_oracle_optimum(backend: str, name: str, numVertices: int, edges: list[tuple[int, int]], tmp_path: Path) -> None:
    graphFile: Path = tmp_path / f"{name}.col"
    graphFile.write_text(colText(numVertices, edges), encoding="utf-8")
    numVertices, edges = loadColFile(graphFile)
    initUB: int = checkLabeling(numVertices, edges, identityLabeling(numVertices))
    events: list[tuple[list[int], int, str]] = []

    result: dict = ILPSolver(numVertices, edges, backend).solve(
        initUB, timeLimit=30, seed=1, onIncumbent=lambda *event: events.append(event), logFile=tmp_path / "solver.log"
    )

    assert result["status"] == "OPTIMAL"
    assert result["bestUB"] == result["lowerBound"] == bruteForceBandwidth(numVertices, edges)
    assert checkLabeling(numVertices, edges, result["labeling"]) == result["bestUB"]
    assert events[0] == (identityLabeling(numVertices), initUB, "identity")
    for labeling, bandwidth, _ in events:
        assert checkLabeling(numVertices, edges, labeling) == bandwidth
    assert result["incumbentOrigin"] == ("identity" if result["bestUB"] == initUB else "solver")
    assert result["method"] == f"ilp_{backend}"
    assert result["totalTime"] >= result["constructionTime"] >= 0


def test_zero_budget_keeps_the_identity_incumbent(backend: str) -> None:
    edges: list[tuple[int, int]] = [(1, 4), (2, 3), (3, 4)]
    result: dict = ILPSolver(4, edges, backend).solve(3, timeLimit=0)
    assert (result["status"], result["nativeStatus"], result["labeling"], result["bestUB"]) == ("FEASIBLE", "NOT_STARTED", [1, 2, 3, 4], 3)


def test_wrong_initial_bound_is_rejected() -> None:
    with pytest.raises(ValueError, match="initUB"):
        ILPSolver(4, [(1, 4)], "gurobi").solve(1)