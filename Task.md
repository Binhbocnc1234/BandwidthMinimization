# Team Tasks — BTL 2

Summary: Responsibilities, delivery criteria, integration order, and report ownership for the three-member BMP group.

## Goal and Scope

Implement exact BMP methods and compare their returned bandwidths, optimality certification, runtime, and memory use on the agreed [Harwell–Boeing dataset](data/HarwellBoeing/README.md).

**Order encoding is mandatory. Both repeated SAT and incremental SAT are mandatory for order encoding. Pairwise encoding is allowed but optional.** Students may develop additional methods or improvements and compare them experimentally. Extensions supplement the required methods; they do not replace them. This scope reflects the confirmed assignment clarification, rather than the original handout's pairwise requirement.

Repeated and incremental SAT are solving schemes for SAT encodings, not requirements to duplicate the CP or ILP models. The required method variants are order/repeated, order/incremental, CP optimization, and ILP optimization. Running a model with another backend is a backend comparison, not another SAT scheme. An optional pairwise encoding may use incremental SAT alone; implementing both schemes for pairwise is optional.

The reference paper supplies the BMP definition and benchmark background. Reimplementing its simulated annealing algorithm is not required. The mathematical target is defined in [Problem.md](docs/Problem.md).

## Members

| Member | Person | Main track | Shared responsibility |
|---|---|---|---|
| 1 | Name to be added | SAT: order encoding; optional pairwise | SAT search, bounds, and SAT experiment artifacts |
| 2 | Name to be added | CP | Dataset loader and independent solution checker |
| 3 | Nguyen Thanh Binh | ILP | Experiment runner, integration, and final report assembly |

## Member 1 — SAT

- Own `scripts/sat/`: construct the order encoding, including threshold boundaries, monotonicity, the all-different constraint, and edge-distance constraints.
- Decode a satisfying assignment into the shared vertex-to-position labeling. Explain why the encoding is equivalent to the decision problem.
- Implement repeated SAT and incremental SAT. Repeated SAT creates a new solver for each bound; incremental SAT keeps one solver and stable variable IDs while adding tighter restrictions.
- Use one pinned CaDiCaL backend through PySAT for both required SAT variants, so the comparison changes the solving scheme rather than the backend.
- Apply the shared bound policy and report contract in [ExperimentContract.md](docs/ExperimentContract.md). Never interpret interruption or timeout as UNSAT.
- Record the tested bounds and outcomes, variable and clause counts, construction time, and search time.
- Add workflow tests that exercise the real encoding, search, decoding, and shared checker on graphs with independently known optima, including disconnected and edgeless graphs.
- Optional extension: implement pairwise encoding with incremental SAT after both required order-encoding workflows pass. Adding repeated SAT for pairwise is a further optional comparison. Use the same input and output contract and mark extension results separately.

**Delivery:** runnable SAT workflows, passing relevant tests, reproducible run artifacts, and the SAT method/results report sections.

## Member 2 — CP and Shared Data Validation

- Own `scripts/cp/`: formulate integer positions, an all-different constraint, and the maximum edge-distance objective.
- Implement the CP model with OR-Tools CP-SAT and IBM CPLEX CP Optimizer adapters. Preserve the distinction between the model and the solver backend in the results.
- Own the shared loader and checker in `scripts/shared/`. The loader reads the committed graph files, checks input validity, and retains all vertices.
- Verify dataset checksums before experiments. Keep all algorithms on the same manifest and graph conversion.
- The checker independently verifies the position permutation and recomputes bandwidth from the original graph. It checks feasible outputs from every method, including SAT and ILP.
- Add workflow tests covering loading, solving, checking, and result export; include malformed inputs and rejection of invalid labelings.
- Verify backend installation and license availability before the main experiment campaign. Share unavailable backends and supporting evidence with the group.

**Delivery:** runnable CP workflows, one shared loader and checker, passing relevant tests, provenance verification, and the CP/dataset report sections.

## Member 3 — ILP and Integration

