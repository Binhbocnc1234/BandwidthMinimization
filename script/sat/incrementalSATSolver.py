import time
from pysat.solvers import Solver

from deadlineRunner import SearchReporter, runSearchWithDeadline
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

        return runSearchWithDeadline(self.searchBounds, self.numVertices, len(self.edges), initUB, timeLimit, self.verbose)

    def searchBounds(self, initUB: int, lb: int, reporter: SearchReporter) -> None:
        """
        Test decreasing bounds on one solver, in the child process of deadlineRunner, which owns the deadline.

        reporter: Sends each bound's result to the parent as soon as it exists.
        """

        # An interruption while the base model is built is recorded against the first bound.
        reporter.boundStarted(initUB - 1)

        if self.encodingType == "order":
            encoder = OrderEncoder(self.numVertices, self.edges)
            baseClausesOnly, metadata = encoder.encode(ub=self.numVertices, includeEdgeConstraints=False)
        else:
            encoder = PairwiseEncoder(self.numVertices, self.edges)
            baseClausesOnly, metadata = encoder.encode(ub=self.numVertices, includeEdgeConstraints=False)

        reporter.modelSize(metadata["numVars"], len(baseClausesOnly))

        currUB = initUB - 1

        with Solver(name="cadical153", bootstrap_with=baseClausesOnly) as solver:
            while currUB >= lb:
                reporter.boundStarted(currUB)

                activationLiteral = self.getActivationVar(currUB)
                reporter.modelSize(activationLiteral, 0)

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

                if self.verbose:
                    resStr = "SAT" if isSat else "UNSAT"
                    print(f"  -> Testing UB = {currUB:>3} | Result: {resStr:>5} | Time: {solverTime:6.4f}s", flush=True)

                traceEntry = {
                    "ub"        : currUB,
                    "isSat"     : isSat,
                    "solveTime" : solverTime
                }

                if isSat:
                    model = solver.get_model()
                    if self.encodingType == "order":
                        labeling = decodeOrderEncoding(model, self.numVertices)
                    else:
                        labeling = decodePairwiseEncoding(model, self.numVertices)

                    reporter.boundFinished(traceEntry, labeling)
                    currUB -= 1

                else:
                    reporter.boundFinished(traceEntry, None)
                    break
