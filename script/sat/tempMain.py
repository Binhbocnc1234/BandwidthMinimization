# main vi du minh hoa wrapper
# TODO: delete later

from SATSolverWrapper import solveBMPSAT

# Gọi chạy Order / Incremental SAT trên file ibm32.col
res = solveBMPSAT(
    filePath="data/HarwellBoeing/graphs/ibm32.col",
    encodingType="pairwise",
    solverType="repeated",
    timeLimit=10.0,
    verbose=True
)

# Lấy các thông tin cần thiết:
print("Trạng thái:", res["status"])
print("Bandwidth tối ưu:", res["bestUB"])
print("Nhãn gán vị trí đỉnh (Labeling):", res["labeling"])
print("Tổng thời gian:", res["totalTime"])

if __name__ == "__main__":
    main()