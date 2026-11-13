import itertools
import json
import os
from pathlib import Path
import random
import pytest
from scripts.cp.checkSolvers import checkSolver
from scripts.cp.cpSolver import CPSolver
from scripts.cp.runCP import exportResult, loadCommittedGraph
from scripts.cp.teamBridge import parseColFile, verifyLabeling


def bruteForceOptimum(numVertices, edges):
    """Vét cạn mọi hoán vị để tìm tối ưu thật trên đồ thị nhỏ.
    Oracle tính trực tiếp từ cạnh, độc lập với mô hình CP và checker dùng chung.
    """
    return min(
        max((abs(p[u - 1] - p[v - 1]) for u, v in edges), default=0)
        for p in itertools.permutations(range(1, numVertices + 1))
    )


# DỮ LIỆU TEST: đỉnh đơn, không cạnh, đường đi, chu trình, đầy đủ, không liên thông.
CASES = [
    (1, []),
    (5, []),
    (4, [(1, 4), (2, 3), (3, 4)]),
    (5, [(1, 2), (2, 3), (3, 4), (4, 5), (1, 5)]),
    (5, list(itertools.combinations(range(1, 6), 2))),
    (6, [(1, 4), (2, 5), (4, 6)]),
    (8, [(1, 8), (2, 7), (3, 6)]),
]
# Thêm 5 đồ thị nhỏ; seed cố định để các lần chạy dùng cùng dữ liệu.
randomGenerator = random.Random(17)
for _ in range(5):
    CASES.append(
        (
            5,
            [
                edge
                for edge in itertools.combinations(range(1, 6), 2)
                if randomGenerator.random() < 0.4
            ],
        )
    )


@pytest.fixture(scope="session", params=["ortools", "cpo"])
def backend(request):
    """Chạy bộ test cho từng backend; CPO thiếu executable có thể được skip.
    Đặt REQUIRE_CPO=1 để coi việc thiếu CPO là lỗi bắt buộc xử lý.
    """
    if request.param == "cpo":
        probe = checkSolver("cpo", os.getenv("CPO_EXECUTABLE"))
        if probe["availability"] != "AVAILABLE_TINY_TEST":
            if "Executable file" not in probe.get("error", ""):
                pytest.fail("CPO implementation/probe error, not a missing runtime: " + str(probe))
            if os.getenv("REQUIRE_CPO") == "1":
                pytest.fail(str(probe))
            pytest.skip("CPO solve unavailable: " + probe.get("error", "probe failed"))
    return request.param


@pytest.mark.parametrize("numVertices,edges", CASES)
def test_real_solve_extract_check_export(backend, numVertices, edges, tmp_path):
    """Kiểm tra toàn luồng: đọc file -> giải thật -> so oracle -> xuất/đọc lại JSON."""
    # 1. TẠO VÀ ĐỌC ĐỒ THỊ THỬ
    inputPath = tmp_path / "graph.col"
    inputPath.write_text(
        f"p edge {numVertices} {len(edges)}\n" + "".join(f"e {u} {v}\n" for u, v in edges)
    )
    numVertices, edges = parseColFile(str(inputPath))
    initUB = verifyLabeling(numVertices, edges, list(range(1, numVertices + 1)))
    # 2. GIẢI THẬT VÀ THU CÁC NGHIỆM ĐƯỢC CALLBACK BÁO
    incumbentEvents = []
    result = CPSolver(numVertices, edges, backend, verifyLabeling).solve(
        initUB,
        timeLimit=15,
        onIncumbent=lambda *event: incumbentEvents.append(event),
        executable=os.getenv("CPO_EXECUTABLE"),
    )
    # 3. SO SÁNH VỚI VÉT CẠN, KIỂM TRA CẬN VÀ NGHIỆM
    assert result["status"] == "OPTIMAL"
    assert result["bestUB"] == bruteForceOptimum(numVertices, edges)
    assert result["lowerBound"] == result["bestUB"]
    assert result["totalTime"] >= result["constructionTime"] >= 0
    assert incumbentEvents[0][2] == "identity"
    for labeling, bestUB, _ in incumbentEvents:
        assert verifyLabeling(numVertices, edges, labeling) == bestUB
    # 4. XUẤT JSON, ĐỌC LẠI VÀ KIỂM TRA
    record = exportResult(result, tmp_path / "out", inputPath, numVertices, edges, 15)
    exported = json.loads((tmp_path / "out" / "labeling.json").read_text())
    assert verifyLabeling(numVertices, edges, exported) == record["bandwidth"]
    assert record["clauses"] is None
    assert record["method"] == ("cp_ortools" if backend == "ortools" else "cp_cpo")


