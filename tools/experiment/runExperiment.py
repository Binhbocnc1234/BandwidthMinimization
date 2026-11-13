"""Run an experiment campaign under docs/ExperimentContract.md and write results/<experiment-id>/.

Example, the smoke runs: python -m tools.experiment.runExperiment --experiment-id smoke-1 --instances ibm32 bcspwr01 bcsstk01 --repetitions 1 --time-limit 10
Run it from the repository root. Each attempt runs in a fresh worker process, one at a time.
"""

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from scripts.shared.graphInput import ManifestInstance, loadManifestInstance, readManifest
from scripts.shared.labeling import checkLabeling, commonLowerBound
from tools.experiment.environment import backendInventory, describeEnvironment, gitRevision
from tools.experiment.methods import METHOD_IDS, REPOSITORY_ROOT, SAT_METHOD_IDS
from tools.experiment.worker import attemptPaths, readPeakRssKiB, writeJsonAtomically

SCHEMA_VERSION: int = 1
DEFAULT_MANIFEST: Path = REPOSITORY_ROOT / "data" / "HarwellBoeing" / "Manifest.json"
SAT_SKIPPED_INSTANCES: dict[str, str] = {
    name: "SAT order encoding needs more memory than the 15 GiB laptop has; see the Experiment Conditions section of docs/ExperimentContract.md"
    for name in ["bcspwr05", "bcsstk20", "sherman1"]
}
POLL_INTERVAL_SECONDS: float = 0.05
MEMORY_SAMPLE_EVERY_POLLS: int = 10


def sampleGroupPeakRssKiB(processGroup: int) -> int:
    """The largest VmHWM among the live processes of a process group."""
    peakKiB: int = 0
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            # The command name in field 2 may contain spaces, so fields are counted after its closing parenthesis: state, parent pid, process group.
            if int((entry / "stat").read_text(encoding="utf-8").rsplit(")", 1)[1].split()[2]) == processGroup:
                peakKiB = max(peakKiB, readPeakRssKiB(entry.name))
        except FileNotFoundError:
            # The process ended between the listing and the read.
            continue
    return peakKiB


