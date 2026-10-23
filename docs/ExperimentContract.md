# Experiment Contract

Summary: Shared graph input, solver result format, experiment conditions, and evidence required for the team's SAT, CP, and ILP comparison.

These are team decisions authorized by the leader for implementation. They are not claims that experiments or verification have already run. Owners and completion criteria are in [Task.md](../Task.md).

## Graph Input

- Input is an undirected, unweighted graph in a UTF-8 `.col` file. Lines beginning with `c` are comments; blank lines are ignored.
- Exactly one `p edge n m` line precedes the edges. Require integer `n >= 1` and `m >= 0`.
- Each `e u v` line declares one edge, with integer IDs satisfying `1 <= u < v <= n`. Reject self-loops, duplicate edges, extra record fields, unknown record types, and an edge count different from `m`.
- Keep every vertex `1..n`, including isolated vertices and vertices outside the largest component. The shared in-memory input is `n: int` and a lexicographically sorted list of `(u, v)` integer pairs.
- Use committed files from the [dataset manifest](../data/HarwellBoeing/Manifest.json). Verify SHA-256 before a run; an absent file or mismatch stops that experiment rather than causing a silent download or substitution.
- The `.col` file is the common solver input. Matrix parsing belongs only to dataset preparation. Regenerating or expanding the dataset produces a reviewed manifest update and a new experiment configuration.

Example input for a triangle:

```text
p edge 3 3
e 1 2
e 1 3
e 2 3
```

## Labeling and Independent Checking

