"""Same bounds and answers as the code before the fix? ibm32, order encoding, a short limit because the old code can overrun without end."""
import sys
sys.path.insert(0, "script/sat")
from SATSolverWrapper import solveBMPSAT, parseFile, verifyLabeling

def main():
    path = "data/HarwellBoeing/graphs/ibm32.col"
    limit = float(sys.argv[2])
    n, edges = parseFile(path)
    new = {s: solveBMPSAT(path, "order", s, timeLimit=limit) for s in ("repeated", "incremental")}
    for name in ("incrementalSATSolver", "repeatedSATSolver", "orderEncoding", "pairwiseEncoding", "decoder"):
        sys.modules.pop(name, None)
    sys.path.insert(0, sys.argv[1])
    import repeatedSATSolver, incrementalSATSolver
    assert "old" in repeatedSATSolver.__file__
    initUB = verifyLabeling(n, edges, list(range(1, n + 1)))
    for s, cls in (("repeated", repeatedSATSolver.RepeatedSATSolver), ("incremental", incrementalSATSolver.IncrementalSATSolver)):
        old = cls(n, edges).solve(initUB, limit)
        a = [(t["ub"], t["isSat"]) for t in new[s]["trace"] if t["isSat"] is not None]
        b = [(t["ub"], t["isSat"]) for t in old["trace"]]
        k = min(len(a), len(b))
        print(f"{s}: answered bounds new {len(a)}, old {len(b)}, shared prefix of {k} equal: {a[:k] == b[:k]}; total new {new[s]['totalTime']:.3f}s, old {old['totalTime']:.3f}s; best new {new[s]['bestUB']}, old {old['bestUB']}", flush=True)
        print("  new sum solve", round(sum(t["solveTime"] for t in new[s]["trace"][:k]), 2), "old sum solve", round(sum(t["solveTime"] for t in old["trace"][:k]), 2), flush=True)

if __name__ == "__main__":
    main()
