import json
import shutil
from pathlib import Path

from scripts.dataset_sync import fetch_trajectories, upload_trajectories


def _write_pair(root: Path, task: str) -> None:
    for modality in ("data-ss", "data-dom"):
        task_root = root / modality / task
        task_root.mkdir(parents=True)
        (task_root / "task_data.json").write_text(
            json.dumps({"task_id": task, "confirmed_task": "Test", "website": "https://example.test"}),
            encoding="utf-8",
        )
        (task_root / "web_surfer.log").write_text("", encoding="utf-8")
        (task_root / "final_answer.json").write_text(
            json.dumps({"final_answer": "Done"}), encoding="utf-8"
        )
    (root / "data-ss" / task / "screenshot0.png").write_bytes(b"image")
    (root / "data-dom" / task / "dom_model0.txt").write_text(
        "URL: https://example.test\n", encoding="utf-8"
    )


def test_fetch_one_task_maps_remote_trajectory_prefix_to_local_data(tmp_path):
    remote = tmp_path / "remote" / "trajectories"
    _write_pair(remote, "task_01")
    _write_pair(remote, "task_02")
    calls = []

    def fake_snapshot_download(**kwargs):
        calls.append(kwargs)
        destination = Path(kwargs["local_dir"])
        for pattern in kwargs["allow_patterns"]:
            task = pattern.split("/")[2]
            for modality in ("data-ss", "data-dom"):
                source = remote / modality / task
                target = destination / "trajectories" / modality / task
                if not target.exists():
                    shutil.copytree(source, target)
        return str(destination)

    local = tmp_path / "local-data"
    receipt = fetch_trajectories(
        data_root=local,
        task="task_01",
        snapshot_download_fn=fake_snapshot_download,
    )

    assert receipt["status"] == "resolved_from_huggingface"
    assert [row["task"] for row in receipt["tasks"]] == ["task_01"]
    assert (local / "data-ss" / "task_01" / "screenshot0.png").is_file()
    assert (local / "data-dom" / "task_01" / "dom_model0.txt").is_file()
    assert not (local / "data-ss" / "task_02").exists()
    assert calls[0]["repo_type"] == "dataset"
    assert calls[0]["allow_patterns"] == [
        "trajectories/data-ss/task_01/**",
        "trajectories/data-dom/task_01/**",
    ]


def test_fetch_revalidates_valid_cache_against_huggingface(tmp_path):
    local = tmp_path / "data"
    _write_pair(local, "task_01")
    calls = []

    def fake_snapshot_download(**kwargs):
        calls.append(kwargs)
        destination = Path(kwargs["local_dir"])
        _write_pair(destination / "trajectories", "task_01")
        return str(destination)

    receipt = fetch_trajectories(
        data_root=local,
        task="task_01",
        snapshot_download_fn=fake_snapshot_download,
    )
    assert receipt["status"] == "resolved_from_huggingface"
    assert len(calls) == 1


def test_upload_publishes_only_paired_trajectory_trees(tmp_path):
    local = tmp_path / "data"
    _write_pair(local, "task_01")

    class FakeApi:
        def __init__(self):
            self.kwargs = None

        def upload_folder(self, **kwargs):
            self.kwargs = kwargs
            return "commit-url"

    api = FakeApi()
    receipt = upload_trajectories(data_root=local, api=api)
    assert receipt["task_count"] == 1
    assert api.kwargs["path_in_repo"] == "trajectories"
    assert api.kwargs["allow_patterns"] == ["data-ss/**", "data-dom/**"]
