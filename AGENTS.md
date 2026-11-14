# Bandwidth Minimization

## Project Brief

Modern Issues in Computer Science, major assignment 2 (BTL 2). The project compares exact SAT, constraint programming (CP), and integer linear programming (ILP) approaches to the graph Bandwidth Minimization Problem. It produces the solver code, the experiment results, and the group report. Nguyen Thanh Binh is Member 3 (ILP).

## Project Index

| Question or task | Resource |
|---|---|
| Who owns what, mandatory scope, completion criteria | [Task.md](Task.md) |
| Mathematical problem and encoding notes | [docs/Problem.md](docs/Problem.md) |
| Shared input, output, status meanings, and measurement rules | [docs/ExperimentContract.md](docs/ExperimentContract.md) |
| Dataset attribution and limitations | [data/HarwellBoeing/README.md](data/HarwellBoeing/README.md) |
| Exact dataset files, source URLs, and checksums | [data/HarwellBoeing/Manifest.json](data/HarwellBoeing/Manifest.json) |
| Download the dataset and rebuild the graphs | [tools/prepare_dataset.py](tools/prepare_dataset.py) |
| SAT solvers: order and pairwise encodings, repeated and incremental solving | [scripts/sat/](scripts/sat/), entry point `solveBMPSAT` in [SATSolverWrapper.py](scripts/sat/SATSolverWrapper.py) |
| CP solvers: OR-Tools CP-SAT and IBM CP Optimizer | [scripts/cp/](scripts/cp/), entry point [runCP.py](scripts/cp/runCP.py) |
| ILP solvers: one formulation on IBM CPLEX and Gurobi | [scripts/ilp/](scripts/ilp/), entry point `ILPSolver` in [ilpSolver.py](scripts/ilp/ilpSolver.py); formulation and correctness argument in the report section [ilpFormulation.tex](report/sections/ilpFormulation.tex) |
| Load a `.col` graph, verify it against the manifest, check a labeling | [scripts/shared/](scripts/shared/): [graphInput.py](scripts/shared/graphInput.py) and [labeling.py](scripts/shared/labeling.py). Every method uses these; none keeps its own loader or checker |
| Brute-force oracle and the correctness-gate graphs for any method's tests | [tests/oracle.py](tests/oracle.py) |
| Which workflow tests a change selects | [tools/testSelection.json](tools/testSelection.json), read by [tools/selectTests.py](tools/selectTests.py). A path that no rule maps selects the full suite |
| Run experiments: one fresh worker process per attempt, deadline kill, peak memory, and the `results/<experiment-id>/` files of the contract | [tools/experiment/](tools/experiment/), entry point [runExperiment.py](tools/experiment/runExperiment.py); the six method IDs map to solver calls in [methods.py](tools/experiment/methods.py) |
| Write a report section | Each owner's LaTeX files in [report/sections/](report/sections/) and their own `.bib` file in [report/](report/); who writes what is in [Task.md](Task.md#report-ownership). [report/main.tex](report/main.tex), owned by Member 3, includes them; build it from `report/` with `latexmk -pdf -outdir=<scratch folder> main.tex`, which needs the `texlive-science` system package |

`results/` does not exist yet. Session scratch files belong in ignored `tmp/`.

## Commands

Python 3.10 or newer is required. Run every command from the repository root. [requirements.txt](requirements.txt) pins the environment frozen for the main campaign.

| Task | Command |
|---|---|
| Create the environment and install the pinned solver and test dependencies | `uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt` |
| Run the tests that the committed changes select, in a clean checkout of `HEAD`; required after the last commit of a request. When the request made several commits, add `--base <commit before the first one>` | `.venv/bin/python tools/selectTests.py` |
| Run every workflow test, required before merging into `main` and before a campaign | `.venv/bin/python -m pytest tests scripts/cp/test_cp_workflow.py` |
| Run the smoke experiment (3 instances, 10 s, once per method); when `GRB_LICENSE_FILE` or `CPO_EXECUTABLE` is not exported, the runner uses the defaults at the top of [runExperiment.py](tools/experiment/runExperiment.py), and a method whose full solver it cannot find is recorded UNAVAILABLE | `.venv/bin/python -m tools.experiment.runExperiment --experiment-id smoke-<date> --instances ibm32 bcspwr01 bcsstk01 --repetitions 1 --time-limit 10` |
| Run the main campaign (198 attempts, up to 16.5 hours plus overhead); add `--resume` to continue it after an interruption | `.venv/bin/python -m tools.experiment.runExperiment --experiment-id <id>` |
| Download the dataset again, without third-party packages | `python tools/prepare_dataset.py` |
| Solve one graph with CP | `python scripts/cp/runCP.py data/HarwellBoeing/graphs/ibm32.col --time-limit 10 --output tmp/cp-ibm32` |
| Check which CP backends are available | `python -m scripts.cp.checkSolvers --output tmp/cp-backends.json` |
| Run only the CP workflow tests | `python -m pytest scripts/cp/test_cp_workflow.py` |

`tools/prepare_dataset.py` updates retrieval timestamps and checksums, so preserve the committed manifest for an experiment before refreshing the data.

The `python3 -m venv` route fails on this laptop, because the `python3.12-venv` system package is not installed; `uv` needs no system package.

Gurobi reads its license from the file named by `GRB_LICENSE_FILE`, for example `export GRB_LICENSE_FILE=~/Documents/CacVanDeHienDaiCuaKHMT/Exercises/gurobi.lic`. Without it, the Gurobi tests are skipped. Git ignores `*.lic`; never commit a license file.

The `cplex` package from PyPI is the free Community Edition, limited to 1,000 variables and 1,000 constraints, and every committed instance exceeds the limit. IBM ILOG CPLEX Optimization Studio 22.2 (free for students through the IBM Academic Initiative) removes the limit, but it ships no Python package. After installing Studio, run `.venv/bin/docplex config --upgrade <Studio folder>`: it copies the unlimited CPLEX library and the `cpoptimizer` program into the venv. Run it again after every reinstall of the `cplex` package.

The CP tests skip the IBM CP Optimizer cases when the `cpoptimizer` program is missing. Set `CPO_EXECUTABLE` to `<Studio folder>/cpoptimizer/bin/x86-64_linux/cpoptimizer`, and `REQUIRE_CPO=1` to turn the skip into a failure. The SAT code has no automated tests yet.

## Dataset

The agreed source is the **Harwell–Boeing Sparse Matrix Collection**, distributed by NIST Matrix Market. This repository includes an initial subset of 12 instances, with 32–1,000 vertices. The supplied reference paper uses 113 instances, so the committed subset is not the full benchmark.

## Team Branches

Teammates push their work to branches that are not named `main`. The owners below come from the commit authors.

| Branch | Owner | Work |
|---|---|---|
| `SAT_main` | Trần Tuấn Cường | SAT, under `scripts/sat/` |
| `CP` | Cao Thế Mạnh | CP, under `scripts/cp/` |

Run `git fetch --all --prune` before reading or merging these branches. Why: a branch on GitHub is invisible locally until it is fetched. On 2026-11-09, `CP` was missing from the local branch list until the fetch.

## Project Rules

A program that calls `solveBMPSAT` MUST run it under an `if __name__ == "__main__":` guard. Why: [deadlineRunner.py](scripts/sat/deadlineRunner.py) runs the SAT search in a child process so it can kill it at the deadline, and starting that child imports the main script again.

`README.md` is a copy of this file. MUST NOT edit `README.md` directly. After changing this file, run `cp AGENTS.md README.md` and commit both files together. Why: developer decision on 2026-11-09, so that teammates reading the repository page and agents reading this file see the same content.