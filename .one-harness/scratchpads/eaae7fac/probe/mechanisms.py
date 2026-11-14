"""Compare ways to stop CaDiCaL (cadical153 via PySAT) on a real hard bound of ibm32, order encoding."""
import sys, time, threading
sys.path.insert(0, "script/sat")
from pysat.solvers import Solver
from SATSolverWrapper import parseFile
from orderEncoding import OrderEncoder

n, edges = parseFile("data/HarwellBoeing/graphs/ibm32.col")
UB = 9  # below the 12 reached in ~8 s, so hard
clauses, meta = OrderEncoder(n, edges).encode(UB)
print("n", n, "clauses", meta["numClauses"], flush=True)

# 1. interrupt() on the real class
s = Solver(name="cadical153", bootstrap_with=clauses)
try:
    s.interrupt(); print("interrupt(): returned")
except Exception as e:
    print("interrupt():", type(e).__name__, e, flush=True)

# 2. Does a Python thread run while solve_limited executes? (GIL held?)
ticks = []
stop = threading.Event()
def tick():
    while not stop.is_set():
        ticks.append(time.monotonic()); time.sleep(0.05)
s.conf_budget(30000)
t = threading.Thread(target=tick, daemon=True); t.start()
t0 = time.monotonic(); r = s.solve_limited(); dt = time.monotonic() - t0
stop.set(); t.join()
gaps = [b - a for a, b in zip(ticks, ticks[1:])]
print(f"thread during solve_limited(30000 conflicts): result={r} took {dt:.2f}s, ticks={len(ticks)}, largest gap {max(gaps or [0]):.2f}s", flush=True)
s.delete()

# 3. conflict-budget slices: time of one slice, per slice size, over ~12 s
for budget in (1000, 10000):
    s = Solver(name="cadical153", bootstrap_with=clauses)
    start = time.monotonic(); longest = 0; slices = 0; r = None
    while time.monotonic() - start < 12:
        s.conf_budget(budget)
        a = time.monotonic(); r = s.solve_limited(); longest = max(longest, time.monotonic() - a); slices += 1
        if r is not None: break
    print(f"conf_budget={budget}: slices={slices} longest slice={longest:.3f}s result={r} after {time.monotonic()-start:.1f}s", flush=True)
    s.delete()
