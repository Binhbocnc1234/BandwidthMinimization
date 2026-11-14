"""Peak RSS of the SAT search child on one graph. Usage: peakRss.py GRAPH SCHEME LIMIT"""
import resource
import sys
import time

sys.path.insert(0, "script/sat")
from SATSolverWrapper import solveBMPSAT

if __name__ == "__main__":
    graph, scheme, limit = sys.argv[1], sys.argv[2], float(sys.argv[3])
    start = time.time()
    result = solveBMPSAT(f"data/HarwellBoeing/graphs/{graph}.col", "order", scheme, limit)
    childPeakMiB = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
    print(f"{graph} {scheme}: status={result['status']} reason={result['terminationReason']} bestUB={result['bestUB']} "
          f"time={result['totalTime']:.1f}s maxClauses={result['maxClauses']} childPeakRSS={childPeakMiB:.0f} MiB "
          f"bounds={[(t['ub'], t['isSat']) for t in result['trace']]}", flush=True)