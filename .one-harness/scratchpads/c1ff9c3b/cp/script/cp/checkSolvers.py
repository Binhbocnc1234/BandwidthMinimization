import argparse
import contextlib
import io
import platform
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path

from .cpSolver import CPSolver
from .teamBridge import verifyLabeling
from .runCP import writeJson


def checkSolver(solverType, executable=None):
    """Thử backend trên đồ thị 4 đỉnh có tối ưu đã biết bằng 1.

    Trả về trạng thái, kết quả/lỗi, log, phiên bản package và môi trường.
    Probe nhỏ không thay thế xác minh license cho campaign.
    """
    # KHỞI TẠO BẢN GHI VÀ BỘ ĐỆM LOG
    output = io.StringIO()
    record = {
        "solver": solverType,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "full_benchmark_license": "NOT_VERIFIED",
        "evidence_scope": "tiny graph only",
    }

    # CHẠY BÀI THỬ THẬT: identity có B=3, tối ưu có B=1.
    try:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            # Nghiệm ban đầu có bandwidth 3; nghiệm tối ưu có bandwidth 1.
            edges = [(1, 4), (2, 3), (3, 4)]
            result = CPSolver(4, edges, solverType, verifyLabeling).solve(
                3, 5, executable=executable
            )

        if result["status"] != "OPTIMAL" or result["bestUB"] != 1:
            raise RuntimeError("Bộ giải chưa chứng minh được bandwidth tối ưu bằng 1")

        record.update(availability="AVAILABLE_TINY_TEST", result=result)

    except Exception as error:
        # Phân biệt thiếu thư viện/runtime với lỗi mô hình hoặc API.
        unavailable = isinstance(error, ModuleNotFoundError) or "Executable file" in str(error)
        record.update(
            availability="UNAVAILABLE" if unavailable else "PROBE_FAILED", error=repr(error)
        )

    # LƯU LOG VÀ PHIÊN BẢN THƯ VIỆN
    record["log"] = output.getvalue()

    packages = ["ortools"] if solverType == "ortools" else ["docplex", "cplex"]
    record["packages"] = {}

    for package in packages:
        try:
            record["packages"][package] = version(package)
        except PackageNotFoundError:
            record["packages"][package] = None

    return record


def main():
    """Kiểm tra lần lượt hai backend và ghi JSON bằng chứng ra file mới."""
    parser = argparse.ArgumentParser(description="Kiểm tra các bộ giải CP bằng một đồ thị nhỏ.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--cpo-executable")
    args = parser.parse_args()

    if Path(args.output).exists():
        parser.error("File kết quả đã tồn tại. Hãy chọn tên mới để giữ kết quả trước.")

    # KIỂM TRA TUẦN TỰ, KHÔNG CHẠY HAI SOLVER ĐỒNG THỜI
    records = [checkSolver(solverType, args.cpo_executable) for solverType in ["ortools", "cpo"]]

    writeJson(args.output, records)

    for record in records:
        print(record["solver"], record["availability"], record.get("error", ""))

    print(
        "Chạy thành công trên đồ thị nhỏ chưa xác nhận "
        "giấy phép cho toàn bộ bộ dữ liệu thực nghiệm."
    )


if __name__ == "__main__":
    main()
