# TODO: 
# Reformat this file into a wrapper for main.py


import os
import sys
import time

from repeatedSATSolver import RepeatedSATSolver
from incrementalSATSolver import IncrementalSATSolver


def parseColFile(filePath: str) -> tuple[int, list[tuple[int, int]]]:
    n = 0
    m = 0
    edges = []

    if not os.path.exists(filePath):
        raise FileNotFoundError(f"File không tồn tại: {filePath}")

    with open(filePath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("c"):
                continue
            parts = line.split()
            if parts[0] == "p":
                n = int(parts[2])
                m = int(parts[3])
            elif parts[0] == "e":
                u = int(parts[1])
                v = int(parts[2])
                edges.append((u, v))

    return n, edges


def verifyLabeling(numVertices: int, edges: list[tuple[int, int]], labeling: list[int]) -> int:
    if sorted(labeling) != list(range(1, numVertices + 1)):
        raise ValueError("ERROR: labeling không phải là hoán vị hợp lệ từ 1..n!")

    if not edges:
        return 0

    maxBw = 0
    for u, v in edges:
        posU = labeling[u - 1]
        posV = labeling[v - 1]
        bw = abs(posU - posV)
        if bw > maxBw:
            maxBw = bw

    return maxBw


def runTempBenchmark(colFilePath: str, timeLimit: float = 300.0):
    print(f"\n==================================================", flush=True)
    print(f"LOADING GRAPH: {colFilePath}", flush=True)
    print(f"==================================================", flush=True)

    n, edges = parseColFile(colFilePath)
    print(f"Graph stats: Vertices (n) = {n}, Edges (m) = {len(edges)}", flush=True)

    identityLabeling = [i + 1 for i in range(n)]
    initUB = verifyLabeling(n, edges, identityLabeling)
    print(f"Initial Upper Bound (Identitydef runTempBenchmark(colFilePath: str, timeLimit: float = 2): Labeling): {initUB}\n", flush=True)

    methods = [
        ("Order / Repeated SAT", "order", "repeated"),
        ("Order / Incremental SAT", "order", "incremental"),
        ("Pairwise / Repeated SAT", "pairwise", "repeated"),
        ("Pairwise / Incremental SAT", "pairwise", "incremental"),
    ]

    for name, encodingType, solverType in methods:
        print(f"---> Running: {name}", flush=True)

        if solverType == "repeated":
            solver = RepeatedSATSolver(n, edges, encodingType=encodingType)
        else:
            solver = IncrementalSATSolver(n, edges, encodingType=encodingType)

        result = solver.solve(initUB=initUB, timeLimit=timeLimit)

        verifiedBw = verifyLabeling(n, edges, result["labeling"])

        print(f"  [SUMMARY] Status: {result['status']} | Proved UB: {result['bestUB']} | Verified BW: {verifiedBw} | Total Time: {result['totalTime']:.3f}s\n", flush=True)

        assert verifiedBw == result["bestUB"], f"Mismatch! Solver UB: {result['bestUB']} vs Verified: {verifiedBw}"


if __name__ == "__main__":
    sampleCol = "data/HarwellBoeing/graphs/bcspwr01.col"

    if os.path.exists(sampleCol):
        runTempBenchmark(sampleCol, timeLimit=10.0)
    else:
        print(f"Không tìm thấy file {sampleCol}. Hãy đảm bảo đã chạy 'python tools/prepare_dataset.py'.")