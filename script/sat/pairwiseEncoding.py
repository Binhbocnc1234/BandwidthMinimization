class PairwiseEncoder:
    def __init__(self, numVerticies: int, edges: list[tuple[int,int]]):
        """
        Khởi tạo Pairwise Encoding.
        numVerticies: Số lượng đỉnh n = |V|.
        edges: Danh sách các cạnh (u, v) theo CTDL tuple, 1 <= u < v <= n
        """

        self.numVerticies = numVerticies
        self.edges = edges

    def varX(self, u: int, k: int) -> int:
        """
        Ánh xạ các biến X(u, k) thành variable ID, phục vụ cho giải SAT.
        u: 1..n, k: 1..n,
        Trả về: ID = (u - 1) * n + k
        """

        return (u - 1) * self.numVerticies + k

    def encode(self, ub: int, includeEdgeConstraints: bool = True) -> tuple[list[list[int]], dict]:
        """
        Tạo danh sách các mệnh đề CNF, kèm với giá trị Upper Bound (UB)
        Trả về: clauses (list[list[int]]), 
                metadata (dict) 
        """

        clauses = []
        n = self.numVerticies

        # ALO: Với mọi k, X(u, k)
        for u in range(1, n + 1):
            clauses.append([self.varX(u, k) for k in range(1, n + 1)])

        # AMO:

            # Mỗi đỉnh nhận đúng 1 vị trí
            # X(u, k1) -> ¬X(u, k2) <=> ¬X(u, k1) v ¬X(u, k2)
        for u in range(1, n + 1):
            for k1 in range(1, n + 1):
                for k2 in range(k1 + 1, n + 1):
                    clauses.append([-self.varX(u, k1), -self.varX(u, k2)])

            # Mội vị trí nhận đúng 1 đỉnh
            # X(u1, k) -> ¬X(u2, k) <=> ¬X(u1, k) v ¬X(u2, k)
        for k in range(1, n + 1):
            for u1 in range(1, n + 1):
                for u2 in range(u1 + 1, n + 1):
                    clauses.append([-self.varX(u1, k), -self.varX(u2, k)])

        # Edge Distance
        # X(u, k) -> X(v, j), X(v, k) -> X(u, j)
        # j chạy từ k - UB (chặn bởi 1) -> k + UB (chặn bởi n)
        if includeEdgeConstraints:
            for u, v in self.edges:
                for k in range(1, n + 1):
                    minJ = max(1, k - ub)
                    maxJ = min(n, k + ub)

                    validRangeV = [self.varX(v, j) for j in range(minJ, maxJ + 1)]
                    validRangeU = [self.varX(u, j) for j in range(minJ, maxJ + 1)]

                    clauses.append([-self.varX(u, k)] + validRangeV)
                    clauses.append([-self.varX(v, k)] + validRangeU)

        metadata = {
            "numVars":      n * n,
            "numClauses":   len(clauses),
            "encoding":     "pairwise",
            "UB":           ub
        }

        return clauses, metadata



