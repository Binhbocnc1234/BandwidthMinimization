import math
import time
from importlib.metadata import version


class CPSolver:
    """Giải Bandwidth Minimization bằng mô hình CP và một trong hai backend."""

    def __init__(
        self,
        numVertices: int,
        edges: list[tuple[int, int]],
        backend: str = "ortools",
        verifyLabeling=None,
    ):
        """Khởi tạo dữ liệu chung cho OR-Tools và IBM CP Optimizer.

        numVertices: Số đỉnh n >= 1.
        edges: Các cạnh (u, v), yêu cầu 1 <= u < v <= n và không trùng.
        backend: "ortools" hoặc "cpo" (default: "ortools").
        verifyLabeling: Hàm checker của nhóm, trả bandwidth sau khi kiểm tra hoán vị.

        Quy ước: labeling[u - 1] là vị trí của đỉnh u, không phải thứ tự duyệt đỉnh.
        """
        # KIỂM TRA ĐẦU VÀO
        if backend not in {"ortools", "cpo"}:
            raise ValueError("backend must be ortools or cpo")
        if verifyLabeling is None:
            raise ValueError("Supply the team's verifyLabeling function")
        if type(numVertices) is not int or numVertices < 1:
            raise ValueError("numVertices must be a positive integer")
        if any(
            type(u) is not int or type(v) is not int or not 1 <= u < v <= numVertices
            for u, v in edges
        ):
            raise ValueError("Expected 1 <= u < v <= numVertices")
        if len(set(edges)) != len(edges):
            raise ValueError("Duplicate edges")
        # LƯU DỮ LIỆU
        self.numVertices = numVertices
        self.edges = sorted(edges)
        self.backend = backend
        self.verifyLabeling = verifyLabeling

    def buildModel(self, initUB: int):
        """Dựng mô hình CP cho bài toán Bandwidth Minimization.

        position[u - 1] là vị trí của đỉnh u. initUB là bandwidth của identity.
        Trả về model cùng các biến cần để trích nghiệm sau khi giải.
        """
        numVertices, edges = self.numVertices, self.edges

        # CHỌN API BACKEND: công thức toán học bên dưới được dùng chung.
        if self.backend == "ortools":
            from ortools.sat.python import cp_model

            model = cp_model.CpModel()

            def newIntVar(lowerBound, upperBound, name):
                return model.new_int_var(lowerBound, upperBound, name)

        else:
            from docplex.cp.model import CpoModel
            from docplex.cp.solution import CpoModelSolution

            model = CpoModel()

            def newIntVar(lowerBound, upperBound, name):
                return model.integer_var(lowerBound, upperBound, name=name)

        # BIẾN: vị trí từng đỉnh, khoảng cách từng cạnh và bandwidth.
        position = [
            newIntVar(1, numVertices, f"position_{u}")
            for u in range(1, numVertices + 1)
        ]
        bandwidth = newIntVar(0, initUB, "bandwidth")
        edgeDistance = [
            newIntVar(0, numVertices - 1, f"distance_{u}_{v}")
            for u, v in edges
        ]

        # Mỗi đỉnh nhận một vị trí riêng; n vị trí trong miền 1..n tạo thành hoán vị.
        if self.backend == "ortools":
            model.add_all_different(position)
            for (u, v), distance in zip(edges, edgeDistance):
                model.add_abs_equality(distance, position[u - 1] - position[v - 1])
            if edges:
                model.add_max_equality(bandwidth, edgeDistance)
            else:
                model.add(bandwidth == 0)
            model.minimize(bandwidth)

            # Hint là gợi ý khởi tạo identity, không ép solver giữ cách xếp này.
            for u, variable in enumerate(position, 1):
                model.add_hint(variable, u)
            model.add_hint(bandwidth, initUB)
            for (u, v), variable in zip(edges, edgeDistance):
                model.add_hint(variable, v - u)
        else:
            model.add(model.all_diff(position))
            for (u, v), distance in zip(edges, edgeDistance):
                model.add(distance == model.abs(position[u - 1] - position[v - 1]))
            model.add(bandwidth == model.max(edgeDistance) if edges else bandwidth == 0)
            model.add(model.minimize(bandwidth))

            # IBM CP Optimizer nhận nghiệm khởi tạo qua starting point.
            startingPoint = CpoModelSolution()
            for u, variable in enumerate(position, 1):
                startingPoint.add_integer_var_solution(variable, u)
            startingPoint.add_integer_var_solution(bandwidth, initUB)
            for (u, v), variable in zip(edges, edgeDistance):
                startingPoint.add_integer_var_solution(variable, v - u)
            model.set_starting_point(startingPoint)

        return model, position, bandwidth

    def solve(self, initUB: int, timeLimit: float = 300.0, seed: int = 0,
              onIncumbent=None, logFile=None, executable=None) -> dict:
        """Giải mô hình và kiểm tra nghiệm bằng checker chung.

        initUB: Bandwidth của identity; timeLimit: ngân sách tính bằng giây.
        seed: Seed backend; onIncumbent: callback(labeling, bestUB, origin).
        logFile: Nơi lưu log; executable: đường dẫn CP Optimizer cho backend cpo.
        Trả về dict giữ nguyên schema CP để runner Member 3 sử dụng.
        OPTIMAL chỉ khi backend chứng minh tối ưu và cận bằng bestUB.
        """
        # KIỂM TRA THAM SỐ VÀ CẬN BAN ĐẦU
        if not math.isfinite(timeLimit) or timeLimit < 0:
            raise ValueError("timeLimit must be finite and >= 0")
        if type(seed) is not int or not 0 <= seed <= 2**31 - 1:
            raise ValueError("seed must be an integer in 0..2^31-1")
        identityLabeling = list(range(1, self.numVertices + 1))
        actualUB = self.verifyLabeling(self.numVertices, self.edges, identityLabeling)
        if type(initUB) is not int or initUB != actualUB:
            raise ValueError("initUB must equal the checked bandwidth of identityLabeling")
        # NẠP BACKEND TRƯỚC KHI BẮT ĐẦU ĐO THỜI GIAN
        if self.backend == "ortools":
            from ortools.sat.python import cp_model

            backendVersion = version("ortools")
        else:
            from docplex.cp.solver.cpo_callback import CpoCallback

            # Import trước timer để không tính thời gian import vào benchmark.
            from docplex.cp.model import CpoModel
            from docplex.cp.solution import CpoModelSolution

            backendVersion = None

        # KHỞI TẠO NGHIỆM: hết giờ vẫn còn identity hợp lệ.
        bestLabeling, bestUB = identityLabeling, initUB
        lowerBound = 1 if self.edges else 0
        incumbentOrigin, nativeStatus = "identity", "NOT_STARTED"
        terminationReason, status = "time_limit", "FEASIBLE"
        trace = []
        if onIncumbent:
            onIncumbent(bestLabeling.copy(), bestUB, "identity")
        startTime = time.perf_counter()

        def remember(labeling, objective):
            """Giữ nghiệm tốt hơn và báo cho runner lưu ngay ra đĩa.
            Chỉ ghi trace khi bandwidth giảm; nghiệm bằng incumbent không thay thế nó.
            """
            nonlocal bestLabeling, bestUB, incumbentOrigin
            if objective < bestUB:
                bestLabeling, bestUB, incumbentOrigin = list(labeling), int(objective), "solver"
                trace.append({"elapsedTime": time.perf_counter() - startTime, "bestUB": bestUB})
                if onIncumbent:
                    onIncumbent(bestLabeling.copy(), bestUB, "solver")

        # DỰNG MÔ HÌNH VÀ TÍNH NGÂN SÁCH CÒN LẠI
        model, position, bandwidth = self.buildModel(initUB)
        constructionTime = time.perf_counter() - startTime
        # Không cấp lại toàn bộ timeLimit sau khi đã dựng mô hình.
        remainingTime = timeLimit - constructionTime
        hintSubmitted, hintAccepted = True, None
        # GIẢI BÀI TOÁN
        if remainingTime > 0:
            if self.backend == "ortools":
                # OR-TOOLS: cấu hình thời gian, một worker và seed.
                solver = cp_model.CpSolver()
                solver.parameters.max_time_in_seconds = remainingTime
                solver.parameters.num_search_workers = 1
                solver.parameters.random_seed = seed
                solver.parameters.absolute_gap_limit = 0
                solver.parameters.relative_gap_limit = 0
                logStream = open(logFile, "w", encoding="utf-8") if logFile else None
                if logStream:
                    solver.parameters.log_search_progress = True
                    solver.parameters.log_to_stdout = False
                    solver.log_callback = lambda message: (
                        logStream.write(message + "\n"),
                        logStream.flush(),
                    )

                # Callback lấy vị trí nguyên mỗi khi backend tìm được nghiệm.
                class IncumbentCallback(cp_model.CpSolverSolutionCallback):
                    def on_solution_callback(self):
                        remember([self.value(p) for p in position], self.value(bandwidth))

                try:
                    nativeCode = solver.solve(model, IncumbentCallback())
                finally:
                    if logStream:
                        logStream.close()
                nativeStatus = solver.status_name(nativeCode)
                if nativeCode in (cp_model.MODEL_INVALID, cp_model.INFEASIBLE):
                    raise RuntimeError("Unexpected BMP status: " + nativeStatus)
                if nativeCode in (cp_model.FEASIBLE, cp_model.OPTIMAL):
                    remember([solver.value(p) for p in position], solver.value(bandwidth))
                    lowerBound = max(lowerBound, solver.best_objective_bound)
                # Có nghiệm chưa đủ: cần trạng thái tối ưu VÀ cận khớp.
                if nativeCode == cp_model.OPTIMAL:
                    if solver.best_objective_bound != bestUB:
                        raise RuntimeError("Native optimal status does not match certified bound")
                    status, terminationReason = "OPTIMAL", "completed"
            else:
                # IBM: xử lý sự kiện Solution bằng cùng hàm remember().
                class IncumbentCallback(CpoCallback):
                    def invoke(self, solver, event, sres):
                        if event == "Solution" and sres.is_solution():
                            remember(
                                [sres.get_value(p) for p in position], sres.get_value(bandwidth)
                            )

                model.add_solver_callback(IncumbentCallback())
                settings = dict(
                    TimeLimit=remainingTime,
                    Workers=1,
                    RandomSeed=seed,
                    OptimalityTolerance=0,
                    RelativeOptimalityTolerance=0,
                    LogVerbosity="Normal" if logFile else "Quiet",
                )
                if executable:
                    settings["execfile"] = executable
                logStream = open(logFile, "w", encoding="utf-8") if logFile else None
                if logStream:
                    settings["log_output"] = logStream
                try:
                    nativeResult = model.solve(**settings)
                finally:
                    if logStream:
                        logStream.close()
                nativeStatus = str(nativeResult.get_solve_status())
                backendVersion = nativeResult.get_solver_infos().get("SolverVersion")
                stopCause = str(nativeResult.get_stop_cause())
                terminationReason = "time_limit" if "TimeLimit" in stopCause else stopCause
                if nativeStatus in {"Infeasible", "Error"}:
                    raise RuntimeError("Unexpected BMP status: " + nativeStatus)
                if nativeResult.is_solution():
                    remember(
                        [nativeResult.get_value(p) for p in position],
                        nativeResult.get_value(bandwidth),
                    )
                    bounds = nativeResult.get_objective_bounds()
                    if bounds and math.isfinite(bounds[0]):
                        lowerBound = max(lowerBound, bounds[0])
                # Dùng cùng tiêu chuẩn chứng nhận tối ưu như OR-Tools.
                if nativeStatus == "Optimal":
                    if lowerBound != bestUB:
                        raise RuntimeError("Native optimal status does not match certified bound")
                    status, terminationReason = "OPTIMAL", "completed"
        totalTime = time.perf_counter() - startTime

        # KIỂM TRA NGHIỆM CUỐI: tính lại bandwidth, ngoài ngân sách giải.
        validationStart = time.perf_counter()
        verifiedBw = self.verifyLabeling(self.numVertices, self.edges, bestLabeling)
        if verifiedBw != bestUB or lowerBound > bestUB:
            raise ValueError("CP output failed independent checking")
        validationTime = time.perf_counter() - validationStart

        # TRẢ KẾT QUẢ CHO RUNNER
        # Số biến/ràng buộc ở mô hình nguồn, chưa tính biến đổi của backend.
        return {
            "status": status,
            "bestUB": bestUB,
            "labeling": bestLabeling,
            "totalTime": totalTime,
            "constructionTime": constructionTime,
            "searchTime": totalTime - constructionTime,
            "validationTime": validationTime,
            "lowerBound": lowerBound,
            "initUB": initUB,
            "trace": trace,
            "method": "cp_ortools" if self.backend == "ortools" else "cp_cpo",
            "model": "cp_positions_all_different_max_distance",
            "backend": "OR-Tools CP-SAT" if self.backend == "ortools" else "IBM CP Optimizer",
            "backendVersion": backendVersion,
            "nativeStatus": nativeStatus,
            "terminationReason": terminationReason,
            "incumbentOrigin": incumbentOrigin,
            "hintSubmitted": hintSubmitted,
            "hintAccepted": hintAccepted,
            "numVars": self.numVertices + 1 + len(self.edges),
            "maxVars": self.numVertices + 1 + len(self.edges),
            "numConstraints": len(self.edges) + 2,
            "modelCountScope": "source model, before backend presolve; objective excluded",
            "maxClauses": None,
            "threads": 1,
            "seed": seed,
            "deadlineOvershoot": max(0, totalTime - timeLimit),
        }
