## Check (done): before the main SAT campaign, decide how to run the graphs whose order encoding does not fit in RAM

Done on 2026-11-11: the developer chose to skip sherman1 and bcsstk20, and bcspwr05 is skipped too, because a measurement on bcspwr04 puts it at about 23 GiB. The reason is recorded in docs/ExperimentContract.md, section "Experiment Conditions" (commit 760978f).

The SAT time limit now holds during clause construction, but memory runs out first on the largest graphs. Measured on 2026-11-09 with the all-different loop of `OrderEncoder.encode` on sherman1: about 222 MiB per million clauses, and about 1.2 million clauses per second. The clause count is n * n*(n-1)/2.

| Graph | Vertices | All-different clauses | Estimated Python memory (clause list alone) |
|---|---|---|---|
| sherman1 | 1,000 | 500 million | about 108 GiB |
| bcsstk20 | 485 | 57 million | about 12 GiB |
| bcspwr05 | 443 | 43 million | about 9.5 GiB |

This laptop has 15 GiB of RAM, with about 9 GiB free when measured, so at that rate sherman1 fills the free RAM in about 35 seconds of a 300-second budget. A run that the OS kills for memory now raises an error that names the exit code, and it is not reported as a timeout. The OS may also slow down or kill other programs first, so do not start these three graphs on order encoding with the full 300 seconds until this is settled. When to do it: before the frozen campaign in docs/ExperimentContract.md.

## Question 1 (done): should CP and ILP also skip bcspwr05, bcsstk20 and sherman1?

Answer (developer, 2026-11-11): Keep them for CP and ILP, as recommended. Recorded in docs/ExperimentContract.md, section "Correctness and Analysis Gate": totals per method cover the 9 instances every method runs, and the 3 instances SAT skips are reported separately.

On 2026-11-11 these three graphs were removed from the SAT runs only, because the SAT order encoding needs about 23–270 GiB of RAM on them. CP and ILP still run all 12 graphs, as docs/ExperimentContract.md now says. The comparison then has 9 graphs where every method ran and 3 graphs with no SAT row, so the count of proved optima per method is taken over different graph sets.

- **Keep them for CP and ILP:** the report shows how CP and ILP handle the largest graphs, and the SAT rows say "skipped, out of memory" there. Cost: per-method totals must be reported over 9 common graphs and 3 extra ones separately.
- **Skip them for every method:** all methods share one 9-graph set. Cost: the report has no graph above 300 vertices, and CP and ILP lose the instances where they may beat SAT most clearly.

**Recommended option:** Keep them for CP and ILP, because SAT failing on memory where CP and ILP still produce results is itself a finding of the comparison. Teammates Cao Thế Mạnh (CP) and Trần Tuấn Cường (SAT) share this decision.

## Check (open): measure bcspwr04 on SAT for the full 300 seconds before the campaign

On 2026-11-11, bcspwr04 (274 vertices) reached 5.4–5.7 GiB in its SAT search process within 60 seconds, and incremental solving was stopped by a 6 GiB memory cap with std::bad_alloc. Incremental solving keeps adding clauses for each bound, so its memory may keep growing over 300 seconds, while the laptop had about 8 GiB available. When to do it: before the frozen campaign. Run it with a memory cap (for example `prlimit --as=...`) so a crash cannot make the OS kill other programs; if it crashes, bcspwr04 joins the SAT skip list in docs/ExperimentContract.md.