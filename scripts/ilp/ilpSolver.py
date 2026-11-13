"""Solve BMP with the shared ILP formulation on IBM CPLEX or Gurobi.

The result dictionary uses the same keys as scripts/cp/cpSolver.py, so the experiment runner reads both alike.
"""

import math
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scripts.ilp.ilpModel import MODEL_NAME, BandwidthModelVariables, DocplexBuilder, GurobiBuilder, buildBandwidthModel
from scripts.shared.labeling import checkLabeling, commonLowerBound, identityLabeling

Edge = tuple[int, int]
IncumbentCallback = Callable[[list[int], int, str], None]

BACKENDS: dict[str, tuple[str, str]] = {
    "cplex": ("ilp_cplex", "IBM CPLEX MIP"),
    "gurobi": ("ilp_gurobi", "Gurobi"),
}

# Both backends accept an integer variable that is within 1e-5 of an integer (Gurobi IntFeasTol and CPLEX mip.tolerances.integrality, defaults read on 2026-11-13). A native objective bound can sit that far below the integer it certifies, so it is rounded up after subtracting this tolerance. BMP objectives are integers.
INTEGRALITY_TOLERANCE: float = 1e-5

# CPLEX solve status codes, from the CPLEX Callable Library (CPXMIP_*).
_CPLEX_OPTIMAL_CODES: frozenset[int] = frozenset({101, 102})
_CPLEX_INFEASIBLE_CODES: frozenset[int] = frozenset({103, 119})


class IncumbentTracker:
    """Keep the best checked labeling found so far, starting from the identity labeling.

    Backend callbacks call offer(). A failure inside a callback is stored rather than raised, because the backends do not pass callback exceptions back to the caller reliably; ILPSolver raises it after the solve ends.
    """

    def __init__(self, numVertices: int, edges: list[Edge], initUB: int, onIncumbent: IncumbentCallback | None) -> None:
        self.numVertices: int = numVertices
        self.edges: list[Edge] = edges
        self.labeling: list[int] = identityLabeling(numVertices)
        self.bandwidth: int = initUB
        self.origin: str = "identity"
        self.trace: list[dict] = []
        self.onIncumbent: IncumbentCallback | None = onIncumbent
        self.startTime: float = time.perf_counter()
        self.error: Exception | None = None
        if onIncumbent:
            onIncumbent(self.labeling.copy(), self.bandwidth, "identity")

    def offer(self, positionValues: list[float]) -> None:
        """Round the solver's position values, check them, and keep them when the bandwidth improves."""
        if self.error is not None:
            return
        try:
            labeling: list[int] = [round(value) for value in positionValues]
            bandwidth: int = checkLabeling(self.numVertices, self.edges, labeling)
            if bandwidth < self.bandwidth:
                self.labeling, self.bandwidth, self.origin = labeling, bandwidth, "solver"
                self.trace.append({"elapsedTime": time.perf_counter() - self.startTime, "bestUB": bandwidth})
                if self.onIncumbent:
                    self.onIncumbent(labeling.copy(), bandwidth, "solver")
        except Exception as error:
            self.error = error


