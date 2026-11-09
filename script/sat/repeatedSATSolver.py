import time
from pysat.solvers import Solver

from deadlineRunner import SearchReporter, runSearchWithDeadline
from orderEncoding import OrderEncoder
from pairwiseEncoding import PairwiseEncoder

from decoder import decodeOrderEncoding, decodePairwiseEncoding

class RepeatedSATSolver:
    def __init__(   self, 
                    numVertices: int, 
                    edges: list[tuple[int, int]], 
                    encodingType: str = "order",
                    verbose: bool = False):

        """
        Khởi tạo thuật toán giải SAT theo PP lặp lại.

        numVertices: Số lượng đỉnh n
        edges: Danh sách cạnh (u, v)
        encodingType: "order" hoặc "pairwise"(default: "order")
        verbose: Hiện thị log quá trình giải (default: False)
        """

        self.numVertices = numVertices
        self.edges = edges
        self.encodingType = encodingType
        self.verbose = verbose

    def solve(self, initUB: int, timeLimit: float = 300.0) -> dict:
        """
        Thực hiện Repeated SAT: 
        Giảm UB dần, từ initUb - 1 xuống cho đến khi unSAT.
        Khởi tạo lại 1 instance Solver mới cho mỗi giá trị UB mới.

        initUB: UB khởi tạo
        timeLimit: Giới hạn thời gian giải (default: 300s)
        """

        return runSearchWithDeadline(self.searchBounds, self.numVertices, len(self.edges), initUB, timeLimit, self.verbose)

    def searchBounds(self, initUB: int, lb: int, reporter: SearchReporter) -> None:
        """
        Test decreasing bounds, in the child process of deadlineRunner, which owns the deadline.

        reporter: Sends each bound's result to the parent as soon as it exists.
        """

        currUB = initUB - 1

        while currUB >= lb:
            reporter.boundStarted(currUB)

            if self.encodingType == "order":
                encoder = OrderEncoder(self.numVertices, self.edges)
            else:
                encoder = PairwiseEncoder(self.numVertices, self.edges)

            clauses, metadata = encoder.encode(currUB)
            reporter.modelSize(metadata["numVars"], metadata["numClauses"])

            with Solver(name="cadical153", bootstrap_with=clauses) as solver:
                solverStart = time.time()
                isSat = solver.solve()
                solverTime = time.time() - solverStart

                if isSat:
                    model = solver.get_model()
                else:
                    model = None

            # IN REAL-TIME NGAY KHI VỪA GIẢI XONG 1 UB
            if self.verbose:
                resStr = "SAT" if isSat else "UNSAT"
                print(f"  -> Testing UB = {currUB:>3} | Result: {resStr:>5} | Time: {solverTime:6.4f}s | Clauses: {metadata['numClauses']}", flush=True)


            traceEntry = {
                "ub": currUB,
                "isSat": isSat,
                "numClauses": metadata["numClauses"],
                "solveTime": solverTime
            }

            if isSat and model is not None:
                if self.encodingType == "order":
                    labeling = decodeOrderEncoding(model, self.numVertices)
                else:
                    labeling = decodePairwiseEncoding(model, self.numVertices)

                reporter.boundFinished(traceEntry, labeling)
                currUB -= 1

            else:
                reporter.boundFinished(traceEntry, None)
                break






        