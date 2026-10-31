import json
import shutil
from pathlib import Path
import pytest

from w8bench.verifier.dataset_sync import build_trajectory_index, fetch_trajectories, upload_trajectories


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
    assert api.kwargs["allow_patterns"] == ["data-ss/**", "data-dom/**", "pairs.jsonl"]
    assert (local / "pairs.jsonl").is_file()


def test_pair_index_retains_source_payloads_and_order_without_modifying_them(tmp_path):
    source = tmp_path / "inputs"
    _write_pair(source, "task_01")
    originals = {p: p.read_bytes() for p in source.rglob("*") if p.is_file()}
    receipt = build_trajectory_index(source)
    record, = [json.loads(line) for line in (source / "pairs.jsonl").read_text().splitlines()]
    assert receipt["task_count"] == 1
    assert record["task_alias"] == "task_01"
    assert record["states"][0]["index"] == 0
    assert record["states"][0]["screenshot_path"] == "trajectories/data-ss/task_01/screenshot0.png"
    assert record["states"][0]["dom_model_text"] == (source / "data-dom/task_01/dom_model0.txt").read_text()
    assert record["screenshot_final_answer_json"] == (source / "data-ss/task_01/final_answer.json").read_text()
    assert all(p.read_bytes() == content for p, content in originals.items())
    first = (source / "pairs.jsonl").read_bytes()
    build_trajectory_index(source)
    assert (source / "pairs.jsonl").read_bytes() == first


def test_pair_index_refuses_mismatched_logs_and_preserves_an_existing_index(tmp_path):
    source = tmp_path / "inputs"
    _write_pair(source, "task_01")
    build_trajectory_index(source)
    first = (source / "pairs.jsonl").read_bytes()
    (source / "data-dom/task_01/web_surfer.log").write_text('{"action":"click"}\n')
    with pytest.raises(ValueError, match="action logs differ"):
        build_trajectory_index(source)
    assert (source / "pairs.jsonl").read_bytes() == first


def test_pair_index_refuses_mismatched_state_counts(tmp_path):
    source = tmp_path / "inputs"
    _write_pair(source, "task_01")
    (source / "data-ss/task_01/screenshot1.png").write_bytes(b"image")
    with pytest.raises(ValueError, match="state counts differ"):
        build_trajectory_index(source)
    assert not (source / "pairs.jsonl").exists()


@pytest.mark.parametrize("filename,payload,message", [
    ("task_data.json", {"task_id":"other", "confirmed_task":"Test", "website":"https://example.test"}, "task identities differ"),
    ("final_answer.json", {"final_answer":"Different"}, "final answers differ"),
])
def test_pair_index_rejects_cross_task_metadata(tmp_path, filename, payload, message):
    source = tmp_path / "inputs"
    _write_pair(source, "task_01")
    (source / "data-dom/task_01" / filename).write_text(json.dumps(payload))
    with pytest.raises(ValueError, match=message):
        build_trajectory_index(source)
    assert not (source / "pairs.jsonl").exists()


def test_pair_index_preserves_unicode_and_line_endings(tmp_path):
    source = tmp_path / "inputs"
    _write_pair(source, "task_01")
    content = "URL: https://example.test\r\nValue: α ≥ 3 😀\r\n".encode("utf-8")
    (source / "data-dom/task_01/dom_model0.txt").write_bytes(content)
    build_trajectory_index(source)
    record = json.loads((source / "pairs.jsonl").read_text())
    assert record["states"][0]["dom_model_text"].encode("utf-8") == content


def test_pair_index_does_not_silently_drop_one_sided_task_folders(tmp_path):
    source = tmp_path / "inputs"
    _write_pair(source, "task_01")
    (source / "data-ss/task_02").mkdir()
    with pytest.raises(ValueError, match="task folders differ"):
        build_trajectory_index(source)
    assert not (source / "pairs.jsonl").exists()


def test_fetch_rejects_stale_but_structurally_valid_cache(tmp_path):
    local = tmp_path / "data"
    _write_pair(local, "task_01")
    original = local / "data-dom/task_01/dom_model0.txt"
    before = original.read_bytes()
    def download(**kwargs):
        destination = Path(kwargs["local_dir"])
        root = destination / "trajectories"
        _write_pair(root, "task_01")
        (root / "data-dom/task_01/dom_model0.txt").write_text("URL: https://different.test/\n")
        return str(destination)
    with pytest.raises(ValueError, match="Cached trajectory differs"):
        fetch_trajectories(data_root=local, task="task_01", snapshot_download_fn=download)
    assert original.read_bytes() == before