- Own `scripts/ilp/`: develop an ILP formulation with unique vertex positions and a bandwidth objective; explain the constraints and any linearization.
- Implement IBM CPLEX MIP and Gurobi adapters for the same formulation. Check availability and licensing before the main campaign.
- Add workflow tests that exercise the real ILP formulation, solve, extraction, and shared checker on independently known cases.
- Own the experiment runner in `tools/`. Apply the shared conditions, schedule methods sequentially, enforce deadlines, collect artifacts, and export comparable results.
- Record the environment, exact solver and dependency versions, Git revision, experiment configuration, and dataset checksums.
- Own integration into `main`. Review cross-method interface changes and check that the required comparison matrix is complete before accepting optional extensions.
- Assemble the paper, reconcile notation and comparisons, maintain references, and prepare the repository link for Data Availability.
- Coordinate member names, actual contributions, deadline planning, final review, and submission. No submission deadline is specified in this plan.

**Delivery:** runnable ILP workflows, passing relevant tests, a reproducible experiment runner, integrated result artifacts, and the assembled report.

## Shared Input, Output, and Conditions

[ExperimentContract.md](docs/ExperimentContract.md) is the canonical contract. All members implement the same input interpretation, labeling representation, status meanings, timing boundaries, and experiment configuration. No member maintains a separate loader or a replacement solution checker.

Implementations use Python 3.10 or newer. Each owner records the exact dependency versions after their backend smoke test; Member 3 freezes one compatible environment before the main campaign. Do not invent version pins before verifying that the selected backends run together.

Commercial backend access is not assumed. A missing license or unusable backend is a documented blocker for that comparison, not permission to omit the method or claim a result. Member 3 resolves access or obtains an explicit scope clarification.

## Integration Order

1. Member 2 implements the loader and checker. Meanwhile, Members 1 and 3 develop their models against the shared contract.
2. Each member integrates their backend and its workflow tests. Member 3 documents a real automated test entry point and change-based test selection before merging maintained tests.
3. All members run the correctness gate in the experiment contract. Member 3 then runs smoke experiments and freezes the environment and configuration.
4. Member 3 executes the main comparison campaign; each method owner investigates failures and reviews their own exported results.
5. Add optional methods as separately named variants after the required workflows work. Regenerate affected comparisons through the shared runner.
6. Each member writes their assigned report sections. All three review the final claims and contribution statement before submission.

## Report Ownership

| Report part | Primary owner | Required review |
|---|---|---|
| Problem definition and notation | Member 1 | Members 2 and 3 |
| Related work and dataset provenance | Member 2 | Members 1 and 3 |
| SAT encoding, both solving schemes, optional SAT extensions | Member 1 | Member 2 |
| CP formulation and backends | Member 2 | Member 3 |
| ILP formulation and backends | Member 3 | Member 1 |
| Experimental setup and reproducibility | Member 3 | Members 1 and 2 |
| Method-specific results | Each method owner | Member 3 checks consistency |
| Comparison tables and charts | Member 3 | All members check against raw records |
| Discussion and limitations | All members | Member 3 integrates |
| Introduction, abstract, conclusion, references, Data Availability | Member 3 | All members |

The report uses the Elsevier `cas-sc` class, as required by the assignment, and cnsplots for result charts. Write the abstract and conclusion after the results are checked. The contribution statement records work actually performed, not only this planned allocation. Cite the source paper, dataset, solver backends, and software versions. Describe actual AI assistance accurately if a disclosure is included or required.

## Completion Criteria

- Every required workflow produces valid results under the shared contract; backend access blockers are resolved or explicitly clarified before claiming the comparison complete.
- The maintained workflow tests execute a nonzero test count and pass through the documented entry point. Tests run against the same candidate files reviewed for integration.
- Every claimed feasible labeling passes the shared checker. Every optimality claim has the evidence required by the experiment contract.
- The experiment matrix, configurations, raw per-run results, logs, solution files, and environment records are available in the repository.
- The report distinguishes proven optima, unproved feasible solutions, timeouts, errors, and unavailable backends. No solver performance results are fabricated or inferred from the paper.
- The final paper links the source code and results in Data Availability. Member 3 resolves repository visibility or reviewer access before submission.
