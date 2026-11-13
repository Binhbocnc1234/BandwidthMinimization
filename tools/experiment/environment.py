"""Environment.json contents and the backend inventory of Config.json, from docs/ExperimentContract.md."""

import os
import platform
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

PACKAGES: list[str] = ["python-sat", "ortools", "docplex", "cplex", "gurobipy"]


def _cpuInfo() -> tuple[str, int]:
    """CPU model and physical core count from /proc/cpuinfo; a physical core is one (physical id, core id) pair."""
    model: str = ""
    cores: set[tuple[str, str]] = set()
    physicalId: str = "0"
    for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "model name":
            model = value
        elif key == "physical id":
            physicalId = value
        elif key == "core id":
            cores.add((physicalId, value))
    return model, len(cores)


def _memoryMiB() -> dict[str, int]:
    fields: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition(":")
        fields[key] = int(value.split()[0]) // 1024
    return {"total_mib": fields["MemTotal"], "available_mib_at_start": fields["MemAvailable"]}


def _packageVersion(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def gitRevision(repositoryRoot: Path) -> tuple[str, bool]:
    """The commit, and whether tracked files differ from it."""
    commit: str = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repositoryRoot, check=True, capture_output=True, text=True).stdout.strip()
    changes: str = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=repositoryRoot, check=True, capture_output=True, text=True).stdout
    return commit, changes != ""


def describeEnvironment(repositoryRoot: Path, cpoExecutable: str | None) -> dict:
    cpuModel, physicalCores = _cpuInfo()
    commit, dirty = gitRevision(repositoryRoot)
    return {
        "cpu_model": cpuModel,
        "physical_cores": physicalCores,
        "logical_cores": os.cpu_count(),
        "ram": _memoryMiB(),
        "os": platform.platform(),
        "python": platform.python_version(),
        "packages": {name: _packageVersion(name) for name in PACKAGES},
        "cpo_executable": cpoExecutable,
        "git_commit": commit,
        "git_tracked_changes": dirty,
        "solver_settings": "one thread and the run's seed for every backend that takes one; CPLEX and Gurobi use a zero MIP gap. The exact parameters are in scripts/cp/cpSolver.py and scripts/ilp/ilpSolver.py at git_commit.",
        "timing": "time.perf_counter inside each method, started after input loading and the checksum check; elapsed time of a killed attempt is time.monotonic from the solve call to the kill",
        "memory": "peak_rss_mib is ru_maxrss from wait4 on the worker process: the largest resident set of the worker or of any descendant it waited for, not a sum, and it includes native solver memory",
    }


def _probe(method: str, cpoExecutable: str | None) -> None:
    """Raise when the backend of `method` cannot run a model of campaign size."""
    if method.startswith("sat_"):
        from pysat.solvers import Solver

        with Solver(name="cadical153", bootstrap_with=[[1]]) as solver:
            solver.solve()
    elif method == "cp_ortools":
        from ortools.sat.python import cp_model

        cp_model.CpModel()
    elif method == "cp_cpo":
        from scripts.cp.checkSolvers import checkSolver

        record: dict = checkSolver("cpo", cpoExecutable)
        if record["availability"] != "AVAILABLE_TINY_TEST":
            raise RuntimeError(record.get("error", record["availability"]))
    elif method == "ilp_gurobi":
        import gurobipy

        gurobipy.Env(params={"OutputFlag": 0}).dispose()
    elif method == "ilp_cplex":
        from docplex.mp.model import Model

        # 1,001 variables pass only the full CPLEX: the Community Edition refuses more than 1,000, and every committed instance needs more.
        with Model(name="sizeProbe") as model:
            variables = model.binary_var_list(1001)
            model.add_constraint(model.sum(variables) >= 1)
            model.minimize(model.sum(variables))
            if model.solve() is None:
                raise RuntimeError(f"CPLEX size probe failed: {model.solve_details.status}")
    else:
        raise ValueError(f"unknown method {method!r}")


def backendInventory(methods: list[str], cpoExecutable: str | None) -> dict[str, dict]:
    """AVAILABLE or UNAVAILABLE with the error, per method. An UNAVAILABLE method gets no runs, as the contract requires."""
    inventory: dict[str, dict] = {}
    for method in methods:
        try:
            _probe(method, cpoExecutable)
            inventory[method] = {"availability": "AVAILABLE", "reason": None}
        except Exception as error:
            inventory[method] = {"availability": "UNAVAILABLE", "reason": repr(error)}
    return inventory