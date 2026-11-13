"""Run one experiment attempt in a fresh process: `python -m tools.experiment.worker <spec.json>`, started by tools/experiment/runExperiment.py.

Files of the attempt, relative to the experiment folder (the runner owns their names through `attemptPaths`):
- Solutions/<run_id>.json: the best labeling so far, rewritten on every improvement, so a kill keeps it.
- Logs/<run_id>.progress.json: when the solve was called, and the bandwidth and origin of that labeling.
- Logs/<run_id>.result.json: the method's normalized result, or the traceback of its exception.
- Logs/<run_id>.trace.json: the method's search trace.
"""

import json
import os
import sys
import time
import traceback
from pathlib import Path

from scripts.shared.graphInput import ManifestInstance, loadManifestInstance
from scripts.shared.labeling import checkLabeling, identityLabeling
from tools.experiment.methods import METHODS, RunRequest


def attemptPaths(experimentDir: Path, runId: str) -> dict[str, Path]:
    return {
        "spec": experimentDir / "Logs" / f"{runId}.spec.json",
        "log": experimentDir / "Logs" / f"{runId}.log",
        "solverLog": experimentDir / "Logs" / f"{runId}.solver.log",
        "labeling": experimentDir / "Solutions" / f"{runId}.json",
        "progress": experimentDir / "Logs" / f"{runId}.progress.json",
        "result": experimentDir / "Logs" / f"{runId}.result.json",
        "trace": experimentDir / "Logs" / f"{runId}.trace.json",
    }


def writeJsonAtomically(path: Path, value: object) -> None:
    """A kill during the write leaves the previous file whole, because rename replaces it in one step."""
    temporaryPath: Path = path.with_name(path.name + ".tmp")
    with open(temporaryPath, "w", encoding="utf-8") as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporaryPath, path)


def runAttempt(spec: dict) -> None:
    paths: dict[str, Path] = attemptPaths(Path(spec["experimentDir"]), spec["runId"])
    instance: ManifestInstance = ManifestInstance(
        name=spec["instance"], graphPath=Path(spec["graphPath"]), graphSha256=spec["graphSha256"], numVertices=spec["numVertices"], numEdges=spec["numEdges"]
    )
    numVertices, edges = loadManifestInstance(instance)
    initUB: int = checkLabeling(numVertices, edges, identityLabeling(numVertices))
    progress: dict = {"solveCalledAtMonotonic": None, "bandwidth": None, "incumbentOrigin": None}

    def onIncumbent(labeling: list[int], bandwidth: int, origin: str) -> None:
        # The labeling is written before the progress file that names its bandwidth, so the progress file never describes a labeling that is not on disk.
        writeJsonAtomically(paths["labeling"], labeling)
        progress.update(bandwidth=bandwidth, incumbentOrigin=origin)
        writeJsonAtomically(paths["progress"], progress)

    request: RunRequest = RunRequest(
        numVertices=numVertices,
        edges=edges,
        initUB=initUB,
        timeLimitSeconds=spec["timeLimitSeconds"],
        seed=spec["seed"],
        onIncumbent=onIncumbent,
        solverLogFile=paths["solverLog"],
        cpoExecutable=spec["cpoExecutable"],
    )
    # time.monotonic() is system-wide on Linux, so the runner can measure a killed attempt from this stamp.
    progress["solveCalledAtMonotonic"] = time.monotonic()
    writeJsonAtomically(paths["progress"], progress)
    result: dict = METHODS[spec["method"]](request)
    writeJsonAtomically(paths["trace"], result.pop("trace"))
    writeJsonAtomically(paths["result"], {"initialUpperBound": initUB, **result})


def main() -> None:
    spec: dict = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        runAttempt(spec)
    except Exception:
        details: str = traceback.format_exc()
        print(details, file=sys.stderr, flush=True)
        writeJsonAtomically(attemptPaths(Path(spec["experimentDir"]), spec["runId"])["result"], {"error": details})
        sys.exit(1)


# The guard is required: the SAT search child is started with "spawn", which imports this main module again.
if __name__ == "__main__":
    main()