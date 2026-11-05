import time
from pysat.solvers import Solver

from orderEncoding import OrderEncoder
from pairwiseEncoding import PairwiseEncoder

from decoder import decodeOrderEncoding, decodePairwiseEncoding

class RepeatedSATSolver:
    def __init__(   self, 
                    numVertices: int, 
                    edges: list[tuple[int, int]], 
                    encodingType: str = "order"):

        """
        Khởi tạo thuật toán giải SAT theo PP lặp lại.

        numVertices: Số lượng đỉnh n
        edges: Danh sách cạnh (u, v)
        encodingType: "order" hoặc "pairwise"(default: "order")
        """

        self.numVertices = numVertices
        self.edges = edges
        self.encodingType = encodingType

    def solve(self, initUB: int, timeLimit: float = 300.0) -> dict:
        """
        Thực hiện Repeated SAT: 
        Giảm UB dần, từ initUb - 1 xuống cho đến khi unSAT.
        Khởi tạo lại 1 instance Solver mới cho mỗi giá trị UB mới.

        initUB: UB khởi tạo
        timeLimit: Giới hạn thời gian giải (default: 300s)
        """

        # KHỞI TẠO THUẬT TOÁN
        startTime = time.time()

        bestLabeling = [i + 1 for i in range(self.numVertices)]
        bestUB = initUB
        lb = 1 if len(self.edges) > 0 else 0

        if bestUB <= lb: 
            status = "OPTIMAL"
        else: 
            status = "FEASIBLE"

        currUB = initUB - 1
        trace = []
        maxVars = 0
        maxClauses = 0

        while currUB >= lb:
            elapsedTime = time.time() - startTime
            if elapsedTime >= timeLimit: 
                status = "FEASIBLE"
                break

            if self.encodingType == "order":
                encoder = OrderEncoder(self.numVertices, self.edges)
            else:
                encoder = PairwiseEncoder(self.numVertices, self.edges)

            clauses, metadata = encoder.encode(currUB)
            maxVars = max(maxVars, metadata["numVars"])
            maxClauses = max(maxClauses, metadata["numClauses"])

            with Solver(name="cadical153", bootstrap_with=clauses) as solver:
                solverStart = time.time()
                isSat = solver.solve()
                solverTime = time.time() - solverStart

                if isSat:
                    model = solver.get_model()
                else:
                    model = None

            # IN REAL-TIME NGAY KHI VỪA GIẢI XONG 1 UB
            # resStr = "SAT" if isSat else "UNSAT"
            # print(f"  -> Testing UB = {currUB:>3} | Result: {resStr:>5} | Time: {solverTime:6.4f}s | Clauses: {metadata['numClauses']}", flush=True)


            trace.append({
                "ub": currUB,
                "isSat": isSat,
                "numClauses": metadata["numClauses"],
                "solveTime": solverTime
            })

            if isSat and model is not None:
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






        