def runAttempt(experimentDir: Path, spec: dict, killAfterSeconds: float) -> tuple[int, float, bool, float]:
    """Run one worker; kill its whole process group after killAfterSeconds. Returns (exit code, sampled peak RSS in MiB, killed, kill time on time.monotonic).

    The sampled peak covers the live processes of the group every MEMORY_SAMPLE_EVERY_POLLS polls, so it can miss the last half second and short-lived children. It is used only when the worker reports no peak of its own.
    """
    paths: dict[str, Path] = attemptPaths(experimentDir, spec["runId"])
    writeJsonAtomically(paths["spec"], spec)
    with open(paths["log"], "w", encoding="utf-8") as logStream:
        # A new session makes the worker a process-group leader, so one kill also ends the cpoptimizer program and the SAT search child.
        worker = subprocess.Popen(
            [sys.executable, "-m", "tools.experiment.worker", str(paths["spec"])], cwd=REPOSITORY_ROOT, stdout=logStream, stderr=subprocess.STDOUT, start_new_session=True
        )
        killAt: float = time.monotonic() + killAfterSeconds
        killed: bool = False
        killTime: float = 0.0
        sampledPeakKiB: int = 0
        polls: int = 0
        while True:
            if time.monotonic() >= killAt:
                sampledPeakKiB = max(sampledPeakKiB, sampleGroupPeakRssKiB(worker.pid))
                os.killpg(worker.pid, signal.SIGKILL)
                killed, killTime = True, time.monotonic()
                worker.wait()
                break
            if worker.poll() is not None:
                break
            if polls % MEMORY_SAMPLE_EVERY_POLLS == 0:
                sampledPeakKiB = max(sampledPeakKiB, sampleGroupPeakRssKiB(worker.pid))
            polls += 1
            time.sleep(POLL_INTERVAL_SECONDS)
        try:
            # Ends descendants that outlived a worker that exited by itself.
            os.killpg(worker.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return worker.returncode, sampledPeakKiB / 1024, killed, killTime


def buildRecord(experimentDir: Path, spec: dict, graph: tuple[int, list], exitCode: int, sampledPeakRssMiB: float, killed: bool, killTime: float) -> dict:
    paths: dict[str, Path] = attemptPaths(experimentDir, spec["runId"])
    numVertices, edges = graph
    result: dict = json.loads(paths["result"].read_text(encoding="utf-8")) if paths["result"].is_file() else {}
    progress: dict = json.loads(paths["progress"].read_text(encoding="utf-8")) if paths["progress"].is_file() else {}
    record: dict = {
        "schema_version": SCHEMA_VERSION, "experiment_id": spec["experimentId"], "run_id": spec["runId"], "attempt": spec["attempt"],
        "instance": spec["instance"], "input_sha256": spec["graphSha256"], "n": numVertices, "m": len(edges),
        "method": spec["method"], "backend": result.get("backend"), "backend_version": result.get("backendVersion"), "git_commit": spec["gitCommit"],
        "repetition": spec["repetition"], "requested_seed": spec["seed"], "effective_seed": result.get("effectiveSeed"), "threads": result.get("threads"),
        "time_limit_seconds": spec["timeLimitSeconds"], "termination_reason": result.get("terminationReason"), "status": result.get("status"),
        "bandwidth": result.get("bandwidth"), "lower_bound": result.get("lowerBound"), "initial_upper_bound": result.get("initialUpperBound"), "incumbent_origin": result.get("incumbentOrigin"),
        "elapsed_seconds": result.get("elapsedSeconds"), "construction_seconds": result.get("constructionSeconds"), "search_seconds": result.get("searchSeconds"), "validation_seconds": None,
        "peak_rss_mib": round(result.get("peakRssMiB", sampledPeakRssMiB), 1), "peak_rss_scope": "worker" if "peakRssMiB" in result else "sampled",
        "variables": result.get("variables"), "constraints": result.get("constraints"), "clauses": result.get("clauses"),
        "labeling_file": None, "trace_file": paths["trace"].relative_to(experimentDir).as_posix() if paths["trace"].is_file() else None,
        "log_file": paths["log"].relative_to(experimentDir).as_posix(), "error": result.get("error"),
        "deadline_overshoot_seconds": result.get("deadlineOvershootSeconds"), "native_status": result.get("nativeStatus"),
        "hint_submitted": result.get("hintSubmitted"), "hint_accepted": result.get("hintAccepted"), "worker_exit_code": exitCode,
    }
    if paths["solverLog"].is_file():
        record["solver_log_file"] = paths["solverLog"].relative_to(experimentDir).as_posix()

    if killed:
        # The worker missed its own deadline by the whole grace period. Its saved incumbent still counts; the kill proves nothing about the bound.
        record["termination_reason"] = "runner_kill"
        record["lower_bound"] = commonLowerBound(edges)
        record["incumbent_origin"] = progress.get("incumbentOrigin")
        if progress.get("solveCalledAtMonotonic") is not None:
            record["elapsed_seconds"] = killTime - progress["solveCalledAtMonotonic"]
            record["deadline_overshoot_seconds"] = max(0.0, record["elapsed_seconds"] - spec["timeLimitSeconds"])
    elif not result:
        record.update(status="ERROR", termination_reason="crash", error=f"worker exited with code {record['worker_exit_code']} and wrote no result; -9 can be the OS out-of-memory killer. See {record['log_file']}.")
        return record
    elif "error" in result:
        record.update(status="ERROR", termination_reason="error")
        return record

    if not paths["labeling"].is_file():
        record.update(status="UNKNOWN", bandwidth=None)
        return record
    validationStart: float = time.perf_counter()
    try:
        checkedBandwidth: int = checkLabeling(numVertices, edges, json.loads(paths["labeling"].read_text(encoding="utf-8")))
    except ValueError as error:
        record.update(status="ERROR", error=f"saved labeling failed the shared checker: {error!r}")
        return record
    record["validation_seconds"] = time.perf_counter() - validationStart
    record["labeling_file"] = paths["labeling"].relative_to(experimentDir).as_posix()
    if killed:
        record["bandwidth"] = checkedBandwidth
        record["status"] = "OPTIMAL" if checkedBandwidth == record["lower_bound"] else "FEASIBLE"
    elif checkedBandwidth != record["bandwidth"]:
        record.update(status="ERROR", error=f"method claims bandwidth {record['bandwidth']}, but its saved labeling checks to {checkedBandwidth}")
    return record


def parseArguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--experiment-id", required=True, help="results/<experiment-id>/ receives the artifacts")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--instances", nargs="+", help="instance names; default: every manifest instance, in manifest order")
    parser.add_argument("--methods", nargs="+", choices=METHOD_IDS, default=METHOD_IDS, help="method order of repetition 1")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--time-limit", type=float, default=300.0, help="seconds of model construction plus search per attempt")
    parser.add_argument("--grace", type=float, default=60.0, help="seconds after the time limit before the runner kills a worker; covers process startup, imports and license checks, which the budget excludes")
    parser.add_argument("--results-dir", type=Path, default=REPOSITORY_ROOT / "results")
    parser.add_argument("--resume", action="store_true", help="continue an experiment; skip every (instance, method, repetition) that already has a record")
    parser.add_argument("--allow-tracked-changes", action="store_true", help="run although tracked files differ from the commit; the results then match no commit")
    return parser.parse_args()