class ILPSolver:
    """The shared ILP formulation on one backend: "cplex" or "gurobi"."""

    def __init__(self, numVertices: int, edges: list[Edge], backend: str) -> None:
        """edges come from the shared loader: sorted, 1 <= u < v <= numVertices, no duplicates."""
        if backend not in BACKENDS:
            raise ValueError(f"backend must be one of {sorted(BACKENDS)}, not {backend!r}")
        self.numVertices: int = numVertices
        self.edges: list[Edge] = edges
        self.backend: str = backend

    def solve(
        self,
        initUB: int,
        timeLimit: float = 300.0,
        seed: int = 0,
        onIncumbent: IncumbentCallback | None = None,
        logFile: Path | None = None,
    ) -> dict:
        """Minimize the bandwidth within timeLimit seconds, which cover model construction and search.

        initUB must be the checked bandwidth of the identity labeling. onIncumbent(labeling, bandwidth, origin) receives the identity labeling first, then every checked improvement, so that a caller can persist them before a kill.
        Raises RuntimeError when the backend reports an infeasible model or an optimum that its bound does not certify.
        """
        if not math.isfinite(timeLimit) or timeLimit < 0:
            raise ValueError("timeLimit must be finite and >= 0")
        if type(seed) is not int or not 0 <= seed <= 2**31 - 1:
            raise ValueError("seed must be an integer in 0..2^31-1")
        if initUB != checkLabeling(self.numVertices, self.edges, identityLabeling(self.numVertices)):
            raise ValueError("initUB must equal the checked bandwidth of the identity labeling")

        if self.backend == "gurobi":
            return self._solveGurobi(initUB, timeLimit, seed, onIncumbent, logFile)
        return self._solveCplex(initUB, timeLimit, seed, onIncumbent, logFile)

    def _solveGurobi(self, initUB: int, timeLimit: float, seed: int, onIncumbent: IncumbentCallback | None, logFile: Path | None) -> dict:
        import gurobipy
        from gurobipy import GRB

        # The license check contacts Gurobi's server, so it happens before the timer, like the imports.
        environment = gurobipy.Env(params={"OutputFlag": 0})
        try:
            model = gurobipy.Model(env=environment)
            tracker: IncumbentTracker = IncumbentTracker(self.numVertices, self.edges, initUB, onIncumbent)
            startTime: float = tracker.startTime
            variables: BandwidthModelVariables = buildBandwidthModel(
                GurobiBuilder(model), self.numVertices, self.edges, commonLowerBound(self.edges), initUB
            )
            model.update()
            constructionTime: float = time.perf_counter() - startTime
            remainingTime: float = timeLimit - constructionTime

            nativeStatus: str = "NOT_STARTED"
            terminationReason: str = "time_limit"
            lowerBound: int = commonLowerBound(self.edges)
            if remainingTime > 0:
                model.Params.TimeLimit = remainingTime
                model.Params.Threads = 1
                model.Params.Seed = seed
                model.Params.MIPGap = 0
                model.Params.MIPGapAbs = 0
                if logFile is not None:
                    model.Params.LogToConsole = 0
                    model.Params.LogFile = str(logFile)
                    model.Params.OutputFlag = 1
                self._setStart(variables, initUB, lambda variable, value: setattr(variable, "Start", value))

                def callback(callbackModel: Any, where: int) -> None:
                    if where == GRB.Callback.MIPSOL:
                        tracker.offer(callbackModel.cbGetSolution(variables.position))
                        if tracker.error is not None:
                            callbackModel.terminate()

                model.optimize(callback)
                statusNames: dict[int, str] = {getattr(GRB.Status, name): name for name in dir(GRB.Status) if name.isupper()}
                nativeStatus = statusNames[model.Status]
                self._raiseStoredError(tracker)
                if model.Status in (GRB.INFEASIBLE, GRB.INF_OR_UNBD, GRB.UNBOUNDED):
                    raise RuntimeError(f"Gurobi reported {nativeStatus} for a BMP model, which always has a solution")
                if model.SolCount > 0:
                    tracker.offer([variable.X for variable in variables.position])
                    self._raiseStoredError(tracker)
                lowerBound = max(lowerBound, self._roundBound(model.ObjBound))
                if model.Status == GRB.OPTIMAL:
                    terminationReason = "completed"
                elif model.Status != GRB.TIME_LIMIT:
                    terminationReason = nativeStatus.lower()
            totalTime: float = time.perf_counter() - startTime

            return self._result(
                tracker, initUB, lowerBound, nativeStatus, nativeStatus == "OPTIMAL", terminationReason,
                totalTime, constructionTime, timeLimit, seed,
                ".".join(str(part) for part in gurobipy.gurobi.version()), model.NumVars, model.NumConstrs,
            )
        finally:
            environment.dispose()

    def _solveCplex(self, initUB: int, timeLimit: float, seed: int, onIncumbent: IncumbentCallback | None, logFile: Path | None) -> dict:
        import cplex
        from docplex.mp.model import Model
        from docplex.mp.progress import FunctionalSolutionListener, ProgressClock
        from docplex.mp.solution import SolveSolution

        backendVersion: str = cplex.Cplex().get_version()
        model = Model(name="bmp")
        try:
            tracker: IncumbentTracker = IncumbentTracker(self.numVertices, self.edges, initUB, onIncumbent)
            startTime: float = tracker.startTime
            variables: BandwidthModelVariables = buildBandwidthModel(
                DocplexBuilder(model), self.numVertices, self.edges, commonLowerBound(self.edges), initUB
            )
            constructionTime: float = time.perf_counter() - startTime
            remainingTime: float = timeLimit - constructionTime

            nativeStatus: str = "NOT_STARTED"
            terminationReason: str = "time_limit"
            nativeOptimal: bool = False
            lowerBound: int = commonLowerBound(self.edges)
            if remainingTime > 0:
                model.parameters.timelimit = remainingTime
                model.parameters.threads = 1
                model.parameters.randomseed = seed
                model.parameters.mip.tolerances.mipgap = 0
                model.parameters.mip.tolerances.absmipgap = 0
                startValues: dict[Any, float] = {}
                self._setStart(variables, initUB, startValues.__setitem__)
                model.add_mip_start(SolveSolution(model, startValues))

                def onSolution(solution: Any) -> None:
                    tracker.offer([solution.get_value(variable) for variable in variables.position])
                    if tracker.error is not None:
                        listener.abort()

                # The Objective clock calls the listener whenever the incumbent objective improves.
                listener = FunctionalSolutionListener(onSolution, clock=ProgressClock.Objective)
                model.add_progress_listener(listener)
                logStream = open(logFile, "w", encoding="utf-8") if logFile is not None else None
                try:
                    solution = model.solve(log_output=logStream if logStream is not None else False)
                finally:
                    if logStream is not None:
                        logStream.close()
                details = model.solve_details
                nativeStatus = details.status
                self._raiseStoredError(tracker)
                if details.status_code in _CPLEX_INFEASIBLE_CODES:
                    raise RuntimeError(f"CPLEX reported {nativeStatus} for a BMP model, which always has a solution")
                if solution is not None:
                    tracker.offer([solution.get_value(variable) for variable in variables.position])
                    self._raiseStoredError(tracker)
                    lowerBound = max(lowerBound, self._roundBound(details.best_bound))
                nativeOptimal = details.status_code in _CPLEX_OPTIMAL_CODES
                if nativeOptimal:
                    terminationReason = "completed"
                elif not details.has_hit_limit():
                    terminationReason = nativeStatus
            totalTime: float = time.perf_counter() - startTime

            return self._result(
                tracker, initUB, lowerBound, nativeStatus, nativeOptimal, terminationReason,
                totalTime, constructionTime, timeLimit, seed,
                backendVersion, model.number_of_variables, model.number_of_constraints,
            )
        finally:
            model.end()

    def _setStart(self, variables: BandwidthModelVariables, initUB: int, setValue: Callable[[Any, float], None]) -> None:
        """Give the backend the common initial incumbent, the identity labeling, as a MIP start."""
        for (v, k), variable in variables.assignment.items():
            setValue(variable, 1 if v == k else 0)
        for v, variable in enumerate(variables.position, 1):
            setValue(variable, v)
        setValue(variables.bandwidth, initUB)

    @staticmethod
    def _roundBound(nativeBound: float) -> int:
        return math.ceil(nativeBound - INTEGRALITY_TOLERANCE)

    @staticmethod
    def _raiseStoredError(tracker: IncumbentTracker) -> None:
        if tracker.error is not None:
            raise RuntimeError("an incumbent from the ILP backend failed checking or saving") from tracker.error

    def _result(
        self, tracker: IncumbentTracker, initUB: int, lowerBound: int, nativeStatus: str, nativeOptimal: bool,
        terminationReason: str, totalTime: float, constructionTime: float, timeLimit: float, seed: int,
        backendVersion: str, numVars: int, numConstraints: int,
    ) -> dict:
        if lowerBound > tracker.bandwidth:
            raise RuntimeError(f"certified lower bound {lowerBound} exceeds the checked incumbent bandwidth {tracker.bandwidth}")
        if nativeOptimal and lowerBound != tracker.bandwidth:
            raise RuntimeError(f"{nativeStatus} reported, but the bound {lowerBound} does not certify bandwidth {tracker.bandwidth}")
        # The common lower bound alone can prove optimality, for example on an edgeless graph or a path.
        status: str = "OPTIMAL" if lowerBound == tracker.bandwidth else "FEASIBLE"

        validationStart: float = time.perf_counter()
        checkedBandwidth: int = checkLabeling(self.numVertices, self.edges, tracker.labeling)
        validationTime: float = time.perf_counter() - validationStart
        if checkedBandwidth != tracker.bandwidth:
            raise RuntimeError(f"final labeling checks to bandwidth {checkedBandwidth}, not {tracker.bandwidth}")

        method, backendName = BACKENDS[self.backend]
        return {
            "status": status,
            "bestUB": tracker.bandwidth,
            "labeling": tracker.labeling,
            "totalTime": totalTime,
            "constructionTime": constructionTime,
            "searchTime": totalTime - constructionTime,
            "validationTime": validationTime,
            "lowerBound": lowerBound,
            "initUB": initUB,
            "trace": tracker.trace,
            "method": method,
            "model": MODEL_NAME,
            "backend": backendName,
            "backendVersion": backendVersion,
            "nativeStatus": nativeStatus,
            "terminationReason": terminationReason,
            "incumbentOrigin": tracker.origin,
            "hintSubmitted": nativeStatus != "NOT_STARTED",
            # Neither backend reports through its API whether it accepted the MIP start; the solver log says so.
            "hintAccepted": None,
            "numVars": numVars,
            "numConstraints": numConstraints,
            "modelCountScope": "source model, before backend presolve",
            "maxClauses": None,
            "threads": 1,
            "seed": seed,
            "deadlineOvershoot": max(0.0, totalTime - timeLimit),
        }