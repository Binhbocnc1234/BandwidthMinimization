# TODO: sua lai ham xu li timeout

import time
from pysat.solvers import Solver

from orderEncoding import OrderEncoder
from pairwiseEncoding import PairwiseEncoder

from decoder import decodeOrderEncoding, decodePairwiseEncoding

class IncrementalSATSolver:
    def __init__(   self, 
                    numVertices: int, 
                    edges: list[tuple[int, int]], 
                    encodingType: str = "order",
                    verbose: bool = False):

        """
        Khởi tạo thuật toán giải SAT theo PP Incremental SAT.

        numVertices: Số lượng đỉnh n
        edges: Danh sách cạnh (u, v)
        encodingType: "order" hoặc "pairwise"(default: "order")
        verbose: Hiện thị log quá trình giải (default: False)
        """

        self.numVertices = numVertices
        self.edges = edges
        self.encodingType = encodingType
        self.verbose = verbose

    def getActivationVar(self, ub: int) -> int:
        """
        Khởi tạo ID của biến phụ activation A_ub
        Trả về ID = n * n + UB.
        """

        return self.numVertices * self.numVertices + ub

    def solve(self, initUB: int, timeLimit: float = 300.0) -> dict:
        """
        Thực hiện Incremental SAT: 
        Giảm UB dần, từ initUb - 1 xuống cho đến khi unSAT.
        Duy trì 1 biến phụ activation A_k cho mỗi UB = k để kiểm tra tại UB này đã SAT chưa.

        initUB: UB khởi tạo
        timeLimit: Giới hạn thời gian giải (default: 300s)
        """

        # KHỞI TẠO THUẬT TOÁN
        startTime = time.time()

        bestLabeling = [i + 1 for i in range(self.numVertices)]
        bestUB = initUB
        lb = 1 if len(self.edges) > 0 else 0

        if self.encodingType == "order":
            encoder = OrderEncoder(self.numVertices, self.edges)
            baseClausesOnly, metadata = encoder.encode(ub=self.numVertices, includeEdgeConstraints=False)
        else:
            encoder = PairwiseEncoder(self.numVertices, self.edges)
            baseClausesOnly, metadata = encoder.encode(ub=self.numVertices, includeEdgeConstraints=False)

        trace = []
        maxVars = metadata["numVars"]
        maxClauses = len(baseClausesOnly)

        status = "OPTIMAL" if bestUB <= lb else "FEASIBLE"
        currUB = initUB - 1

        with Solver(name="cadical153", bootstrap_with=baseClausesOnly) as solver:
            while currUB >= lb:
                elapsedTime = time.time() - startTime
                remainingTime = timeLimit - elapsedTime

                if remainingTime <= 0: 
                    status = "FEASIBLE"
                    if self.verbose:
                        print(f"  [Timeout] Đã vượt quá giới hạn thời gian {timeLimit}s!", flush=True)
                    break

                activationLiteral = self.getActivationVar(currUB)
                maxVars = max(maxVars, activationLiteral)

                if self.encodingType == "order":
                    for u, v in self.edges:
                        for k in range(1, self.numVertices + 1):
                            pos = k + currUB

                            if pos < self.numVertices:
                                solver.add_clause([-encoder.varL(u, k), encoder.varL(v, pos), -activationLiteral])
                                solver.add_clause([-encoder.varL(v, k), encoder.varL(u, pos), -activationLiteral])
                
                else:
                    for u, v in self.edges:
                        for k in range(1, self.numVertices + 1):
                            minJ = max(1, k - currUB)
                            maxJ = min(self.numVertices, k + currUB)

                            validRangeV = [encoder.varX(v, j) for j in range(minJ, maxJ + 1)]
                            validRangeU = [encoder.varX(u, j) for j in range(minJ, maxJ + 1)]

                            solver.add_clause([-encoder.varX(u, k)] + validRangeV + [-activationLiteral])
                            solver.add_clause([-encoder.varX(v, k)] + validRangeU + [-activationLiteral])

                solverStart = time.time()
                isSat = solver.solve(assumptions=[activationLiteral])
                solverTime = time.time() - solverStart

                if solverTime >= remainingTime or (time.time() - startTime) >= timeLimit:
                    status = "FEASIBLE"
                    if self.verbose:
                        print(" ->[TIMEOUT]: CaDiCaL timeout tại UB = {currUB}", flush=True)
                    break

                if self.verbose:
                    resStr = "SAT" if isSat else "UNSAT"
                    print(f"  -> Testing UB = {currUB:>3} | Result: {resStr:>5} | Time: {solverTime:6.4f}s", flush=True)

                trace.append({
                    "ub"        : currUB,
                    "isSat"     : isSat,
                    "solveTime" : solverTime
                })

                if isSat:
                    model = solver.get_model()
                    if self.encodingType == "order":
                        bestLabeling = decodeOrderEncoding(model, self.numVertices)
                    else:
                        bestLabeling = decodePairwiseEncoding(model, self.numVertices)

                    bestUB = currUB
                    currUB -= 1

                else:
                    status = "OPTIMAL"
                    break

        totalTime = time.time() - startTime

        return {
            "status"        : status,
            "bestUB"        : bestUB,
            "labeling"      : bestLabeling,
            "totalTime"     : totalTime,
            "maxVars"       : maxVars,
            "maxClauses"    : maxClauses,
            "trace"         : trace
        }
