"""Download the selected NIST matrices and derive unweighted BMP graphs."""

import gzip
import hashlib
import json
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1] / "data" / "HarwellBoeing"
SELECTION = {
    "ibm32": "smtape",
    "bcspwr01": "bcspwr",
    "bcsstk01": "bcsstruc1",
    "bcspwr02": "bcspwr",
    "curtis54": "smtape",
    "ash85": "smtape",
    "bcspwr03": "bcspwr",
    "bcsstk04": "bcsstruc1",
    "bcspwr04": "bcspwr",
    "bcspwr05": "bcspwr",
    "bcsstk20": "bcsstruc3",
    "sherman1": "sherman",
}


def parse_matrix(payload: bytes) -> tuple[int, set[tuple[int, int]], int]:
    lines = gzip.decompress(payload).decode("ascii").splitlines()
    header = lines[0].lower().split()
    if len(header) != 5 or header[:3] != ["%%matrixmarket", "matrix", "coordinate"]:
        raise ValueError(f"Unsupported Matrix Market header: {lines[0]}")
    field, symmetry = header[3:]
    if field not in {"pattern", "real", "integer"}:
        raise ValueError(f"Unsupported field: {field}")
    if symmetry not in {"general", "symmetric"}:
        raise ValueError(f"Unsupported symmetry: {symmetry}")
    records = [line.split() for line in lines[1:] if line.strip() and not line.startswith("%")]
    rows, columns, entries = map(int, records[0])
    if rows != columns or rows < 1 or len(records) - 1 != entries:
        raise ValueError("Matrix must be square with its declared number of entries")
    edges: set[tuple[int, int]] = set()
    coordinates: set[tuple[int, int]] = set()
    for record in records[1:]:
        if len(record) != (2 if field == "pattern" else 3):
            raise ValueError(f"Invalid coordinate record: {record}")
        row, column = map(int, record[:2])
        if not (1 <= row <= rows and 1 <= column <= columns):
            raise ValueError(f"Coordinate outside matrix: {record}")
        if (row, column) in coordinates:
            raise ValueError("Duplicate matrix coordinates need explicit aggregation")
        coordinates.add((row, column))
        value = 1.0 if field == "pattern" else float(record[2].replace("D", "E"))
        if not math.isfinite(value):
            raise ValueError("Non-finite matrix value")
        if row != column and value != 0:
            edges.add((min(row, column), max(row, column)))
    return rows, edges, entries


def component_count(vertices: int, edges: set[tuple[int, int]]) -> int:
    neighbors: list[list[int]] = [[] for _ in range(vertices + 1)]
    for left, right in edges:
        neighbors[left].append(right)
        neighbors[right].append(left)
    remaining = set(range(1, vertices + 1))
    count = 0
    while remaining:
        stack = [remaining.pop()]
        count += 1
        while stack:
            for neighbor in neighbors[stack.pop()]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
    return count


def prepare_instance(item: tuple[str, str]) -> dict:
    name, group = item
    url = f"https://math.nist.gov/pub/MatrixMarket2/Harwell-Boeing/{group}/{name}.mtx.gz"
    page = f"https://math.nist.gov/MatrixMarket/data/Harwell-Boeing/{group}/{name}.html"
    # NIST returns HTTP 403 for Python's default User-Agent.
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as response:
        payload = response.read()
    retrieved_at = datetime.now(timezone.utc).isoformat()
    vertices, edges, entries = parse_matrix(payload)
    graph = f"c Source: {url}\np edge {vertices} {len(edges)}\n"
    graph += "".join(f"e {left} {right}\n" for left, right in sorted(edges))
    graph_bytes = graph.encode("ascii")
    raw_path = ROOT / "raw" / f"{name}.mtx.gz"
    graph_path = ROOT / "graphs" / f"{name}.col"
    raw_path.write_bytes(payload)
    graph_path.write_bytes(graph_bytes)
    components = component_count(vertices, edges)
    print(f"{name}: {vertices} vertices, {len(edges)} edges, {components} components", flush=True)
    return {
        "name": name,
        "source_page": page,
        "download_url": url,
        "retrieved_at_utc": retrieved_at,
        "raw_file": raw_path.relative_to(ROOT).as_posix(),
        "raw_sha256": hashlib.sha256(payload).hexdigest(),
        "graph_file": graph_path.relative_to(ROOT).as_posix(),
        "graph_sha256": hashlib.sha256(graph_bytes).hexdigest(),
        "vertices": vertices,
        "edges": len(edges),
        "stored_matrix_entries": entries,
        "connected_components": components,
    }


def main() -> None:
    for folder in ("raw", "graphs"):
        (ROOT / folder).mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        instances = list(pool.map(prepare_instance, SELECTION.items()))
    manifest = {
        "collection": "Harwell-Boeing Sparse Matrix Collection (NIST Matrix Market)",
        "collection_url": "https://math.nist.gov/MatrixMarket/data/Harwell-Boeing/",
        "reference_paper_doi": "10.1016/j.ins.2014.12.041",
        "selection": "12-instance initial subset; not the complete 113-instance paper benchmark",
        "instances": sorted(instances, key=lambda instance: (instance["vertices"], instance["name"])),
    }
    (ROOT / "Manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(instances)} instances; manifest: {ROOT / 'Manifest.json'}", flush=True)


if __name__ == "__main__":
    main()
