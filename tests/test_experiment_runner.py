"""Experiment runner workflow: the real runner, worker and solvers on a two-graph manifest, checked against the brute-force oracle."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from scripts.shared.labeling import checkLabeling
from tests.oracle import bruteForceBandwidth, colText

REPOSITORY_ROOT: Path = Path(__file__).resolve().parents[1]
# One method per solver family; ilp_cplex fits the Community Edition on these graphs, so the test needs no license.
METHODS: list[str] = ["sat_order_incremental", "cp_ortools", "ilp_cplex"]
GRAPHS: dict[str, tuple[int, list[tuple[int, int]]]] = {
    "pathShuffled": (5, [(1, 4), (2, 5), (3, 4), (3, 5)]),
    "cycle6": (6, [(1, 2), (1, 6), (2, 3), (3, 4), (4, 5), (5, 6)]),
}


def _writeManifest(folder: Path) -> Path:
    instances: list[dict] = []
    for name, (numVertices, edges) in GRAPHS.items():
        graphFile: Path = folder / "graphs" / f"{name}.col"
        graphFile.parent.mkdir(parents=True, exist_ok=True)
        graphFile.write_text(colText(numVertices, edges), encoding="utf-8")
        instances.append({"name": name, "graph_file": f"graphs/{name}.col", "graph_sha256": hashlib.sha256(graphFile.read_bytes()).hexdigest(), "vertices": numVertices, "edges": len(edges)})
    manifest: Path = folder / "Manifest.json"
    manifest.write_text(json.dumps({"instances": instances}), encoding="utf-8")
    return manifest


def _runRunner(tmp_path: Path, experimentId: str, *options: str) -> Path:
    command: list[str] = [
        sys.executable, "-m", "tools.experiment.runExperiment", "--experiment-id", experimentId, "--manifest", str(_writeManifest(tmp_path / "data")),
        "--results-dir", str(tmp_path / "results"), "--methods", *METHODS, "--allow-tracked-changes", *options,
    ]
    completed = subprocess.run(command, cwd=REPOSITORY_ROOT, capture_output=True, text=True, timeout=120)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return tmp_path / "results" / experimentId


def _records(experimentDir: Path) -> list[dict]:
    return [json.loads(line) for line in (experimentDir / "Runs.jsonl").read_text(encoding="utf-8").splitlines()]


def test_runner_solves_checks_and_records_every_attempt(tmp_path: Path) -> None:
    experimentDir: Path = _runRunner(tmp_path, "workflow", "--repetitions", "2", "--time-limit", "10")

    records: list[dict] = _records(experimentDir)
    # Instances in manifest order, repetitions ascending, method order rotated by repetition.
    assert [(r["instance"], r["repetition"], r["method"]) for r in records] == [
        (name, repetition, method)
        for name in GRAPHS
        for repetition, order in [(1, METHODS), (2, METHODS[1:] + METHODS[:1])]
        for method in order
    ]
    for record in records:
        numVertices, edges = GRAPHS[record["instance"]]
        assert record["status"] == "OPTIMAL", record
        assert record["bandwidth"] == record["lower_bound"] == bruteForceBandwidth(numVertices, edges)
        labeling: list[int] = json.loads((experimentDir / record["labeling_file"]).read_text(encoding="utf-8"))
        assert checkLabeling(numVertices, edges, labeling) == record["bandwidth"]
        assert record["requested_seed"] == record["repetition"] - 1
        assert record["peak_rss_mib"] > 0 and record["validation_seconds"] >= 0 and record["error"] is None
        assert (experimentDir / record["log_file"]).is_file() and (experimentDir / record["trace_file"]).is_file()
    config: dict = json.loads((experimentDir / "Config.json").read_text(encoding="utf-8"))
    assert {entry["availability"] for entry in config["backend_inventory"].values()} == {"AVAILABLE"}
    assert (experimentDir / "DatasetManifest.json").is_file() and json.loads((experimentDir / "Environment.json").read_text(encoding="utf-8"))["git_commit"]


def test_runner_kills_a_worker_at_the_deadline_without_claiming_a_result(tmp_path: Path) -> None:
    # A zero budget and no grace make the runner kill each worker at once, before it saves any labeling.
    experimentDir: Path = _runRunner(tmp_path, "killed", "--repetitions", "1", "--time-limit", "0", "--grace", "0", "--instances", "cycle6")

    records: list[dict] = _records(experimentDir)
    assert len(records) == len(METHODS)
    for record in records:
        assert (record["status"], record["termination_reason"], record["bandwidth"], record["labeling_file"]) == ("UNKNOWN", "runner_kill", None, None), record
        assert record["worker_exit_code"] == -9