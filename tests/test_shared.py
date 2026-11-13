"""Workflow tests of the shared loader, the manifest checks and the independent labeling checker."""

import json
import shutil
from pathlib import Path

import pytest

from scripts.shared.graphInput import (
    DatasetIntegrityError,
    GraphFormatError,
    loadColFile,
    loadManifestInstance,
    parseColText,
    readManifest,
)
from scripts.shared.labeling import LabelingError, checkLabeling, commonLowerBound, identityLabeling
from tests.oracle import CORRECTNESS_CASES, bruteForceBandwidth, colText

REPOSITORY_ROOT: Path = Path(__file__).resolve().parents[1]
COMMITTED_MANIFEST: Path = REPOSITORY_ROOT / "data" / "HarwellBoeing" / "Manifest.json"


def test_loader_keeps_isolated_vertices_and_sorts_edges(tmp_path: Path) -> None:
    graphFile: Path = tmp_path / "graph.col"
    graphFile.write_text("c a comment\n\np edge 6 3\ne 3 5\ne 1 2\nc another comment\ne 1 5\n", encoding="utf-8")
    assert loadColFile(graphFile) == (6, [(1, 2), (1, 5), (3, 5)])


@pytest.mark.parametrize(
    "text",
    [
        "e 1 2\np edge 2 1\n",  # edge before the problem line
        "p edge 3 1\np edge 3 1\ne 1 2\n",  # two problem lines
        "p col 3 1\ne 1 2\n",  # wrong problem type
        "p edge 0 0\n",  # no vertex
        "p edge 3 2\ne 1 2\n",  # fewer edges than declared
        "p edge 3 1\ne 1 2\ne 2 3\n",  # more edges than declared
        "p edge 3 1\ne 2 2\n",  # self-loop
        "p edge 3 1\ne 2 1\n",  # u > v
        "p edge 3 1\ne 1 4\n",  # vertex above n
        "p edge 3 2\ne 1 2\ne 1 2\n",  # duplicate edge
        "p edge 3 1\ne 1 2 7\n",  # extra field
        "p edge 3 1\ne +1 2\n",  # signed integer
        "p edge 3 1\nx 1 2\n",  # unknown record type
        "",  # no problem line
    ],
)
def test_loader_rejects_malformed_input(text: str) -> None:
    with pytest.raises(GraphFormatError):
        parseColText(text, "case")


def test_committed_manifest_instances_load_in_manifest_order() -> None:
    instances = readManifest(COMMITTED_MANIFEST)
    assert len(instances) == 12
    for instance in instances:
        numVertices, edges = loadManifestInstance(instance)
        assert (numVertices, len(edges)) == (instance.numVertices, instance.numEdges)
        assert edges == sorted(edges)


def _copyManifestWith(tmp_path: Path, editGraph) -> Path:
    """Copy ibm32 into a one-instance manifest under tmp_path, after editGraph(graphFile) changes the copy."""
    source = readManifest(COMMITTED_MANIFEST)[0]
    (tmp_path / "graphs").mkdir()
    graphFile: Path = tmp_path / "graphs" / "ibm32.col"
    shutil.copyfile(source.graphPath, graphFile)
    editGraph(graphFile)
    manifest: dict = {
        "instances": [
            {"name": "ibm32", "graph_file": "graphs/ibm32.col", "graph_sha256": source.graphSha256, "vertices": 32, "edges": 90}
        ]
    }
    manifestFile: Path = tmp_path / "Manifest.json"
    manifestFile.write_text(json.dumps(manifest), encoding="utf-8")
    return manifestFile


def test_checksum_mismatch_stops_loading(tmp_path: Path) -> None:
    manifestFile = _copyManifestWith(tmp_path, lambda graphFile: graphFile.write_text(graphFile.read_text() + "c changed\n"))
    with pytest.raises(DatasetIntegrityError, match="SHA-256"):
        loadManifestInstance(readManifest(manifestFile)[0])


def test_missing_graph_stops_loading(tmp_path: Path) -> None:
    manifestFile = _copyManifestWith(tmp_path, lambda graphFile: graphFile.unlink())
    with pytest.raises(DatasetIntegrityError, match="missing"):
        loadManifestInstance(readManifest(manifestFile)[0])


@pytest.mark.parametrize("name,numVertices,edges", CORRECTNESS_CASES, ids=[case[0] for case in CORRECTNESS_CASES])
def test_checker_and_common_bounds_agree_with_the_oracle(name: str, numVertices: int, edges: list[tuple[int, int]], tmp_path: Path) -> None:
    graphFile: Path = tmp_path / f"{name}.col"
    graphFile.write_text(colText(numVertices, edges), encoding="utf-8")
    loadedVertices, loadedEdges = loadColFile(graphFile)
    identityBandwidth: int = checkLabeling(loadedVertices, loadedEdges, identityLabeling(loadedVertices))
    assert identityBandwidth == max((v - u for u, v in edges), default=0)
    assert commonLowerBound(loadedEdges) <= bruteForceBandwidth(numVertices, edges) <= identityBandwidth


@pytest.mark.parametrize(
    "labeling",
    [
        [1, 2, 3],  # too short
        [1, 2, 3, 4, 5],  # too long
        [1, 2, 2, 4],  # repeated position
        [0, 1, 2, 3],  # position 0
        [1, 2, 3, 5],  # position above n
        [1, 2, 3, 4.0],  # float
        [True, 2, 3, 4],  # bool
    ],
)
def test_checker_rejects_invalid_labelings(labeling: list) -> None:
    with pytest.raises(LabelingError):
        checkLabeling(4, [(1, 4), (2, 3), (3, 4)], labeling)