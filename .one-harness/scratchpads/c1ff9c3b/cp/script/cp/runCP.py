import sys

# Không ghi .pyc khi import các module.
# Chạy trực tiếp file này để cấu hình có hiệu lực trước khi nạp package.
sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import math
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from script.cp.cpSolver import CPSolver
from script.cp.teamBridge import parseColFile, verifyLabeling


def loadCommittedGraph(inputPath):
    """Đọc đồ thị .col đã được khai báo trong Manifest.json.

    inputPath: Đường dẫn file trong data/HarwellBoeing/graphs/.
    Kiểm tra SHA-256, số đỉnh và số cạnh trước khi đưa cho solver.
    Trả về: (numVertices, edges). Không tự tải lại hoặc thay thế dữ liệu.
    """
    inputPath = Path(inputPath).resolve()
    datasetRoot = PROJECT_ROOT / "data" / "HarwellBoeing"

    manifest = json.loads((datasetRoot / "Manifest.json").read_text(encoding="utf-8"))

    for item in manifest["instances"]:
        graphPath = (datasetRoot / item["graph_file"]).resolve()

        if graphPath == inputPath:
            digest = hashlib.sha256(inputPath.read_bytes()).hexdigest()

            if digest != item["graph_sha256"]:
                raise ValueError("Nội dung file đồ thị không khớp SHA-256 trong Manifest.json.")

            numVertices, edges = parseColFile(str(inputPath))

            if (numVertices, len(edges)) != (item["vertices"], item["edges"]):
                raise ValueError("Số đỉnh hoặc số cạnh không khớp Manifest.json.")

            return numVertices, edges

    raise ValueError("File đồ thị phải nằm trong danh sách của Manifest.json.")


