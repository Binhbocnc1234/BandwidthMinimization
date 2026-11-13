# ILP Model

Summary: The ILP formulation that `ilp_cplex` and `ilp_gurobi` share, why its optimum equals the BMP optimum, and how a backend bound becomes an optimality claim.

The code is `buildBandwidthModel` in [ilpModel.py](../scripts/ilp/ilpModel.py); both backends call it, so they solve one model. The target is defined in [Problem.md](Problem.md#mathematical-target).

## Formulation

For vertices and positions $v, k \in \{1, \ldots, n\}$, with $LB$ the common lower bound and $UB_0$ the identity bandwidth from the [experiment contract](ExperimentContract.md#bounds-and-optimality):

$$\min B$$

$$\sum_{k=1}^{n} x_{vk} = 1 \quad \forall v, \qquad \sum_{v=1}^{n} x_{vk} = 1 \quad \forall k$$

$$p_v = \sum_{k=1}^{n} k\,x_{vk} \quad \forall v$$

$$p_u - p_v \le B, \qquad p_v - p_u \le B \quad \forall \{u, v\} \in E$$

$$x_{vk} \in \{0, 1\}, \qquad 1 \le p_v \le n, \qquad B \in \mathbb{Z},\ LB \le B \le UB_0$$

Size: $n^2 + n + 1$ variables and $3n + 2m$ constraints. The position variables $p_v$ keep each edge row at 3 nonzeros; substituting their sums into the edge rows would put $2n$ nonzeros in each of the $2m$ edge rows.

## Why the Optimum Is the BMP Optimum

- The two assignment rows make $x$ a permutation matrix, so $f(v) = p_v$ is a bijection onto $\{1, \ldots, n\}$. Every bijection gives such a matrix, so the feasible $x$ are exactly the labelings.
- The two edge rows are $B \ge |p_u - p_v|$. For a fixed labeling, the smallest feasible $B$ is the largest edge difference, $B(f)$; on an edgeless graph it is $\max(LB, 0) = 0$, the team convention.
- $B(f)$ is an integer, so declaring $B$ integer removes no labeling. $LB \le B(f^*) \le UB_0$ holds for an optimal labeling $f^*$, because the identity labeling is feasible with bandwidth $UB_0$ and the contract's $LB$ is valid. So the bounds on $B$ remove no optimal labeling, and the model's optimum equals $\min_f B(f)$.

`p` is continuous, because it equals an integer sum whenever $x$ is integral. A backend's $x$ is integral only within its integrality tolerance, so the code rounds each $p_v$ and passes the result to the shared checker; a rounded vector that is not a permutation fails the run with `ERROR`.

## From a Backend Bound to `OPTIMAL`

Both backends run with relative and absolute MIP gap 0, one thread, the run's seed, and the remaining time budget. The identity labeling is the MIP start.

The native best bound is rounded to $\lceil bound - 10^{-5} \rceil$, where $10^{-5}$ is the default integrality tolerance of both backends (`INTEGRALITY_TOLERANCE` in [ilpSolver.py](../scripts/ilp/ilpSolver.py)). A run is `OPTIMAL` when that bound equals the checked incumbent bandwidth. A native optimal status whose rounded bound does not equal the incumbent is a run error, not an optimum.

## Limits

The free CPLEX Community Edition refuses models above 1,000 variables or 1,000 constraints. This model exceeds that from $n = 32$ ($32^2 + 32 + 1 = 1{,}057$ variables), so `ilp_cplex` needs the full CPLEX for every committed instance.

The LP relaxation of this formulation is weak: setting every $x_{vk} = 1/n$ puts every $p_v$ at $(n+1)/2$ and satisfies the edge rows with $B = 0$. Proofs of optimality therefore rely on branching, and a time-limited run often ends `FEASIBLE`. A stronger formulation is an allowed extension variant under the contract, not a replacement of this one.