def test_zero_budget_keeps_identity():
    """Ngân sách 0: không tìm kiếm nhưng vẫn trả nghiệm identity hợp lệ."""
    edges = [(1, 4), (2, 3), (3, 4)]
    result = CPSolver(4, edges, "ortools", verifyLabeling).solve(3, timeLimit=0)
    assert result["status"] == "FEASIBLE"
    assert result["nativeStatus"] == "NOT_STARTED"
    assert result["incumbentOrigin"] == "identity"
    assert result["labeling"] == [1, 2, 3, 4]


def test_wrong_initial_bound_is_rejected():
    """Từ chối initUB không bằng bandwidth thực tế của identity."""
    with pytest.raises(ValueError, match="initUB"):
        CPSolver(4, [(1, 4)], "ortools", verifyLabeling).solve(1)


def test_checker_failure_is_not_feasible():
    """Checker báo lỗi phải phát exception, không được trả FEASIBLE."""

    def rejectingChecker(numVertices, edges, labeling):
        if labeling != list(range(1, numVertices + 1)):
            raise ValueError("injected independent checker failure")
        return verifyLabeling(numVertices, edges, labeling)

    with pytest.raises(ValueError, match="checker failure"):
        CPSolver(4, [(1, 4), (2, 3), (3, 4)], "ortools", rejectingChecker).solve(3)


def test_export_rejects_invalid_labeling(tmp_path):
    """Không cho xuất nghiệm có hai đỉnh trùng vị trí."""
    with pytest.raises(ValueError):
        exportResult({"labeling": [1, 1], "bestUB": 1}, tmp_path, "unused", 2, [(1, 2)], 1)


def test_cpo_real_model_can_be_serialized_without_runtime():
    """Kiểm tra mô hình IBM có AllDifferent và mục tiêu, chưa cần chạy executable."""
    solver = CPSolver(4, [(1, 4), (2, 3), (3, 4)], "cpo", verifyLabeling)
    model, position, bandwidth = solver.buildModel(3)
    cpoText = model.get_cpo_string()
    assert "alldiff" in cpoText.lower()
    assert "minimize" in cpoText
    assert len(position) == 4


def test_invalid_graph_rejected():
    """Từ chối cạnh trùng trước khi dựng mô hình."""
    with pytest.raises(ValueError, match="Duplicate"):
        CPSolver(3, [(1, 2), (1, 2)], "ortools", verifyLabeling)


def test_existing_dataset_and_checker_bridge():
    """Đọc ibm32 thật trong data, kiểm tra manifest và checker dùng chung."""
    graph = Path(__file__).resolve().parents[2] / "data/HarwellBoeing/graphs/ibm32.col"
    numVertices, edges = loadCommittedGraph(graph)
    assert numVertices == 32
    assert len(edges) == 90
    assert verifyLabeling(numVertices, edges, list(range(1, numVertices + 1))) >= 1


def test_checksum_mismatch_is_rejected(monkeypatch):
    """Giả lập nội dung file thay đổi để kiểm tra cơ chế SHA-256."""
    graph = Path(__file__).resolve().parents[2] / "data/HarwellBoeing/graphs/ibm32.col"
    original = Path.read_bytes

    def modifiedBytes(path):
        data = original(path)
        return data + b"\nc modified" if path.resolve() == graph.resolve() else data

    monkeypatch.setattr(Path, "read_bytes", modifiedBytes)
    with pytest.raises(ValueError, match="SHA-256"):
        loadCommittedGraph(graph)


def test_invalid_seed_is_rejected():
    """Từ chối seed âm trước khi gọi backend."""
    with pytest.raises(ValueError, match="seed"):
        CPSolver(2, [(1, 2)], "ortools", verifyLabeling).solve(1, seed=-1)
