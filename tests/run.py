#!/usr/bin/env python3
"""Run the test suite.

Prefers pytest. If pytest is not installed, falls back to a minimal runner so the suite
still works on a bare Python — these tests need no fixtures and no plugins, which is the
whole point of keeping them free of the Home Assistant test rig.

    python3 tests/run.py
    pytest tests            # identical results
"""

from __future__ import annotations

import importlib
import pathlib
import re
import sys
import traceback

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _install_pytest_stub() -> None:
    """Just enough of pytest for these tests: `raises`."""
    import contextlib
    import types

    stub = types.ModuleType("pytest")

    @contextlib.contextmanager
    def raises(expected, match=None):
        try:
            yield
        except expected as err:
            if match and not re.search(match, str(err)):
                raise AssertionError(
                    f"{expected.__name__} raised but {match!r} not in {str(err)!r}"
                ) from None
        else:
            raise AssertionError(f"{expected.__name__} was not raised")

    stub.raises = raises
    sys.modules["pytest"] = stub


def main() -> int:
    try:
        import pytest  # noqa: F401
    except ModuleNotFoundError:
        print("pytest not installed — using the built-in fallback runner\n")
        _install_pytest_stub()
    else:
        return pytest.main([str(HERE), "-q"])

    passed, failed = 0, []
    for path in sorted(HERE.glob("test_*.py")):
        module = importlib.import_module(path.stem)
        print(path.name)
        for name in sorted(vars(module)):
            if not name.startswith("test_"):
                continue
            try:
                getattr(module, name)()
            except Exception:  # noqa: BLE001 — a runner reports everything
                failed.append((path.name, name, traceback.format_exc()))
                print(f"  FAIL  {name}")
            else:
                passed += 1
                print(f"  ok    {name}")
        print()

    if failed:
        for filename, name, tb in failed:
            print(f"===== {filename}::{name}\n{tb}")
        print(f"{passed} passed, {len(failed)} failed")
        return 1
    print(f"{passed} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
