"""Select the workflow tests that the committed changes can affect, and run them on the committed files.

The mapping from changed paths to tests is owned by tools/testSelection.json. A change that no rule maps selects the full suite, so a missing rule costs time, never coverage.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

REPOSITORY_ROOT: Path = Path(__file__).resolve().parents[1]
CONFIG_PATH: str = "tools/testSelection.json"


def _globPattern(glob: str) -> re.Pattern[str]:
    """Translate a repository glob: `**` spans folders, `*` stays inside one path segment."""
    parts: list[str] = []
    index: int = 0
    while index < len(glob):
        if glob.startswith("**/", index):
            parts.append("(?:.*/)?")
            index += 3
        elif glob.startswith("**", index):
            parts.append(".*")
            index += 2
        elif glob[index] == "*":
            parts.append("[^/]*")
            index += 1
        else:
            parts.append(re.escape(glob[index]))
            index += 1
    return re.compile("".join(parts) + r"\Z")


def _matches(path: str, globs: list[str]) -> bool:
    return any(_globPattern(glob).match(path) for glob in globs)


def _git(*arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=REPOSITORY_ROOT, check=True, capture_output=True, text=True).stdout


def selectTests(changedPaths: list[str], config: dict) -> tuple[list[str], list[str]]:
    """Return the pytest targets to run and one reason line per selection decision."""
    targets: list[str] = []
    reasons: list[str] = []

    def add(target: str, reason: str) -> None:
        if target not in targets:
            targets.append(target)
        reasons.append(f"{target}: {reason}")

    for path in changedPaths:
        if _matches(path, config["full_suite_paths"]):
            return list(config["full_suite"]), [f"full suite: {path} is shared by every check"]
        if _matches(path, config["no_check"]):
            reasons.append(f"no check: {path} is not executable")
            continue
        mapped: bool = False
        for check in config["checks"]:
            if path in check["tests"] or _matches(path, check["paths"]):
                mapped = True
                for test in check["tests"]:
                    add(test, f"check {check['id']} covers {path}")
        if not mapped:
            return list(config["full_suite"]), [f"full suite: no rule in {CONFIG_PATH} maps {path}"]
    return targets, reasons


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="HEAD~1", help="Revision before the changes to check; pass the commit before a request's first commit when it made several. Default: HEAD~1.")
    arguments = parser.parse_args()

    head: str = _git("rev-parse", "HEAD").strip()
    changedPaths: list[str] = [line for line in _git("diff", "--name-only", arguments.base, head).splitlines() if line]
    # The selection and the run both read the committed config, so an uncommitted edit to it cannot change what is checked.
    config: dict = json.loads(_git("show", f"{head}:{CONFIG_PATH}"))
    targets, reasons = selectTests(changedPaths, config)
    print(f"Changed files {arguments.base}..{head[:7]}: {len(changedPaths)}")
    for reason in reasons:
        print(f"  {reason}")
    if not targets:
        print("No test selected.")
        return 0

    with tempfile.TemporaryDirectory(prefix="bmp-select-") as folder:
        checkout: Path = Path(folder) / "checkout"
        # A detached worktree of HEAD tests the committed files only, while keeping the git metadata that the runner records.
        _git("worktree", "add", "--detach", "--quiet", str(checkout), head)
        try:
            command: list[str] = [sys.executable, "-m", "pytest", "-q", *targets]
            print(f"Running in a checkout of {head[:7]}: {' '.join(command[1:])}", flush=True)
            exitCode: int = subprocess.run(command, cwd=checkout, env=os.environ.copy()).returncode
        finally:
            _git("worktree", "remove", "--force", str(checkout))
    if exitCode != 0:
        print(f"Selected tests failed: pytest exited {exitCode} (5 means no test was collected).")
    return exitCode


if __name__ == "__main__":
    sys.exit(main())