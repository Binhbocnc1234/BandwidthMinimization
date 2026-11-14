"""How much time and memory does OrderEncoder.encode cost on the 1,000-vertex graph? Runs under a 6 GB address-space cap."""
import sys, time, resource
resource.setrlimit(resource.RLIMIT_AS, (6 << 30, 6 << 30))
sys.path.insert(0, "script/sat")
from SATSolverWrapper import parseFile
from orderEncoding import OrderEncoder
n, edges = parseFile("data/HarwellBoeing/graphs/sherman1.col")
print("expected all-different clauses", n * n * (n - 1) // 2, flush=True)
e = OrderEncoder(n, edges); t = time.monotonic()
class Counting(list):
    def append(self, c):
        list.append(self, c)
        if len(self) % 2000000 == 0:
            print(f"{len(self)} clauses, {time.monotonic()-t:.1f}s, peak RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024:.0f} MiB", flush=True)
import builtins
src_list = Counting
# Build a counting copy of the triple loop by replacing the literal list via the encoder's own code object is not possible, so sample the same loop body:
clauses = Counting(); varL = e.varL
try:
    for i in range(1, n + 1):
        for u in range(1, n + 1):
            for v in range(u + 1, n + 1):
                if i == 1: clauses.append([-varL(u, 1), -varL(v, 1)])
                else: clauses.append([-varL(u, i), -varL(v, i), varL(u, i - 1), varL(v, i - 1)])
except MemoryError:
    print("MemoryError at", len(clauses), f"{time.monotonic()-t:.1f}s")
