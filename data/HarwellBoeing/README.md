# Harwell–Boeing Dataset

Summary: Source, attribution, selection limits, and reproduction entry point for the team's initial BMP dataset.

## Source and Rationale

[Documented] The **Harwell–Boeing Sparse Matrix Collection** was developed by Iain Duff, Roger Grimes, and John Lewis. The data is distributed through [NIST Matrix Market](https://math.nist.gov/MatrixMarket/data/Harwell-Boeing/); see [NIST's collection description](https://math.nist.gov/MatrixMarket/collections/hb.html).

[Documented] The supplied reference paper, J. Torres-Jimenez et al., *A dual representation simulated annealing algorithm for the bandwidth minimization problem on graphs*, Information Sciences 303 (2015), 33–49, uses 113 Harwell–Boeing instances in Section 5 and cites NIST Matrix Market in reference [22]. DOI: [10.1016/j.ins.2014.12.041](https://doi.org/10.1016/j.ins.2014.12.041). The team selected this collection to connect the assignment's experiments to its supplied BMP reference.

## Committed Selection

This repository includes an initial subset of 12 instances spanning 32–1,000 vertices. The selected names occur in the paper's result tables. This is not a random sample or the complete 113-instance benchmark, and it does not by itself establish performance across the full collection.

[Manifest.json](Manifest.json) is the canonical inventory. It records source pages, exact download URLs, original retrieval timestamps, original and derived SHA-256 checksums, graph dimensions, and connected-component counts. `raw/` preserves the downloaded `.mtx.gz` matrices; `graphs/` contains derived `.col` graphs. The repository import preserves the original retrieval metadata rather than pretending that the matrices were downloaded again.

These are input instances, not reference solutions or certified optimal bandwidths. Preserve the original source attribution; inclusion here does not relicense third-party data or the reference paper.

## Conversion and Input

For the undirected BMP graph, off-diagonal nonzero matrix entries become unweighted edges. Either matrix direction creates the same edge; numerical weights, diagonal entries, and repeated undirected edges do not contribute additional graph edges. Every matrix row remains a vertex. Preserving the entire graph follows the paper's Section 5, including disconnected components and isolated vertices.

The common solver input and validation rules are owned by [ExperimentContract.md](../../docs/ExperimentContract.md#graph-input). Matrix Market syntax is described by [NIST](https://math.nist.gov/MatrixMarket/formats.html). The executable conversion is in [prepare_dataset.py](../../tools/prepare_dataset.py).

## Reproduce

From the repository root:

```bash
python tools/prepare_dataset.py
```

The command requires network access, downloads the selected matrices again, regenerates graph files, and updates manifest retrieval timestamps and checksums. Retain the frozen manifest and input checksums with every experiment campaign. Expanding the subset is a deliberate dataset change, not a silent alteration of a running comparison.
