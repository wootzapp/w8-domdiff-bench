from pathlib import Path

import pytest

from w8bench.run_paths import resolve_run_name, run_directory
from w8bench.verifier import dataset_sync
from .test_dataset_sync import _write_pair


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


def test_fetch_uses_only_the_selected_run(tmp_path):
    def download(**kwargs):
        assert kwargs["allow_patterns"] == [
            "trajectories/run_3/data-ss/task_01/**",
            "trajectories/run_3/data-dom/task_01/**"]
        destination = Path(kwargs["local_dir"])
        _write_pair(destination / "trajectories/run_3", "task_01")
        return str(destination)
    dataset_sync.fetch_trajectories(data_root=tmp_path / "local/run_3", task="task_01",
                                   run_name="run_3", snapshot_download_fn=download)
    assert (tmp_path / "local/run_3/data-dom/task_01/dom_model0.txt").is_file()
