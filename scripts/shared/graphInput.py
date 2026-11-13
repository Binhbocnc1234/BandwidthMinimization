"""Shared graph input for every BMP method, following the Graph Input section of docs/ExperimentContract.md."""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

Edge = tuple[int, int]

# int() also accepts "+3", " 3" and "3_0", which the contract's integer fields do not allow.
_UNSIGNED_INTEGER = re.compile(r"[0-9]+")


class GraphFormatError(ValueError):
    """A .col input breaks the contract; the message names the source and line."""


class DatasetIntegrityError(ValueError):
    """A dataset file is missing, or differs from the checksum or size recorded in the manifest."""


@dataclass(frozen=True)
class ManifestInstance:
    """One instance entry of data/HarwellBoeing/Manifest.json."""

    name: str
    graphPath: Path
    graphSha256: str
    numVertices: int
    numEdges: int


def _parseInteger(field: str, source: str, lineNumber: int) -> int:
    if _UNSIGNED_INTEGER.fullmatch(field) is None:
        raise GraphFormatError(f"{source}:{lineNumber}: expected a non-negative integer, found {field!r}")
    return int(field)


def parseColText(text: str, source: str) -> tuple[int, list[Edge]]:
    """Parse .col text into (n, edges sorted lexicographically). `source` only labels error messages."""
    numVertices: int | None = None
    declaredEdges: int = 0
    edges: list[Edge] = []
    seen: set[Edge] = set()

    for lineNumber, rawLine in enumerate(text.splitlines(), 1):
        line: str = rawLine.strip()
        if not line or line.startswith("c"):
            continue
        fields: list[str] = line.split()
        if fields[0] == "p":
            if numVertices is not None:
                raise GraphFormatError(f"{source}:{lineNumber}: second 'p' line")
            if len(fields) != 4 or fields[1] != "edge":
                raise GraphFormatError(f"{source}:{lineNumber}: expected 'p edge n m', found {line!r}")
            numVertices = _parseInteger(fields[2], source, lineNumber)
            declaredEdges = _parseInteger(fields[3], source, lineNumber)
            if numVertices < 1:
                raise GraphFormatError(f"{source}:{lineNumber}: n must be at least 1")
        elif fields[0] == "e":
            if numVertices is None:
                raise GraphFormatError(f"{source}:{lineNumber}: edge before the 'p edge n m' line")
            if len(fields) != 3:
                raise GraphFormatError(f"{source}:{lineNumber}: expected 'e u v', found {line!r}")
            u: int = _parseInteger(fields[1], source, lineNumber)
            v: int = _parseInteger(fields[2], source, lineNumber)
            if not 1 <= u < v <= numVertices:
                raise GraphFormatError(f"{source}:{lineNumber}: edge ({u}, {v}) breaks 1 <= u < v <= {numVertices}")
            if (u, v) in seen:
                raise GraphFormatError(f"{source}:{lineNumber}: duplicate edge ({u}, {v})")
            seen.add((u, v))
            edges.append((u, v))
        else:
            raise GraphFormatError(f"{source}:{lineNumber}: unknown record type {fields[0]!r}")

    if numVertices is None:
        raise GraphFormatError(f"{source}: no 'p edge n m' line")
    if len(edges) != declaredEdges:
        raise GraphFormatError(f"{source}: declares {declaredEdges} edges but lists {len(edges)}")
    return numVertices, sorted(edges)


def loadColFile(path: str | Path) -> tuple[int, list[Edge]]:
    """Read a UTF-8 .col file into (n, sorted edges). Every vertex 1..n is kept, including isolated ones."""
    filePath: Path = Path(path)
    return parseColText(filePath.read_bytes().decode("utf-8"), str(filePath))


def readManifest(manifestPath: str | Path) -> list[ManifestInstance]:
    """List the manifest's instances in manifest order, which is the campaign's instance order."""
    manifestFile: Path = Path(manifestPath).resolve()
    manifest: dict = json.loads(manifestFile.read_text(encoding="utf-8"))
    return [
        ManifestInstance(
            name=item["name"],
            graphPath=manifestFile.parent / item["graph_file"],
            graphSha256=item["graph_sha256"],
            numVertices=item["vertices"],
            numEdges=item["edges"],
        )
        for item in manifest["instances"]
    ]


def loadManifestInstance(instance: ManifestInstance) -> tuple[int, list[Edge]]:
    """Load an instance after checking its SHA-256 and size against the manifest. Never downloads or substitutes a file."""
    if not instance.graphPath.is_file():
        raise DatasetIntegrityError(f"{instance.name}: graph file {instance.graphPath} is missing")
    content: bytes = instance.graphPath.read_bytes()
    digest: str = hashlib.sha256(content).hexdigest()
    if digest != instance.graphSha256:
        raise DatasetIntegrityError(f"{instance.name}: SHA-256 {digest} differs from the manifest's {instance.graphSha256}")
    numVertices, edges = parseColText(content.decode("utf-8"), str(instance.graphPath))
    if (numVertices, len(edges)) != (instance.numVertices, instance.numEdges):
        raise DatasetIntegrityError(
            f"{instance.name}: file has n={numVertices}, m={len(edges)}; manifest says n={instance.numVertices}, m={instance.numEdges}"
        )
    return numVertices, edges