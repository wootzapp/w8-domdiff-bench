from pathlib import Path

import pytest

from w8bench.run_paths import resolve_run_name, run_directory


def test_run_selection_and_no_double_nesting(monkeypatch):
    monkeypatch.delenv("W8_RUN_NAME", raising=False)
    assert resolve_run_name() == "run_1"
    monkeypatch.setenv("W8_RUN_NAME", "run_2")
    assert run_directory("recordings") == Path("recordings/run_2")
    assert run_directory("recordings/run_3", "run_3") == Path("recordings/run_3")
    assert resolve_run_name("run_3") == "run_3"
    for value in ("", "..", "/tmp/other", "run/2", "a\\b"):
        with pytest.raises(ValueError):
            resolve_run_name(value)