def writeJson(filePath, payload):
    """Lưu dữ liệu JSON UTF-8 qua file tạm rồi thay file đích.
    Tự tạo thư mục cha; hạn chế file kết quả chính bị ghi dở khi gián đoạn.
    """
    filePath = Path(filePath)
    filePath.parent.mkdir(parents=True, exist_ok=True)

    temporary = filePath.with_suffix(filePath.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(filePath)


def prepareOutput(outputDirectory):
    """Chuẩn bị thư mục output và xóa các file kết quả cũ do runner tạo.
    Muốn giữ lần chạy trước: truyền một outputDirectory khác.
    """
    outputDirectory = Path(outputDirectory)
    outputDirectory.mkdir(parents=True, exist_ok=True)

    generatedFiles = (
        "result.json",
        "labeling.json",
        "trace.json",
        "incumbent.json",
        "solver.log",
        "error.json",
    )

    for filename in generatedFiles:
        filePath = outputDirectory / filename
        if filePath.is_file():
            filePath.unlink()

    return outputDirectory


def exportResult(result, outputDirectory, inputPath, numVertices, edges, timeLimit):
    """Kiểm tra nghiệm, lưu labeling/trace và xuất result.json.

    result: Dictionary trả về từ CPSolver.solve().
    outputDirectory: Thư mục nhận các file kết quả của một lần chạy.
    inputPath, numVertices, edges: Dữ liệu đầu vào để kiểm tra và ghi nguồn.
    timeLimit: Ngân sách được yêu cầu, tính bằng giây.

    Trả về: record đã ghi vào result.json.
    Đây là kết quả chạy thử CP; runner campaign thuộc Member 3.
    """
    outputDirectory = Path(outputDirectory)

    checkedBw = verifyLabeling(numVertices, edges, result["labeling"])

    if checkedBw != result["bestUB"]:
        raise ValueError("Bandwidth tính lại không khớp kết quả của bộ giải.")

    writeJson(outputDirectory / "labeling.json", result["labeling"])
    writeJson(outputDirectory / "trace.json", result["trace"])

    record = {
        "artifact_kind": "local_cp_smoke_NOT_CAMPAIGN",
        "schema_version": 1,
        "instance": Path(inputPath).stem,
        "input_sha256": hashlib.sha256(Path(inputPath).read_bytes()).hexdigest(),
        "n": numVertices,
        "m": len(edges),
        "method": result["method"],
        "model": result["model"],
        "solver": result["backend"],
        "solver_version": result["backendVersion"],
        "status": result["status"],
        "native_status": result["nativeStatus"],
        "bandwidth": result["bestUB"],
        "lower_bound": result["lowerBound"],
        "initial_upper_bound": result["initUB"],
        "incumbent_origin": result["incumbentOrigin"],
        "elapsed_seconds": result["totalTime"],
        "construction_seconds": result["constructionTime"],
        "search_seconds": result["searchTime"],
        "validation_seconds": result["validationTime"],
        "variables": result["numVars"],
        "constraints": result["numConstraints"],
        "clauses": None,
        "peak_rss_mib": None,
        "time_limit_seconds": timeLimit,
        "termination_reason": result["terminationReason"],
        "threads": 1,
        "requested_seed": result["seed"],
        "effective_seed": result["seed"],
        "labeling_file": "labeling.json",
        "trace_file": "trace.json",
        "log_file": ("solver.log" if (outputDirectory / "solver.log").is_file() else None),
        "hint_submitted": result["hintSubmitted"],
        "hint_accepted": result["hintAccepted"],
        "model_count_scope": result["modelCountScope"],
        "error": None,
        "deadline_overshoot_seconds": result["deadlineOvershoot"],
        "checker": "SATSolverWrapper.verifyLabeling",
    }

    writeJson(outputDirectory / "result.json", record)
    return record


def main():
    """Đọc tham số dòng lệnh, giải một đồ thị và lưu kết quả."""
    # ĐỌC THAM SỐ DÒNG LỆNH
    parser = argparse.ArgumentParser(description="Giải BMP bằng CP.")
    parser.add_argument("input", help="Đường dẫn file đồ thị .col")
    parser.add_argument(
        "--solver",
        "--backend",
        dest="solver",
        choices=["ortools", "cpo"],
        default="ortools",
        help="Bộ giải: ortools hoặc cpo",
    )
    parser.add_argument("--time-limit", type=float, default=10, help="Giới hạn thời gian (giây)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--output", required=True, help="Thư mục kết quả; chạy lại sẽ thay kết quả cũ"
    )
    parser.add_argument("--cpo-executable", help="Đường dẫn executable CP Optimizer")

    args = parser.parse_args()

    # KIỂM TRA THAM SỐ
    if not math.isfinite(args.time_limit) or args.time_limit < 0:
        parser.error("--time-limit phải là số hữu hạn và >= 0.")

    if not 0 <= args.seed <= 2**31 - 1:
        parser.error("--seed phải nằm trong khoảng 0..2147483647.")

    # ĐỌC DỮ LIỆU VÀ TÍNH UB CỦA IDENTITY
    # Chỉ dọn output sau khi đầu vào đã được kiểm tra.
    numVertices, edges = loadCommittedGraph(args.input)
    identityLabeling = list(range(1, numVertices + 1))
    initUB = verifyLabeling(numVertices, edges, identityLabeling)

    outputDirectory = prepareOutput(args.output)

    try:
        solver = CPSolver(numVertices, edges, args.solver, verifyLabeling)

        def saveIncumbent(labeling, bestUB, origin):
            """Lưu identity hoặc nghiệm cải thiện; phải kiểm tra lại nếu bị ngắt."""
            writeJson(
                outputDirectory / "incumbent.json",
                {
                    "labeling": labeling,
                    "bestUB": bestUB,
                    "origin": origin,
                    "validation": "must recheck after interruption",
                },
            )

        # GIẢI BÀI TOÁN; callback lưu nghiệm ngay trong quá trình tìm kiếm.
        result = solver.solve(
            initUB,
            args.time_limit,
            args.seed,
            saveIncumbent,
            outputDirectory / "solver.log",
            args.cpo_executable,
        )

        # KIỂM TRA VÀ XUẤT KẾT QUẢ
        record = exportResult(result, outputDirectory, args.input, numVertices, edges, args.time_limit)

        print(json.dumps(record, indent=2, ensure_ascii=False))

    except Exception as error:
        writeJson(
            outputDirectory / "error.json",
            {
                "status": "ERROR",
                "error": repr(error),
                "note": "Kiểm tra môi trường bằng checkSolvers.py.",
            },
        )
        raise


if __name__ == "__main__":
    main()
