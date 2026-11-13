import os
import sys
import time

from repeatedSATSolver import RepeatedSATSolver
from incrementalSATSolver import IncrementalSATSolver

def parseFile(filePath: str) -> tuple[int, list[tuple[int, int]]]:
    """
    Đọc file .col trong dữ liệu.
    Trả về: (n, [danh sách cạnh])
    """

    n = 0
    m = 0
    edges = []

    if not os.path.exists(filePath):
        raise FileNotFoundError(f" -> [ERROR] File không tồn tại: {filePath}")

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

    if len(edges) != m:
        print(f" -> [Warning] Số lượng cạnh đọc được ({len(edges)}) khác với m trong file ({m}).")

    return n, edges

def verifyLabeling(numVertices: int, edges: list[tuple[int, int]], labeling: list[int]) -> int:
    """
    Kiểm tra tính độc lập của các label:
    Labeling có phải là hoán vị hợp lệ của dãy (1..n) ?
    
    Ngoài ra, hỗ trợ tính lại bandwidth: B(f) = max|f(u) - f(v)|.

    numVertices: Số lượng đỉnh đầu vào
    edges: Danh sách các cạnh của đồ thị
    labeling: Danh sách thứ tự đỉnh duyệt.

    Trả về:
    - ValueError nếu label bị sai.
    - maxBandwidth của labeling.
    """

    if sorted(labeling) != list(range(1, numVertices + 1)):
        raise ValueError(" ->[ERROR]: Labeling không hợp lệ.")

    if not edges: return 0

    maxBandwidth = 0
    for u, v in edges:
        posU = labeling[u - 1]
        posV = labeling[v - 1]

        bandwidth = abs(posU - posV)
        if bandwidth > maxBandwidth: maxBandwidth = bandwidth

    return maxBandwidth

def solveBMPSAT(
    filePath: str = None,
    encodingType: str = "order",
    solverType: str = "incremental",
    timeLimit: float = 300.0,
    verbose: bool = False
) -> dict:

    """
    Wrapper cho việc giải bài toán theo PP SAT.
    
    filePath: Đường dẫn đến file .col.
    encodingType: "order" hoặc "pairwise" (default: "order").
    solverType: "incremental" hoặc "repeated" (default: "incremental").
    timeLimit: (default: 300.0s). Covers model construction and every bound; a child process is killed at the deadline.
    verbose: In thông tin log ra console (default: False).

    The calling program needs an `if __name__ == "__main__":` guard. See deadlineRunner.runSearchWithDeadline.
        
    Trả về Dictionary chuẩn:
        {
            "instance": str,           # Tên file hoặc graph
            "numVertices": int,        # Số đỉnh n
            "numEdges": int,           # Số cạnh m
            "encodingType": str,       # "order" / "pairwise"
            "solverType": str,         # "incremental" / "repeated"
            "status": str,             # "OPTIMAL" / "FEASIBLE"
            "bestUB": int,             # Bandwidth tối ưu (hoặc tốt nhất) tìm được
            "verifiedBW": int,         # Bandwidth đã xác minh qua verifyLabeling()
            "labeling": list[int],     # Mảng hoán vị nhãn gán 0-indexed [pos_v1, pos_v2, ...]
            "totalTime": float,        # Tổng thời gian giải (seconds)
            "maxVars": int,            # Số lượng biến SAT lớn nhất
            "maxClauses": int,         # Số lượng mệnh đề CNF lớn nhất
            "trace": list[dict],       # Lịch sử các bước thử nghiệm UB; isSat = None is a bound interrupted at the deadline
            "terminationReason": str,  # "completed" / "time_limit"
            "deadlineOvershootSeconds": float  # max(0, totalTime - timeLimit)
        }
    """

    # ĐỌC FILE ĐỒ THỊ
    instanceName = ""

    if filePath is not None:
        instanceName = os.path.basename(filePath)
        n, edges = parseFile(filePath)
    else: raise ValueError( "->[ERROR]: File path không hợp lệ." )

    if verbose:
        print(f"\n==================================================")
        print(f"SOLVING GRAPH:      {instanceName} (n={n}, m={len(edges)})")
        

    # KHỞI TẠO UB = IDENTITY LABELING:
    idLabeling = [i + 1 for i in range(n)] # 1-index based labeling / labeling bắt đầu đếm từ 1
    initUB = verifyLabeling(n, edges, idLabeling)

    if verbose:
        print(f"Initial UB:         {initUB}")
        

    # TRUYỀN ENCODER VÀ SOLVER
    ecTypeNormalized = encodingType.lower()
    slTypeNormalized = solverType.lower()

    if ecTypeNormalized not in ("order, pairwise"):
        raise ValueError(f" ->[ERROR]: PP encoding {ecTypeNormalized} không hợp lệ (order, pairwise)")

    if slTypeNormalized == "repeated":
        solver = RepeatedSATSolver(n, edges, encodingType=ecTypeNormalized, verbose=verbose)
    elif slTypeNormalized == "incremental":
        solver = IncrementalSATSolver(n, edges, encodingType=ecTypeNormalized, verbose=verbose)
    else: raise ValueError(f" ->[ERROR]: PP giải {slTypeNormalized} không hợp lệ (order, incremental)")

    if verbose:
        print(f"Method:             {encodingType.upper()} | {solverType.upper()}")
        print(f"==================================================")


    # GIẢI BÀI TOÁN

    result = solver.solve(initUB, timeLimit)
    verifiedBandwidth = verifyLabeling(n, edges, result['labeling'])
    
    
    assert verifiedBandwidth == result["bestUB"], f" -> [ERROR] Bandwidth kiểm tra lại không khớp kết quả."
    
    output = {
        "instance": instanceName,
        "numVertices": n,
        "numEdges": len(edges),
        "encodingType": ecTypeNormalized,
        "solverType": slTypeNormalized,
        "status": result["status"],
        "bestUB": result["bestUB"],
        "verifiedBW": verifiedBandwidth,
        "labeling": result["labeling"],
        "totalTime": result["totalTime"],
        "maxVars": result["maxVars"],
        "maxClauses": result["maxClauses"],
        "trace": result["trace"],
        "terminationReason": result["terminationReason"],
        "deadlineOvershootSeconds": result["deadlineOvershootSeconds"]
    }

    if verbose:
        print(f"\n ->[FINISHED]\n   Status: {output['status']}\n   Best BW: {output['bestUB']}\n   Time: {output['totalTime']:.3f}s\n")

    return output
