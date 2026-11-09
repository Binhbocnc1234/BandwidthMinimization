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
| SAT solvers: order and pairwise encodings, repeated and incremental solving | [script/sat/](script/sat/), entry point `solveBMPSAT` in [SATSolverWrapper.py](script/sat/SATSolverWrapper.py) |
| CP solvers: OR-Tools CP-SAT and IBM CP Optimizer | [script/cp/](script/cp/), entry point [runCP.py](script/cp/runCP.py) |

[Task.md](Task.md) assigns `scripts/sat/`, `scripts/cp/`, `scripts/ilp/`, and `scripts/shared/`, but the SAT and CP code is committed under `script/`. The ILP code, the shared loader and checker, `tests/`, `results/`, and `report/` do not exist yet. Session scratch files belong in ignored `tmp/`.

## Commands

Python 3.10 or newer is required. Run every command from the repository root. Solver dependencies are not pinned yet, because [Task.md](Task.md#shared-input-output-and-conditions) freezes one environment before the main campaign.

| Task | Command |
|---|---|
| Install the solver and test dependencies | `pip install pytest python-sat ortools docplex` |
| Download the dataset again, without third-party packages | `python tools/prepare_dataset.py` |
| Solve one graph with CP | `python script/cp/runCP.py data/HarwellBoeing/graphs/ibm32.col --time-limit 10 --output tmp/cp-ibm32` |
| Check which CP backends are available | `python -m script.cp.checkSolvers --output tmp/cp-backends.json` |
| Run the CP workflow tests, required after a change under `script/cp/` | `python -m pytest script/cp/test_cp_workflow.py` |

`tools/prepare_dataset.py` updates retrieval timestamps and checksums, so preserve the committed manifest for an experiment before refreshing the data.

The CP tests skip the IBM CP Optimizer cases when the `cpoptimizer` program is missing. Set `CPO_EXECUTABLE` to its path, and `REQUIRE_CPO=1` to turn the skip into a failure. The SAT code has no automated tests yet.

## Dataset

The agreed source is the **Harwell–Boeing Sparse Matrix Collection**, distributed by NIST Matrix Market. This repository includes an initial subset of 12 instances, with 32–1,000 vertices. The supplied reference paper uses 113 instances, so the committed subset is not the full benchmark.

## Team Branches

Teammates push their work to branches that are not named `main`. The owners below come from the commit authors.

| Branch | Owner | Work |
|---|---|---|
| `SAT_main` | Trần Tuấn Cường | SAT, under `script/sat/` |
| `CP` | Cao Thế Mạnh | CP, under `script/cp/` |

Run `git fetch --all --prune` before reading or merging these branches. Why: a branch on GitHub is invisible locally until it is fetched. On 2026-11-09, `CP` was missing from the local branch list until the fetch.

## Project Rules

A program that calls `solveBMPSAT` MUST run it under an `if __name__ == "__main__":` guard. Why: [deadlineRunner.py](script/sat/deadlineRunner.py) runs the SAT search in a child process so it can kill it at the deadline, and starting that child imports the main script again.

`README.md` is a copy of this file. MUST NOT edit `README.md` directly. After changing this file, run `cp AGENTS.md README.md` and commit both files together. Why: developer decision on 2026-11-09, so that teammates reading the repository page and agents reading this file see the same content.