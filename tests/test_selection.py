import json
from pathlib import Path

from tools.selectTests import REPOSITORY_ROOT, CONFIG_PATH, selectTests

CONFIG: dict = json.loads((REPOSITORY_ROOT / CONFIG_PATH).read_text(encoding="utf-8"))
FULL_SUITE: list[str] = CONFIG["full_suite"]


def test_selection_follows_the_committed_mapping() -> None:
    assert selectTests(["scripts/ilp/ilpModel.py"], CONFIG)[0] == ["tests/test_ilp_workflow.py", "tests/test_experiment_runner.py"]
    assert selectTests(["tests/test_shared.py"], CONFIG)[0] == ["tests/test_shared.py"]
    assert selectTests(["Task.md", "docs/Problem.md", "report/sections/ilpFormulation.tex"], CONFIG)[0] == []
    assert selectTests(["scripts/shared/labeling.py"], CONFIG)[0] == FULL_SUITE
    assert selectTests(["tools/testSelection.json"], CONFIG)[0] == FULL_SUITE
    # A path that no rule names must widen the run, never skip it.
    assert selectTests(["Task.md", "tools/newTool.py"], CONFIG)[0] == FULL_SUITE


def test_every_mapped_test_file_exists() -> None:
    for check in CONFIG["checks"]:
        for test in check["tests"]:
            assert (REPOSITORY_ROOT / test).is_file(), f"{check['id']} names a missing test file {test}"
    for target in FULL_SUITE:
        assert Path(REPOSITORY_ROOT / target).exists()