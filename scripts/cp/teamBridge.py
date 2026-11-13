"""Dùng chung bộ đọc đồ thị và checker của nhóm (scripts/shared, Member 3).

parseColFile(path) -> (n, edges).
verifyLabeling(n, edges, labeling) -> bandwidth; báo lỗi nếu không là hoán vị.
Quy ước: labeling[u - 1] là vị trí của đỉnh u.
"""

from scripts.shared.graphInput import loadColFile as parseColFile
from scripts.shared.labeling import checkLabeling as verifyLabeling
