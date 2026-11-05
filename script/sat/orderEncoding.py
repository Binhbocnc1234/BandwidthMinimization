class OrderEncoder:
    def __init__(self, numVertices: int, edges: list[tuple[int,int]]):
        """
        Khởi tạo Order Encoding.
        numVertices: Số lượng đỉnh n = |V|.
        edges: Danh sách các cạnh (u, v) theo CTDL tuple, 1 <= u < v <= n
        """

        self.numVertices = numVertices
        self.edges = edges

    def varL(self, u: int, i: int) -> int:
        """
        Ánh xạ các biến L(u, i) thành variable ID, phục vụ cho giải SAT.
        u: 1..n, i: 1..n,
        Trả về: ID = (u - 1) * n + i
        """

        return (u - 1) * self.numVertices + i

    def encode(self, ub: int, includeEdgeConstraints: bool = True) -> tuple[list[list[int]], dict]:
        """
        Tạo danh sách các mệnh đề CNF, kèm với giá trị Upper Bound (UB)
        Trả về: clauses (list[list[int]]), 
                metadata (dict) 
        """

        clauses = []
        n = self.numVertices

        # L(u, n)
        for u in range(1, n + 1):
            clauses.append([self.varL(u, n)])

        #  L(u, i) -> L(u, i + 1) <=> ¬L(u, i) v L(u, i + 1)
        for u in range(1, n + 1):
            for i in range(1, n):
                clauses.append([-self.varL(u, i), self.varL(u, i + 1)])

        # AMO (Bijection): X(u,i) ↔ L(u, i) ∧ ¬L(u, i - 1)
        # Với 2 đỉnh u, v bất kì:
        # <=> ¬( (L(u, i) ∧ ¬L(u, i - 1)) ∧ (L(v, i) ∧ ¬L(v, i - 1)) )
        # <=> ¬L(u, i) v L(u, i - 1) v ¬L(v, i) v L(v, i - 1)
        for i in range(1, n + 1):
            for u in range(1, n + 1):
                for v in range(u + 1, n + 1):
                    clause = [-self.varL(u, i), -self.varL(v, i)]

                    # Không cho phép 2 đỉnh u, v cùng "chạm ngưỡng" True tại i nếu trước đó (i-1) cả 2 đều chưa True
                    if i == 1:
                        clauses.append([-self.varL(u, 1), -self.varL(v, 1)])
                    else:
                    # Dùng thuộc tính chuyển tiếp của Order Encoding:
                    # Giới hạn số lượng nhãn L(u, i) tăng lên theo vị trí
                        clauses.append([-self.varL(u, i), -self.varL(v, i), self.varL(u, i - 1), self.varL(v, i - 1)])

                        
        # Edge Distance
        # L(u, k) -> L(v, k + ub)  <=>  ~L(u, k) v L(v, k + ub)
        # L(v, k) -> L(u, k + ub)  <=>  ~L(v, k) v L(u, k + ub)

        if includeEdgeConstraints:
            for u, v in self.edges:
                for k in range(1, n + 1):
                    pos = k + ub

                    if pos < n:
                        clauses.append([-self.varL(u, k), self.varL(v, pos)])
                        clauses.append([-self.varL(v, k), self.varL(u, pos)])

        metadata = {
            "numVars":      n * n,
            "numClauses":   len(clauses),
            "encoding":     "order",
            "UB":           ub
        }

        return clauses, metadata