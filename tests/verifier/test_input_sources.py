import json
import hashlib
import shutil
from pathlib import Path

import pytest

from w8bench.verifier import run_full_comparison as workflow


@pytest.fixture
def inputs(pair_factory):
    return pair_factory(sidecars=False, metrics=False)


def forbid_fetch(**kwargs):
    raise AssertionError("Local mode must not download published trajectories")


def test_local_single_input_has_no_fetch_or_paid_calls(inputs, monkeypatch, capsys):
    monkeypatch.setattr(workflow, "fetch_trajectories", forbid_fetch)
    monkeypatch.setattr(workflow, "generate_rubric", lambda *a: pytest.fail("Paid path entered"))
    before = sorted(inputs["staged"].rglob("*"))
    assert workflow.main(["--task", "task1", "--data-source", "local",
                          "--data-root", str(inputs["staged"])]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["input_source"]["data_source"] == "local"
    assert not Path(receipt["screenshot_task"]).is_absolute()
    assert (workflow.REPOSITORY_ROOT / receipt["screenshot_task"]).resolve() == inputs["screenshot"]
    assert receipt["validation"]["actions"] == 1
    assert receipt["paid_calls_authorized"] is False
    assert sorted(inputs["staged"].rglob("*")) == before


def test_local_batch_validates_all_pairs_without_download(inputs, monkeypatch, capsys):
    monkeypatch.setattr(workflow, "fetch_trajectories", forbid_fetch)
    assert workflow.main(["--all", "--data-source", "local", "--data-root", str(inputs["staged"])]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["selected_tasks"] == 1 and receipt["tasks"] == ["task1"]


def test_local_missing_input_does_not_fall_back(tmp_path, monkeypatch):
    monkeypatch.setattr(workflow, "fetch_trajectories", forbid_fetch)
    with pytest.raises(FileNotFoundError):
        workflow.main(["--task", "task1", "--data-source", "local", "--data-root", str(tmp_path / "missing")])


def test_invalid_local_pair_fails_before_clients(inputs, monkeypatch):
    monkeypatch.setattr(workflow, "fetch_trajectories", forbid_fetch)
    monkeypatch.setattr(workflow, "generate_rubric", lambda *a: pytest.fail("Paid path entered"))
    (inputs["dom"] / "dom_model1.txt").unlink()
    with pytest.raises(ValueError, match="N actions require"):
        workflow.main(["--all", "--data-source", "local", "--data-root", str(inputs["staged"]), "--execute"])


@pytest.mark.parametrize("explicit", [False, True])
def test_huggingface_source_fetches_to_download_folder(inputs, monkeypatch, capsys, explicit):
    calls = []
    monkeypatch.setattr(workflow, "DEFAULT_DATASET_ROOT", inputs["staged"])
    monkeypatch.setattr(workflow, "fetch_trajectories", lambda **kw: calls.append(kw) or {"status": "fetched"})
    args = ["--task", "task1", "--hf-revision", "pinned-revision"]
    if explicit:
        args += ["--data-source", "huggingface"]
    assert workflow.main(args) == 0
    assert len(calls) == 1 and calls[0]["revision"] == "pinned-revision"
    assert calls[0]["data_root"] == inputs["staged"]
    assert '"data_source": "huggingface"' in capsys.readouterr().out


def test_local_default_uses_trajectories_not_download_folder(inputs, tmp_path, monkeypatch):
    monkeypatch.setattr(workflow, "REPOSITORY_ROOT", tmp_path)
    shutil.copytree(inputs["staged"], tmp_path / "trajectories")
    monkeypatch.setattr(workflow, "fetch_trajectories", forbid_fetch)
    assert workflow.main(["--all", "--data-source", "local"]) == 0


def test_download_mode_refuses_locally_prepared_root(inputs, monkeypatch):
    monkeypatch.setattr(workflow, "DEFAULT_DATASET_ROOT", inputs["staged"])
    (inputs["staged"] / "preparation_report.json").write_text("{}")
    monkeypatch.setattr(workflow, "fetch_trajectories", forbid_fetch)
    with pytest.raises(ValueError, match="locally prepared"):
        workflow.main(["--task", "task1", "--data-source", "huggingface"])


@pytest.mark.parametrize("argv", [
    ["--all", "--data-root", "/tmp/local"],
    ["--task", "../task1", "--data-source", "local"],
    ["--task", "..", "--data-source", "local"],
])
def test_source_and_path_conflicts_are_rejected(argv):
    with pytest.raises(SystemExit):
        workflow.parse_args(argv)


def test_execute_passes_only_selected_local_inputs(inputs, tmp_path, monkeypatch):
    monkeypatch.setattr(workflow, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(workflow, "fetch_trajectories", forbid_fetch)
    env = tmp_path / ".env"; env.write_text("")
    seen = []
    def generate(argv):
        screenshot = Path(argv[argv.index("--screenshot-task") + 1])
        assert (screenshot / "final_answer.json").read_bytes() == (inputs["screenshot"] / "final_answer.json").read_bytes()
        seen.append("generate")
        return 0
    def score(argv):
        seen.append("score")
        root = tmp_path / "evaluation/task1/check"
        root.mkdir(parents=True)
        return 0
    monkeypatch.setattr(workflow, "generate_rubric", generate)
    monkeypatch.setattr(workflow, "run_comparison", score)
    assert workflow.main(["--task", "task1", "--data-source", "local", "--data-root", str(inputs["staged"]),
                          "--env-file", str(env), "--eval-config", str(inputs["config"]),
                          "--run-id", "check", "--execute"]) == 0
    assert seen == ["generate", "score"]
    receipt = json.loads((tmp_path / "evaluation/task1/check/input_source.json").read_text())
    assert receipt["data_source"] == "local"
    assert not Path(receipt["data_root"]).is_absolute()
    assert (tmp_path / receipt["data_root"]).resolve() == inputs["staged"]


def test_preparation_hashes_block_edited_inputs_before_paid_calls(inputs, monkeypatch):
    root = inputs["staged"]
    hashes = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for side in ("data-ss", "data-dom") for p in (root / side / "task1").iterdir() if p.is_file()}
    report = {"schema_version": "1.0", "selected_recordings": 1, "prepared_count": 1,
              "excluded_count": 0, "excluded": [],
              "prepared": [{"task": "task1", "output_sha256": hashes}]}
    (root / "preparation_report.json").write_text(json.dumps(report))
    monkeypatch.setattr(workflow, "fetch_trajectories", forbid_fetch)
    assert workflow.main(["--all", "--data-source", "local", "--data-root", str(root)]) == 0
    with (inputs["dom"] / "dom_model0.txt").open("a") as stream:
        stream.write("An unrecorded fact.\n")
    monkeypatch.setattr(workflow, "generate_rubric", lambda *a: pytest.fail("Paid path entered"))
    with pytest.raises(ValueError, match="differ from the preparation receipt"):
        workflow.main(["--all", "--data-source", "local", "--data-root", str(root), "--execute"])


def test_huggingface_batch_downloads_once_and_keeps_source_in_children(inputs, monkeypatch):
    root = inputs["staged"]
    calls, children = [], []
    monkeypatch.setattr(workflow, "DEFAULT_DATASET_ROOT", root)
    monkeypatch.setattr(workflow, "fetch_trajectories", lambda **kw: calls.append(kw) or {})
    monkeypatch.setattr(workflow, "_run_task", lambda args, selected: children.append((args.data_source, selected)) or 1)
    with pytest.raises(RuntimeError, match="All selected task comparisons failed"):
        workflow.main(["--all", "--data-source", "huggingface", "--execute"])
    assert len(calls) == 1 and calls[0]["task"] is None
    assert children == [("huggingface", root)]


def test_malformed_local_preparation_report_is_rejected(inputs, monkeypatch):
    root = inputs["staged"]
    (root / "preparation_report.json").write_text("[]")
    monkeypatch.setattr(workflow, "fetch_trajectories", forbid_fetch)
    with pytest.raises(ValueError, match="report schema"):
        workflow.main(["--all", "--data-source", "local", "--data-root", str(root)])
