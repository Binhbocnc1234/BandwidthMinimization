"""Run one SAT bound search in a child process and stop it at the deadline.

The whole search of a run lives in one child process, and the parent kills that process at the deadline. CaDiCaL through PySAT offers no way to stop a running solve from the same process: `Cadical153.interrupt()` raises NotImplementedError, and a solve holds the GIL, so a watchdog thread cannot run either. Cutting a solve into conflict-budget slices changes the search (ibm32 at bound 12 took 6.3 s as one call and was unsolved after 25 s in slices) and cannot stop clause construction. One process per run, rather than per bound, keeps the single persistent solver that incremental solving needs.
"""

import multiprocessing
import time
import traceback
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from typing import Any, Callable


class SearchReporter:
    """Child-side channel that sends search progress to the parent as soon as it exists, so a kill at the deadline cannot lose it."""

    def __init__(self, connection: Connection) -> None:
        self.connection: Connection = connection

    def _send(self, kind: str, payload: Any = None) -> None:
        # time.monotonic() is system-wide, so the parent can compare this stamp with its own deadline.
        self.connection.send((kind, time.monotonic(), payload))

    def boundStarted(self, ub: int) -> None:
        """Announce the bound being tested, before its model is built."""
        self._send("boundStarted", ub)

    def modelSize(self, numVars: int, numClauses: int) -> None:
        """Report a model size; the parent keeps the largest values."""
        self._send("modelSize", (numVars, numClauses))

    def boundFinished(self, traceEntry: dict, labeling: list[int] | None) -> None:
        """Report a definitive answer for a bound. `labeling` is the decoded model when SAT, and None when UNSAT."""
        self._send("boundFinished", (traceEntry, labeling))

    def searchFinished(self) -> None:
        """Announce that the search ran out of bounds to test."""
        self._send("searchFinished")

    def searchFailed(self, details: str) -> None:
        """Send the full traceback of an exception raised by the search."""
        self._send("searchFailed", details)


SearchFunction = Callable[[int, int, SearchReporter], None]


def _runChild(search: SearchFunction, initUB: int, lb: int, sender: Connection) -> None:
    reporter: SearchReporter = SearchReporter(sender)
    # Sent after this process has finished importing, so the budget excludes process startup and imports, as docs/ExperimentContract.md requires.
    reporter._send("ready")
    try:
        search(initUB, lb, reporter)
    except Exception:
        reporter.searchFailed(traceback.format_exc())
    else:
        reporter.searchFinished()


def runSearchWithDeadline(
    search: SearchFunction,
    numVertices: int,
    numEdges: int,
    initUB: int,
    timeLimit: float,
    verbose: bool,
) -> dict:
    """
    Run `search(initUB, lb, reporter)` in a child process for at most timeLimit seconds, which cover model construction and every bound.

    The caller's program needs an `if __name__ == "__main__":` guard, because the "spawn" start method imports the main script again in the child.

    Returns the solver result dictionary described in solveBMPSAT. An interrupted bound is only ever recorded as unknown (isSat None), never as UNSAT.
    Raises RuntimeError when the child raises an exception or dies before the deadline.
    """

    bestLabeling: list[int] = [i + 1 for i in range(numVertices)]
    bestUB: int = initUB
    lb: int = 1 if numEdges > 0 else 0
    status: str = "OPTIMAL" if bestUB <= lb else "FEASIBLE"
    terminationReason: str = "completed"
    trace: list[dict] = []
    maxVars: int = 0
    maxClauses: int = 0
    startTime: float = time.monotonic()

    if bestUB > lb:
        # "spawn" exists on every OS, so there is one tested start path, and the child inherits no threads or solver state.
        context = multiprocessing.get_context("spawn")
        receiver, sender = context.Pipe(duplex=False)
        child = context.Process(target=_runChild, args=(search, initUB, lb, sender), daemon=True)
        child.start()
        # While the parent holds this end, the pipe never reports end-of-file, so a dead child would go unnoticed until the deadline.
        sender.close()

        currentBound: int | None = None
        boundStartTime: float = 0.0
        try:
            _receive(receiver, child, currentBound)
            startTime = time.monotonic()
            deadline: float = startTime + timeLimit

            while True:
                if not receiver.poll(max(0.0, deadline - time.monotonic())):
                    terminationReason = "time_limit"
                    break

                kind, sentAt, payload = _receive(receiver, child, currentBound)

                # A result that was produced after the deadline does not count, even when it arrives before the kill.
                if sentAt > deadline:
                    terminationReason = "time_limit"
                    break

                if kind == "boundStarted":
                    currentBound = payload
                    boundStartTime = sentAt
                elif kind == "modelSize":
                    maxVars = max(maxVars, payload[0])
                    maxClauses = max(maxClauses, payload[1])
                elif kind == "boundFinished":
                    traceEntry, labeling = payload
                    trace.append(traceEntry)
                    currentBound = None
                    if traceEntry["isSat"]:
                        bestUB = traceEntry["ub"]
                        bestLabeling = labeling
                    else:
                        status = "OPTIMAL"
                        break
                elif kind == "searchFinished":
                    break
                else:
                    raise RuntimeError(f"SAT search failed in its child process:\n{payload}")

            if terminationReason == "time_limit" and currentBound is not None:
                # solveTime covers the construction and search of this bound, because the two are not split once a bound is interrupted.
                trace.append({"ub": currentBound, "isSat": None, "solveTime": time.monotonic() - boundStartTime})
                if verbose:
                    print(f"  [Timeout] Stopped at UB = {currentBound} after the {timeLimit}s limit", flush=True)
        finally:
            # Also ends a child that has finished its work, so interpreter teardown is not measured.
            child.kill()
            child.join()
            receiver.close()

    # Stopped after the kill completes, so the overshoot includes the time the OS takes to end the child.
    totalTime: float = time.monotonic() - startTime

    return {
        "status": status,
        "bestUB": bestUB,
        "labeling": bestLabeling,
        "totalTime": totalTime,
        "maxVars": maxVars,
        "maxClauses": maxClauses,
        "trace": trace,
        "terminationReason": terminationReason,
        "deadlineOvershootSeconds": max(0.0, totalTime - timeLimit),
    }


def _receive(receiver: Connection, child: BaseProcess, currentBound: int | None) -> tuple[str, float, Any]:
    """Read one message, and turn a dead child into an error that keeps its exit code."""
    try:
        return receiver.recv()
    except (EOFError, OSError) as error:
        child.join()
        raise RuntimeError(
            f"SAT child process ended without a result: exit code {child.exitcode} while testing bound {currentBound}. A negative code is the signal that ended it; -9 can be the OS out-of-memory killer. An exit code of 1 at startup can mean the main script has no __main__ guard; see the traceback above."
        ) from error