# Bandwidth Minimization Problem

Summary: The mathematical BMP target, the group's edgeless-graph convention, and SAT encoding background for implementation.

## Mathematical Target

Given a finite undirected graph $G=(V,E)$ with $n=|V|\ge 1$, choose a bijection

$$f:V\rightarrow\{1,2,\ldots,n\}.$$

For a labeling $f$, define

$$B(f)=\max_{\{u,v\}\in E}|f(u)-f(v)|,$$

and minimize $B(f)$ over all bijections. The position difference is between the endpoints of an edge.

The group adopts $B(f)=0$ when $E$ is empty. This is an explicit team convention for a case the supplied notes did not settle. The graph remains nonempty in vertices, so every vertex still receives a position.

For a decision bound $b$, SAT means a bijection exists with $|f(u)-f(v)|\le b$ for every edge. UNSAT means no such bijection exists. Timeout and interruption establish neither result.

## Order Encoding Background

The lecturer's supplied notes introduce $L(u,i)$ meaning $f(u)\le i$:

$$L(u,0)=\bot,\qquad L(u,n)=\top,$$

$$L(u,i)\implies L(u,i+1)\qquad(0\le i<n).$$

The first true threshold gives the vertex's position. Threshold monotonicity alone does not give different vertices different positions. Member 1 must choose and justify the all-different CNF construction.

For each edge $\{u,v\}$, the notes give

$$L(u,k)\implies L(v,k+b),\qquad L(v,k)\implies L(u,k+b).$$

Indices at or above $n$ represent the constant true boundary, not unconstrained new variables.

## Direct Position Encoding Background

The notes also define $X(u,k)$ meaning $f(u)=k$. These variables need exactly one position per vertex and exactly one vertex per position. The edge-distance restriction can be expressed as

$$X(u,k)\implies\bigvee_{j=\max(1,k-b)}^{\min(n,k+b)}X(v,j).$$

When relating direct and order variables, the intended relationship is

$$X(u,i)\iff L(u,i)\land\neg L(u,i-1).$$

The encoding notes describe the intended meanings, not a completed implementation or proof. Required and optional method scope is owned by [Task.md](../Task.md#goal-and-scope); the shared bound policy is owned by the [experiment contract](ExperimentContract.md#bounds-and-optimality).

## Reference

[Documented] The provided reference is J. Torres-Jimenez et al., *A dual representation simulated annealing algorithm for the bandwidth minimization problem on graphs*, Information Sciences 303 (2015), 33–49, DOI [10.1016/j.ins.2014.12.041](https://doi.org/10.1016/j.ins.2014.12.041). Its introduction defines BMP; Section 5 uses the Harwell–Boeing benchmark and reference [22] points to NIST Matrix Market. The paper's algorithm is simulated annealing.
