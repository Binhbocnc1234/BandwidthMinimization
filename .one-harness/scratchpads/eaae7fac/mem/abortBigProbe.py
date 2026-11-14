"""Does a child that aborts before the deadline get reported as an error? Usage: abortProbe.py"""
import os
import sys
import time

sys.path.insert(0, "script/sat")
import deadlineRunner


def abortingSearch(initUB: int, lb: int, reporter: deadlineRunner.SearchReporter) -> None:
    reporter.boundStarted(initUB - 1)
    ballast = b"\x01" * (3 * 1024**3)
    time.sleep(1.0)
    print(f"child aborts at {time.monotonic():.3f}", flush=True)
    os.abort()


if __name__ == "__main__":
    print(f"parent starts at {time.monotonic():.3f}", flush=True)
    try:
        result = deadlineRunner.runSearchWithDeadline(abortingSearch, 4, 3, 3, 5.0, True)
        print(f"RESULT {result['terminationReason']} at {time.monotonic():.3f}: {result['trace']}", flush=True)
    except RuntimeError as error:
        print(f"ERROR at {time.monotonic():.3f}: {error}", flush=True)