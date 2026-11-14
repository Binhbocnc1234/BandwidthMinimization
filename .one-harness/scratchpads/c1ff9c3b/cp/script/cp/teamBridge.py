"""Dùng chung bộ đọc đồ thị và checker với Member 1.

parseColFile(path) -> (n, edges).
verifyLabeling(n, edges, labeling) -> bandwidth; báo lỗi nếu không là hoán vị.
Quy ước: labeling[u - 1] là vị trí của đỉnh u.

CP chỉ dùng loader/checker, không gọi SAT để tìm nghiệm.
Khi Member 3 cung cấp module shared, đổi nguồn import tại đây.
Hiện SATSolverWrapper còn import PySAT nên môi trường CP cũng cần python-sat.
"""

import sys
from pathlib import Path

# XÁC ĐỊNH THƯ MỤC SAT: cần cho các import nội bộ hiện tại của Member 1.
satDirectory = Path(__file__).resolve().parents[1] / "sat"
if str(satDirectory) not in sys.path:
    sys.path.insert(0, str(satDirectory))

# ĐỔI TÊN parseFile ĐỂ NÊU RÕ ĐỊNH DẠNG ĐẦU VÀO .col.
from SATSolverWrapper import parseFile as parseColFile, verifyLabeling
