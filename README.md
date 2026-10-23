# Bandwidth Minimization

Modern Issues in Computer Science — major assignment 2 (BTL 2).

Compare exact SAT, constraint programming (CP), and integer linear programming (ILP) approaches to the graph Bandwidth Minimization Problem.

## Start Here

Read [Task.md](Task.md) for the three-member allocation, mandatory scope, report ownership, and completion criteria. Nguyen Thanh Binh is the team leader and Member 3 (ILP).

Read the [problem definition](docs/Problem.md) before building a model. Use the [experiment contract](docs/ExperimentContract.md) for shared input, output, and measurement rules. These documents define the team's implementation decisions; they do not claim that a solver or experiment has already been completed.

## Dataset

The agreed source is the **Harwell–Boeing Sparse Matrix Collection**, distributed by NIST Matrix Market. This repository includes an initial subset of 12 instances, with 32–1,000 vertices. The supplied reference paper uses 113 instances; the committed subset is not the full benchmark. See the [dataset notes](data/HarwellBoeing/README.md) for attribution and limitations, and the [manifest](data/HarwellBoeing/Manifest.json) for exact files, source URLs, and checksums.

## Repository Layout

| Path | Purpose |
|---|---|
| [Task.md](Task.md) | Member responsibilities, dependencies, report ownership, and acceptance criteria |
| [docs/Problem.md](docs/Problem.md) | Mathematical problem and encoding notes |
| [docs/ExperimentContract.md](docs/ExperimentContract.md) | Shared implementation and experiment contracts |
| [data/HarwellBoeing/](data/HarwellBoeing/README.md) | Original matrices, derived graphs, and provenance |
| [tools/prepare_dataset.py](tools/prepare_dataset.py) | Dataset download and graph preparation entry point |

Future implementation uses `scripts/sat/`, `scripts/cp/`, `scripts/ilp/`, and `scripts/shared/`. Future workflow tests use `tests/`; validated experiment artifacts use `results/<experiment-id>/`; the paper uses `report/`. These paths are assigned in Task.md and are created when their owners add the implementation. Session scratch files belong in ignored `tmp/`.

## Available Command

Dataset preparation requires Python 3.10 or newer and network access, without third-party packages. Run from the repository root:

```bash
python tools/prepare_dataset.py
```

This command downloads the selected instances again and updates retrieval timestamps and checksums. Preserve the committed manifest for an experiment before refreshing the data.

The repository currently provides the dataset and team plan. Solver commands, dependency locks, automated tests, and experiment results will be added by their assigned owners. A solver setup or test command must only be documented after the corresponding implementation exists.
