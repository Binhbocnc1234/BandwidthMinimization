"""Does cutting one CaDiCaL solve into conflict-budget slices change the search? Same formula, same bound."""
import sys, time
sys.path.insert(0, "script/sat")
from pysat.solvers import Solver
from SATSolverWrapper import parseFile
from orderEncoding import OrderEncoder
n, edges = parseFile("data/HarwellBoeing/graphs/ibm32.col")
for UB in (14, 12):
    clauses, _ = OrderEncoder(n, edges).encode(UB)
    with Solver(name="cadical153", bootstrap_with=clauses) as s:
        a = time.monotonic(); r = s.solve(); print(f"UB={UB} plain solve: {r} {time.monotonic()-a:.2f}s", flush=True)
    for budget in (1000, 10000):
        with Solver(name="cadical153", bootstrap_with=clauses) as s:
            a = time.monotonic(); r = None; k = 0
            while r is None and time.monotonic() - a < 25:
                s.conf_budget(budget); r = s.solve_limited(); k += 1
            print(f"UB={UB} slices {budget}: {r} {time.monotonic()-a:.2f}s in {k} slices", flush=True)
