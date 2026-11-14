"""Scratch verification of the SAT time limit. Run from the repository root."""
import itertools, json, os, sys, tempfile, time
sys.path.insert(0, "script/sat")
from SATSolverWrapper import solveBMPSAT, verifyLabeling, parseFile
from deadlineRunner import runSearchWithDeadline

failures = []
def check(cond, msg):
    print(("  ok  " if cond else "  FAIL ") + msg, flush=True)
    if not cond: failures.append(msg)

def brute(n, edges):
    best = None
    for p in itertools.permutations(range(1, n + 1)):
        b = max((abs(p[u-1]-p[v-1]) for u, v in edges), default=0)
        if best is None or b < best: best = b
    return best

def writeGraph(d, name, n, edges):
    path = os.path.join(d, name + ".col")
    with open(path, "w") as f:
        f.write(f"p edge {n} {len(edges)}\n")
        for u, v in edges: f.write(f"e {u} {v}\n")
    return path

def timeouts():
    print("== timeouts (order encoding)", flush=True)
    for graph, limit in (("ibm32", 3.0), ("ibm32", 10.0), ("curtis54", 5.0), ("bcsstk20", 4.0), ("sherman1", 4.0)):
        path = f"data/HarwellBoeing/graphs/{graph}.col"
        n, edges = parseFile(path)
        for scheme in ("repeated", "incremental"):
            wall = time.monotonic()
            r = solveBMPSAT(path, "order", scheme, timeLimit=limit)
            wall = time.monotonic() - wall
            vb = verifyLabeling(n, edges, r["labeling"])
            last = r["trace"][-1] if r["trace"] else None
            print(f"  {graph} {scheme} limit={limit}: totalTime={r['totalTime']:.3f}s overshoot={r['deadlineOvershootSeconds']*1000:.1f}ms wall={wall:.3f}s status={r['status']} reason={r['terminationReason']} bestUB={r['bestUB']} verified={vb} bounds={len(r['trace'])} last={last}", flush=True)
            check(r["terminationReason"] == "time_limit", "reached time limit")
            check(r["status"] == "FEASIBLE", "not OPTIMAL")
            check(vb == r["bestUB"], "labeling verified")
            check(r["deadlineOvershootSeconds"] < 1.0, "overshoot under 1 s")
            check(last is not None and last["isSat"] is None, "interrupted bound is unknown, not UNSAT")

def oracle():
    print("== brute-force oracle", flush=True)
    import random
    rng = random.Random(7)
    graphs = {
        "path6": (6, [(i, i+1) for i in range(1, 6)]),
        "cycle7": (7, [(i, i+1) for i in range(1, 7)] + [(1, 7)]),
        "complete6": (6, list(itertools.combinations(range(1, 7), 2))),
        "star7": (7, [(1, i) for i in range(2, 8)]),
        "disconnected8": (8, [(1, 2), (2, 3), (1, 3), (5, 8), (6, 8), (7, 8)]),
        "edgeless5": (5, []),
        "single": (1, []),
        "wheel8": (8, [(1, i) for i in range(2, 9)] + [(i, i+1) for i in range(2, 8)] + [(2, 8)]),
    }
    for k in range(6):
        n = rng.randint(4, 8)
        pairs = list(itertools.combinations(range(1, n + 1), 2))
        graphs[f"random{k}_n{n}"] = (n, sorted(rng.sample(pairs, rng.randint(1, len(pairs)))))
    runs = 0
    with tempfile.TemporaryDirectory(dir=os.environ["AGENT_SCRATCHPAD"]) as d:
        for name, (n, edges) in graphs.items():
            path = writeGraph(d, name, n, edges)
            want = brute(n, edges)
            for enc, scheme in itertools.product(("order", "pairwise"), ("repeated", "incremental")):
                r = solveBMPSAT(path, enc, scheme, timeLimit=60.0)
                runs += 1
                ok = r["bestUB"] == want and r["verifiedBW"] == want and r["terminationReason"] == "completed" and r["deadlineOvershootSeconds"] == 0.0
                if not ok: check(False, f"{name} {enc} {scheme}: got {r['bestUB']} want {want} {r['terminationReason']}")
            print(f"  {name}: oracle bandwidth {want} matched by 4 methods", flush=True)
    check(runs == 56, f"oracle runs executed: {runs}")

def failSearch(initUB, lb, reporter):
    raise ValueError("planted failure in search")

def crashSearch(initUB, lb, reporter):
    reporter.boundStarted(7)
    os._exit(5)

def slowSearch(initUB, lb, reporter):
    reporter.boundStarted(initUB - 1)
    time.sleep(0.5)
    reporter.boundFinished({"ub": initUB - 1, "isSat": True, "solveTime": 0.5}, list(range(1, 11)))
    reporter.boundStarted(initUB - 2)
    time.sleep(30)

def errors():
    print("== failure paths", flush=True)
    for f, text in ((failSearch, "planted failure"), (crashSearch, "exit code 5")):
        try:
            runSearchWithDeadline(f, 10, 5, 9, 5.0, False)
            check(False, f"{f.__name__} should raise")
        except RuntimeError as e:
            check(text in str(e), f"{f.__name__}: {str(e).splitlines()[-1][:110]}")
    r = runSearchWithDeadline(slowSearch, 10, 5, 9, 1.0, False)
    check(r["bestUB"] == 8 and r["status"] == "FEASIBLE" and r["trace"][-1]["isSat"] is None and r["totalTime"] < 1.5, f"incumbent survives a kill: {r['bestUB']} in {r['totalTime']:.3f}s; child killed")

def overhead():
    print("== process startup", flush=True)
    with tempfile.TemporaryDirectory(dir=os.environ["AGENT_SCRATCHPAD"]) as d:
        path = writeGraph(d, "c5", 5, [(1,2),(2,3),(3,4),(4,5),(1,5)])
        for i in range(3):
            w = time.monotonic(); r = solveBMPSAT(path, "order", "incremental", timeLimit=30); w = time.monotonic() - w
            print(f"  wall {w:.3f}s, of which budgeted totalTime {r['totalTime']:.3f}s, status {r['status']}", flush=True)

if __name__ == "__main__":
    {"timeouts": timeouts, "oracle": oracle, "errors": errors, "overhead": overhead}[sys.argv[1]]()
    print("FAILURES:", failures, flush=True)
    sys.exit(1 if failures else 0)