def main() -> None:
    arguments: argparse.Namespace = parseArguments()
    experimentDir: Path = arguments.results_dir / arguments.experiment_id
    gitCommit, trackedChanges = gitRevision(REPOSITORY_ROOT)
    if trackedChanges and not arguments.allow_tracked_changes:
        sys.exit("tracked files differ from the commit; commit them, or pass --allow-tracked-changes for a run that is not part of the comparison")
    cpoExecutable: str | None = os.environ.get("CPO_EXECUTABLE")
    manifest: list[ManifestInstance] = readManifest(arguments.manifest)
    if arguments.instances:
        unknown: set[str] = set(arguments.instances) - {instance.name for instance in manifest}
        if unknown:
            sys.exit(f"instances not in {arguments.manifest}: {sorted(unknown)}")
        manifest = [instance for instance in manifest if instance.name in arguments.instances]

    if arguments.resume:
        config: dict = json.loads((experimentDir / "Config.json").read_text(encoding="utf-8"))
        if config["git_commit"] != gitCommit:
            sys.exit(f"the experiment ran at commit {config['git_commit']}, but HEAD is {gitCommit}")
        inventory: dict[str, dict] = config["backend_inventory"]
    else:
        if experimentDir.exists():
            sys.exit(f"{experimentDir} exists; choose a new --experiment-id, or pass --resume")
        (experimentDir / "Solutions").mkdir(parents=True)
        (experimentDir / "Logs").mkdir()
        shutil.copyfile(arguments.manifest, experimentDir / "DatasetManifest.json")
        writeJsonAtomically(experimentDir / "Environment.json", describeEnvironment(REPOSITORY_ROOT, cpoExecutable))
        inventory = backendInventory(arguments.methods, cpoExecutable)
        writeJsonAtomically(experimentDir / "Config.json", {
            "experiment_id": arguments.experiment_id, "created_at_utc": datetime.now(timezone.utc).isoformat(), "git_commit": gitCommit,
            "dataset_manifest_sha256": hashlib.sha256(arguments.manifest.read_bytes()).hexdigest(),
            "instances": [instance.name for instance in manifest], "method_order": arguments.methods, "method_order_rule": "repetition r runs method_order rotated left by r - 1",
            "repetitions": arguments.repetitions, "seeds": {str(r): r - 1 for r in range(1, arguments.repetitions + 1)},
            "time_limit_seconds": arguments.time_limit, "kill_grace_seconds": arguments.grace, "threads": 1,
            "backend_inventory": inventory,
            "sat_skipped_instances": {name: reason for name, reason in SAT_SKIPPED_INSTANCES.items() if name in {instance.name for instance in manifest}},
        })
    for method, entry in inventory.items():
        if entry["availability"] != "AVAILABLE":
            print(f"UNAVAILABLE {method}: {entry['reason']}", flush=True)

    runsFile: Path = experimentDir / "Runs.jsonl"
    earlier: list[dict] = [json.loads(line) for line in runsFile.read_text(encoding="utf-8").splitlines()] if runsFile.is_file() else []
    for instance in manifest:
        graph: tuple[int, list] = loadManifestInstance(instance)
        for repetition in range(1, arguments.repetitions + 1):
            shift: int = (repetition - 1) % len(arguments.methods)
            for method in arguments.methods[shift:] + arguments.methods[:shift]:
                if inventory[method]["availability"] != "AVAILABLE":
                    continue
                if method in SAT_METHOD_IDS and instance.name in SAT_SKIPPED_INSTANCES:
                    continue
                sameRun: list[dict] = [r for r in earlier if (r["instance"], r["method"], r["repetition"]) == (instance.name, method, repetition)]
                if sameRun:
                    continue
                spec: dict = {
                    "experimentId": arguments.experiment_id, "experimentDir": str(experimentDir.resolve()), "runId": f"{instance.name}-{method}-r{repetition}-a1", "attempt": 1,
                    "instance": instance.name, "graphPath": str(instance.graphPath), "graphSha256": instance.graphSha256, "numVertices": instance.numVertices, "numEdges": instance.numEdges,
                    "method": method, "repetition": repetition, "seed": repetition - 1, "timeLimitSeconds": arguments.time_limit, "cpoExecutable": cpoExecutable, "gitCommit": gitCommit,
                }
                exitCode, sampledPeakRssMiB, killed, killTime = runAttempt(experimentDir, spec, arguments.time_limit + arguments.grace)
                record: dict = buildRecord(experimentDir, spec, graph, exitCode, sampledPeakRssMiB, killed, killTime)
                with open(runsFile, "a", encoding="utf-8") as stream:
                    stream.write(json.dumps(record) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                print(f"{record['run_id']}: {record['status']} bandwidth={record['bandwidth']} lb={record['lower_bound']} elapsed={record['elapsed_seconds']} rss={record['peak_rss_mib']}MiB {record['termination_reason']}", flush=True)


if __name__ == "__main__":
    main()