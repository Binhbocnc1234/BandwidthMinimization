"""The six required method IDs of docs/ExperimentContract.md, each run with the same inputs and returning the same result keys.

Every function runs inside a fresh worker process (tools/experiment/worker.py), so backend imports and solver state never carry over between runs.
"""

import sys
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

from scripts.shared.labeling import commonLowerBound, identityLabeling

Edge = tuple[int, int]
IncumbentCallback = Callable[[list[int], int, str], None]

REPOSITORY_ROOT: Path = Path(__file__).resolve().parents[2]
# The SAT modules import each other by bare module name, so their folder must be on sys.path. The SAT search child inherits sys.path under the "spawn" start method.
SAT_FOLDER: Path = REPOSITORY_ROOT / "scripts" / "sat"

METHOD_IDS: list[str] = ["sat_order_repeated", "sat_order_incremental", "cp_ortools", "cp_cpo", "ilp_cplex", "ilp_gurobi"]
SAT_METHOD_IDS: frozenset[str] = frozenset({"sat_order_repeated", "sat_order_incremental"})


@dataclass(frozen=True)
class RunRequest:
    numVertices: int
    edges: list[Edge]
    initUB: int
    timeLimitSeconds: float
    seed: int
    onIncumbent: IncumbentCallback
    solverLogFile: Path
    cpoExecutable: str | None


def _runSat(request: RunRequest, solverType: str) -> dict:
    """Run the order-encoded SAT search; it enforces its own deadline by killing its search child.

    The SAT solvers return their incumbents only at the end, so a kill of the whole worker loses every improvement except the identity. The SAT deadline runs inside the budget, so that kill happens only when the SAT code misses its own deadline by the runner's grace period.
    """
    if str(SAT_FOLDER) not in sys.path:
        sys.path.insert(0, str(SAT_FOLDER))
    from incrementalSATSolver import IncrementalSATSolver
    from repeatedSATSolver import RepeatedSATSolver

    request.onIncumbent(identityLabeling(request.numVertices), request.initUB, "identity")
    solverClass: type = RepeatedSATSolver if solverType == "repeated" else IncrementalSATSolver
    result: dict = solverClass(request.numVertices, request.edges, encodingType="order", verbose=True).solve(request.initUB, request.timeLimitSeconds)
    origin: str = "identity" if result["bestUB"] == request.initUB else "solver"
    if origin == "solver":
        request.onIncumbent(list(result["labeling"]), result["bestUB"], "solver")
    # The SAT code reports OPTIMAL only after UNSAT just below its incumbent. By contrast, the contract also counts reaching the common lower bound as proof, and the SAT search stops there without an UNSAT answer.
    lowerBound: int = result["bestUB"] if result["status"] == "OPTIMAL" else commonLowerBound(request.edges)
    return {
        "status": "OPTIMAL" if result["bestUB"] == lowerBound else result["status"],
        "bandwidth": result["bestUB"],
        "lowerBound": lowerBound,
        "incumbentOrigin": origin,
        "terminationReason": result["terminationReason"],
        "elapsedSeconds": result["totalTime"],
        # The SAT code times model construction and search together per bound, so the split is not measured.
        "constructionSeconds": None,
        "searchSeconds": None,
        "deadlineOvershootSeconds": result["deadlineOvershootSeconds"],
        "backend": "CaDiCaL 1.5.3 through PySAT",
        "backendVersion": f"python-sat {version('python-sat')}",
        # PySAT exposes no seed for CaDiCaL.
        "effectiveSeed": None,
        "threads": 1,
        "variables": result["maxVars"],
        "constraints": None,
        "clauses": result["maxClauses"],
        "nativeStatus": None,
        "hintSubmitted": None,
        "hintAccepted": None,
        "trace": result["trace"],
    }


def _fromCpOrIlp(result: dict) -> dict:
    """Map the result keys that scripts/cp/cpSolver.py and scripts/ilp/ilpSolver.py share."""
    return {
        "status": result["status"],
        "bandwidth": result["bestUB"],
        "lowerBound": result["lowerBound"],
        "incumbentOrigin": result["incumbentOrigin"],
        "terminationReason": result["terminationReason"],
        "elapsedSeconds": result["totalTime"],
        "constructionSeconds": result["constructionTime"],
        "searchSeconds": result["searchTime"],
        "deadlineOvershootSeconds": result["deadlineOvershoot"],
        "backend": result["backend"],
        "backendVersion": result["backendVersion"],
        "effectiveSeed": result["seed"],
        "threads": result["threads"],
        "variables": result["numVars"],
        "constraints": result["numConstraints"],
        "clauses": None,
        "nativeStatus": result["nativeStatus"],
        "hintSubmitted": result["hintSubmitted"],
        "hintAccepted": result["hintAccepted"],
        "trace": result["trace"],
    }


def _runCp(request: RunRequest, backend: str) -> dict:
    from scripts.cp.cpSolver import CPSolver
    from scripts.cp.teamBridge import verifyLabeling

    result: dict = CPSolver(request.numVertices, request.edges, backend, verifyLabeling).solve(
        request.initUB, request.timeLimitSeconds, request.seed, onIncumbent=request.onIncumbent, logFile=str(request.solverLogFile), executable=request.cpoExecutable
    )
    return _fromCpOrIlp(result)


def _runIlp(request: RunRequest, backend: str) -> dict:
    from scripts.ilp.ilpSolver import ILPSolver

    result: dict = ILPSolver(request.numVertices, request.edges, backend).solve(
        request.initUB, request.timeLimitSeconds, request.seed, onIncumbent=request.onIncumbent, logFile=request.solverLogFile
    )
    return _fromCpOrIlp(result)


METHODS: dict[str, Callable[[RunRequest], dict]] = {
    "sat_order_repeated": lambda request: _runSat(request, "repeated"),
    "sat_order_incremental": lambda request: _runSat(request, "incremental"),
    "cp_ortools": lambda request: _runCp(request, "ortools"),
    "cp_cpo": lambda request: _runCp(request, "cpo"),
    "ilp_cplex": lambda request: _runIlp(request, "cplex"),
    "ilp_gurobi": lambda request: _runIlp(request, "gurobi"),
}