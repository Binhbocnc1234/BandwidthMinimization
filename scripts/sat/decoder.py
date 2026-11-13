def decodeOrderEncoding(model: list[int], numVertices: int) -> list[int]:
    """
    Giả̉i mã kết quả model thu được từ PySAT Solver cho Order Encoding thành mảng labeling.
    
    model: Danh sách các literal (1-indexed, có dấu dương/âm) từ solver.get_model()
    numVertices: Số lượng đỉnh n (|V|)
    
    Trả về:
        labeling: Danh sách 0-indexed kích thước n. 
                  labeling[v - 1] là vị trí position (1..n) được gán cho đỉnh v.
    """

    if not model:
        return [i + 1 for i in range(numVertices)]

    positiveVars = set(lit for lit in model if lit > 0)

    labeling = [0] * numVertices

    for u in range(1, numVertices + 1):
        # f(u) là chỉ số i nhỏ nhất (1..n) mà L(u, i) = True

        currPos = numVertices

        for i in range(1, numVertices + 1):
            varID = (u - 1) * numVertices + i

            if varID in positiveVars:
                currPos = i
                break

        labeling[u - 1] = currPos

    return labeling


def decodePairwiseEncoding(model: list[int], numVertices: int) -> list[int]:
    """
    Giải mã kết quả model thu được từ PySAT Solver cho Pairwise Encoding thành mảng labeling.
    
    model: Danh sách các literal từ solver.get_model()
    numVertices: Số lượng đỉnh n (|V|)
    
    Trả về:
        labeling: Danh sách 0-indexed kích thước n.
                  labeling[v - 1] là vị trí position (1..n) được gán cho đỉnh v.
    """

    if not model:
        return [i + 1 for i in range(numVertices)]

    positiveVars = set(lit for lit in model if lit > 0)

    labeling = [0] * numVertices

    for u in range(1, numVertices + 1):
        # f(u) là vị trí k (1..n) mà X(u, k) = True

        currPos = numVertices
        for k in range(1, numVertices + 1):
            varID = (u - 1) * numVertices + k

            if varID in positiveVars:
                currPos = k
                break
            
        labeling[u - 1] = currPos

    return labeling