`labeling[v - 1]` is the position assigned to vertex `v`. A valid labeling is a JSON array containing every integer `1..n` exactly once. The shared checker verifies the permutation and independently computes the maximum position difference over the input edges, using the [edgeless convention](Problem.md#mathematical-target).

A claimed objective must equal the recomputed bandwidth. Failed validation is `ERROR`, never a feasible result. The checker does not prove optimality; the method must supply separate evidence.

## Bounds and Optimality

Use the identity labeling `labeling[v - 1] = v` as the common initial incumbent. Compute its actual bandwidth as the initial upper bound, and share this same incumbent across all methods. For any graph with an edge, the common initial lower bound is 1; otherwise it is 0. The initial incumbent counts as feasible but does not count as a solver improvement.

For the primary SAT comparison, start at one less than the incumbent bandwidth and decrease the candidate bound by exactly 1 after each SAT result. Keep the encoding and bound schedule the same for repeated and incremental SAT. A SAT answer must be decoded and checked; a definitive UNSAT answer at the bound immediately below the last feasible bandwidth proves that incumbent optimal. Reaching the common lower bound also establishes optimality. Do not call a solver with a negative bound.

CP and ILP minimize the same objective directly, with the common initial incumbent supplied as a hint or start when the backend supports one; record whether the backend accepted it. Their native termination result and certified objective bound must support every optimality claim. Round numerical bounds only according to a documented backend tolerance and the integer nature of BMP; never infer an optimum from two similar floating-point numbers.

Improved initial bounds, a different search schedule, or a heuristic warm start are allowed as separate extension variants. Apply the same extension to compared methods where applicable and identify the change explicitly.

## Required Comparison Matrix

| Method ID | Model and solving scheme | Backend | Owner |
|---|---|---|---|
| `sat_order_repeated` | Order encoding, fresh solver per bound | CaDiCaL through PySAT | Member 1 |
| `sat_order_incremental` | Order encoding, persistent solver | The same CaDiCaL build | Member 1 |
| `cp_ortools` | CP formulation | OR-Tools CP-SAT | Member 2 |
| `cp_cpo` | CP formulation | IBM CPLEX CP Optimizer | Member 2 |
| `ilp_cplex` | ILP formulation | IBM CPLEX MIP | Member 3 |
| `ilp_gurobi` | The same ILP formulation | Gurobi | Member 3 |

The table contains four model/scheme variants and six backend configurations. Repeated/incremental SAT does not apply to the CP and ILP rows. The repeated order-encoding variant is the controlled baseline for measuring solver reuse, not an assumption that incremental SAT must be faster.

Use `sat_pairwise_incremental` for the optional pairwise extension; a separate `sat_pairwise_repeated` comparison is optional. A backend setup failure is recorded as `UNAVAILABLE` in the campaign inventory with its reason; it is not a solver timeout or a completed comparison. Do not substitute another backend under an existing method ID.

## Experiment Conditions

| Setting | Main comparison decision |
|---|---|
| Instance set | All 12 instances in the committed manifest; identify this as the initial subset, not the full paper benchmark |
| Machine | One recorded machine and OS for the complete comparison campaign |
| Concurrency | One active experiment; one solver worker/thread per run |
| Time budget | 300 seconds per instance, method, and repetition for model construction plus optimization |
| Repetitions | Three fresh-process runs per instance/method with run IDs 1, 2, 3 |
| Seeds | 0, 1, 2 respectively where a backend supports seeds; record the actual backend seed or `null` if unsupported |
| Run order | Instances in manifest order; repetitions ascending; rotate the method order by repetition |
| Memory | No separate team-imposed memory cap; record available RAM and per-run peak resident memory in MiB |
| Backend settings | One thread, the assigned seed, and declared time settings; record every other nondefault option |
| Preparation | Freeze the Git commit, dataset/configuration hashes, exact dependencies, and solver versions before the campaign |

These limits bound experiment cost; they are not a claim that a method solves any instance within the budget. The six required variants give 216 runs, with at most 18 hours of budgeted model construction and optimization. Setup, validation, and cleanup add time outside that estimate. The 12-instance subset limits conclusions about the full collection.

Before the campaign, smoke-test `ibm32`, `bcspwr01`, and `bcsstk01` once per backend with a 10-second budget. These runs verify integration and record failures; exclude them from the main performance comparison. A smoke timeout alone does not imply an integration error.

Start the measured timer after input loading and checksum verification, immediately before any method-specific preprocessing or model construction. Stop at termination or the deadline. Include every SAT bound test in the same budget; do not reset the budget per bound. Exclude process startup/imports, the shared input loader, final independent checking, and result serialization; record validation time separately.

The runner enforces the overall budget and each backend receives the remaining time. Persist incumbents when found so a terminated process does not lose its best known labeling. A backend ignoring the deadline is interrupted; never interpret that interruption as an infeasibility proof. Record actual elapsed time, termination reason, and any deadline overshoot. Preserve errors and earlier failed attempts rather than replacing them with a later passing run.

No other benchmark run may overlap a measured run. Record unexpected competing load or an OS out-of-memory termination. Treat affected results as interrupted attempts, with a reason, and rerun under the frozen conditions rather than comparing their timing as ordinary runs.

## Result Artifacts

The leader's runner writes `results/<experiment-id>/Config.json`, `Environment.json`, `DatasetManifest.json`, `Runs.jsonl`, `Solutions/`, and `Logs/`. The manifest is the exact dataset inventory used, not a URL to a changing file. Every attempt has a unique `run_id`; paths stored inside artifacts are relative to that experiment directory. Commit the records and referenced artifacts used by the paper.

Each JSON Lines record in `Runs.jsonl` contains the following fields. Use JSON `null` for unavailable measurements; do not use zero to mean missing.

| Fields | Meaning |
|---|---|
| `schema_version`, `experiment_id`, `run_id`, `attempt` | Version 1 schema, campaign identity, unique attempt identity, and retry number |
| `instance`, `input_sha256`, `n`, `m` | Input identity and graph dimensions |
| `method`, `backend`, `backend_version`, `git_commit` | Model/scheme identity, actual backend, and source revision |
| `repetition`, `requested_seed`, `effective_seed`, `threads` | Actual execution settings |
| `time_limit_seconds`, `termination_reason`, `status` | Budget, cause of termination, and normalized result |
| `bandwidth`, `lower_bound`, `initial_upper_bound`, `incumbent_origin` | Checked objective, proved lower bound, common starting bound, and `identity` or `solver` |
| `elapsed_seconds`, `construction_seconds`, `search_seconds`, `validation_seconds` | Measured durations; construction plus search partition the elapsed budget |
| `peak_rss_mib`, `variables`, `constraints`, `clauses` | Resource/model size measurements; SAT `clauses` is null for CP/ILP |
| `labeling_file`, `trace_file`, `log_file`, `error` | Relative artifact paths and error details; no credentials or license contents |

SAT traces record every attempted bound, start/end times, SAT/UNSAT/UNKNOWN outcome, and formula size. The size summary reports the largest number of active variables/clauses reached in that run; native CP/ILP counts identify whether presolve has been applied. `labeling_file` contains the labeling JSON array and is required for a feasible or optimal record.

`Environment.json` records CPU model, physical/logical core counts, RAM, OS, Python/package/solver versions, solver settings, and the timing/memory measurement mechanism. `Config.json` records the method order, instances, budgets, seeds, backend availability, and all shared or variant-specific settings.

## Status Meanings

| Status | Required evidence |
|---|---|
| `OPTIMAL` | A checked labeling plus definitive SAT lower-bound evidence or a native CP/ILP optimality result |
| `FEASIBLE` | A checked incumbent exists but optimality has not been established; timeout may be the termination reason |
| `UNKNOWN` | No checked incumbent and no proof, for example after early interruption |
| `ERROR` | Invalid input/output, exception, crash, or inconsistent solver result; retain the error and log |

The initial identity labeling means a valid initialized optimization run already has a feasible incumbent. Therefore, a timed-out run normally reports `FEASIBLE` with its incumbent origin and `termination_reason = "time_limit"`, rather than losing the available labeling. `UNKNOWN` remains possible if interruption occurs before initialization.

For these valid BMP inputs, the unconstrained optimization problem is always feasible. UNSAT/infeasible is expected for individual decision bounds; an overall CP/ILP infeasibility claim is an `ERROR` requiring investigation, not a successful optimization result. `UNAVAILABLE` belongs to the campaign inventory, not this per-run status set.

## Correctness and Analysis Gate

Before performance runs, every implemented method must pass workflow scenarios for paths, cycles, complete graphs, disconnected graphs, and edgeless graphs. For graphs of at most 8 vertices, the shared test oracle enumerates permutations and evaluates the objective independently of every SAT/CP/ILP model. Each backend must return valid labelings and agree with the oracle's optimum. Record a nonzero executed test count and keep performance measurements separate from correctness tests.

Compare proved-optimal counts, checked incumbent bandwidths, deadline outcomes, and runtime. Report median and range over the three repetitions; show all raw records. Only compare times to prove an optimum when the methods proved the same optimum. Report memory with its measurement scope and do not assume a Python-only allocation count includes native solver memory.

Use cnsplots for report charts. Cite literature objective values as external reference values and distinguish proved optima from best-known upper bounds. Do not compare literature runtimes with local runtimes as if the hardware and budgets were identical.
