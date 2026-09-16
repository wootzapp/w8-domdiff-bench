from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import runner  # noqa: E402
import task_cli  # noqa: E402


class TaskCliTests(unittest.TestCase):
    def test_selector_and_unique_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            first = task_cli.unique_run_id(
                "task1",
                "ranking lookup",
                output,
                timestamp="20260810T120000Z",
            )
            (output / first).mkdir()
            second = task_cli.unique_run_id(
                "task1",
                "ranking lookup",
                output,
                timestamp="20260810T120000Z",
            )
        self.assertEqual(first, "task1-ranking-lookup-20260810T120000Z")
        self.assertEqual(second, first + "-2")

    def test_post_action_language_redirect_is_disabled_by_default(self) -> None:
        runner_args = runner.parse_args([])
        cli_args = task_cli.parse_args(
            ["task1", "--output-dir", "/tmp/browser-runs"]
        )

        self.assertFalse(runner_args.post_action_language_redirect)
        self.assertFalse(cli_args.post_action_language_redirect)

    def test_arbitrary_task_definition_is_validated(self) -> None:
        definition = task_cli.validate_task_definition(
            "Inspect the visible page.",
            "https://example.test/path",
            model="gpt-5.1",
        )
        self.assertEqual(definition["instruction"], "Inspect the visible page.")
        self.assertEqual(definition["start_url"], "https://example.test/path")
        self.assertEqual(definition["model"], "gpt-5.1")
        with self.assertRaises(runner.RunnerError):
            task_cli.validate_task_definition("", "https://example.test/")
        with self.assertRaises(runner.RunnerError):
            task_cli.validate_task_definition("Inspect it", "example.test")

    def test_runner_command_uses_new_run_and_enables_human_pause(self) -> None:
        command = task_cli.build_runner_command(
            {
                "instruction": "Inspect the visible page.",
                "start_url": "https://example.test/",
                "model": "gpt-5.1",
            },
            task_id="task4",
            task_name="metadata lookup retry",
            run_id="task4-metadata-20260810T120000Z",
            output_dir=Path("/tmp/browser-runs"),
            env_file=Path("/tmp/example.env"),
            allow_human_intervention=True,
            novnc_url="http://[::1]:39084/vnc.html",
            max_steps=80,
        )
        self.assertIn("--allow-human-intervention", command)
        self.assertIn("--no-post-action-language-redirect", command)
        self.assertEqual(command[command.index("--source-task-id") + 1], "task4")
        self.assertEqual(
            command[command.index("--task-id") + 1],
            "task4-metadata-20260810T120000Z",
        )
        self.assertEqual(command[command.index("--max-steps") + 1], "80")

    def test_explicit_output_dry_run_accepts_any_manual_task(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            env_file = Path(temporary) / "empty.env"
            output_dir = Path(temporary) / "chosen-output"
            result = task_cli.main(
                [
                    "custom-research",
                    "custom task",
                    "--task",
                    "Open the page and report its heading.",
                    "--start-url",
                    "https://example.test/",
                    "--env-file",
                    str(env_file),
                    "--output-dir",
                    str(output_dir),
                    "--dry-run",
                ]
            )
        self.assertEqual(result, 0)

    def test_catalog_task_selection_accepts_exact_and_numeric_aliases(self) -> None:
        payload = "\n".join(
            [
                json.dumps(
                    {
                        "task_id": "browser_task_001",
                        "category": "ranking",
                        "instruction": "Inspect the ranking.",
                        "start_url": "https://example.test/one",
                        "stopping_condition": "Stop after recording the first row.",
                        "constraints": ["Do not sign in."],
                    }
                ),
                json.dumps(
                    {
                        "task_id": "browser_task_002",
                        "category": "metadata",
                        "instruction": "Inspect the metadata.",
                        "start_url": "https://example.test/two",
                        "stopping_condition": "Stop after recording it.",
                        "constraints": [],
                    }
                ),
            ]
        )
        rows = task_cli.parse_task_catalog(payload, source="fixture")
        self.assertEqual(task_cli.select_catalog_task(rows, "browser_task_001")["category"], "ranking")
        self.assertEqual(task_cli.select_catalog_task(rows, "task2")["category"], "metadata")
        self.assertEqual(task_cli.select_catalog_task(rows, "1")["task_id"], "browser_task_001")

    def test_catalog_dry_run_uses_configured_definition_and_selected_output(self) -> None:
        definition = {
            "instruction": "Inspect the visible metadata.\n\nStopping condition: Stop after recording it.",
            "start_url": "https://example.test/",
            "model": "",
            "source_task_id": "browser_task_001",
            "task_name": "metadata lookup",
            "source_catalog": "https://catalog.example/tasks.jsonl",
        }
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "recordings"
            with patch.object(
                task_cli,
                "fetch_catalog_task",
                return_value=definition,
            ) as fetch:
                result = task_cli.main(
                    [
                        "task1",
                        "--output-dir",
                        str(output_dir),
                        "--env-file",
                        str(Path(temporary) / "empty.env"),
                        "--dry-run",
                    ]
                )
        self.assertEqual(result, 0)
        fetch.assert_called_once()

    def test_browser_service_start_preserves_existing_container(self) -> None:
        completed = SimpleNamespace(returncode=0, stdout="", stderr="")
        with patch.object(task_cli.subprocess, "run", return_value=completed) as run:
            task_cli.ensure_browser_service(Path("/tmp/recorder.env"))

        command = run.call_args.args[0]
        self.assertIn("--no-recreate", command)
        self.assertNotIn("--force-recreate", command)
        self.assertNotIn("down", command)
        self.assertEqual(command[-1], "w8-core")

    def test_task_boundary_restart_preserves_container_and_waits_for_health(self) -> None:
        completed = SimpleNamespace(returncode=0, stdout="", stderr="")
        with patch.object(
            task_cli.subprocess, "run", side_effect=[completed, completed, completed]
        ) as run:
            task_cli.restart_browser_service(Path("/tmp/recorder.env"))

        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0][-1], "w8-core")
        self.assertIn("--no-recreate", commands[0])
        self.assertEqual(commands[1][-2:], ["restart", "w8-core"])
        self.assertNotIn("down", commands[1])
        self.assertEqual(commands[2][-1], "w8-core")
        self.assertIn("--wait", commands[2])

    def test_stale_active_run_record_is_removed_without_signalling(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            active = Path(temporary) / "active-run.json"
            task_cli.write_active_run(
                {
                    "pid": 999999,
                    "pgid": 999999,
                    "process_start_ticks": 1,
                    "run_id": "old-run",
                },
                active,
            )
            with patch.object(task_cli.os, "killpg") as killpg:
                result = task_cli.stop_previous_run(active, timeout=0)

        self.assertEqual(result["status"], "stale_record_removed")
        killpg.assert_not_called()
        self.assertFalse(active.exists())

    def test_old_cli_cannot_clear_new_active_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            active = Path(temporary) / "active-run.json"
            task_cli.write_active_run({"pid": 202, "run_id": "new-run"}, active)
            task_cli.clear_active_run(101, active)
            record = task_cli.read_active_run(active)

        self.assertIsNotNone(record)
        self.assertEqual(record["run_id"], "new-run")

    def test_profile_counter_path_can_be_configured(self) -> None:
        custom_path = "/custom/profile/task-count"
        completed = [
            SimpleNamespace(
                returncode=0,
                stdout='[{"Id": "container-id", "Created": "created-at"}]',
                stderr="",
            ),
            SimpleNamespace(returncode=0, stdout="2", stderr=""),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
        ]

        with (
            patch.dict(
                task_cli.os.environ,
                {"BROWSER_PROFILE_TASK_COUNT_PATH": custom_path},
            ),
            patch.object(
                task_cli.subprocess,
                "run",
                side_effect=completed,
            ) as run,
        ):
            provenance = task_cli.claim_browser_profile_provenance("browser")

        self.assertEqual(provenance["tasks_previously_run_in_container"], 2)
        self.assertFalse(provenance["profile_fresh_at_run_start"])
        self.assertEqual(run.call_args_list[1].args[0][-1], custom_path)
        self.assertEqual(run.call_args_list[2].args[0][-2], custom_path)

    def test_human_request_requires_opt_in_and_reason(self) -> None:
        decision = {
            "action": "request_human",
            "final_answer": "Solve the visible CAPTCHA without signing in.",
        }
        self.assertIn(
            "not enabled",
            runner.action_rejection_reason(decision, frozenset(), []),
        )
        self.assertEqual(
            runner.action_rejection_reason(
                decision,
                frozenset(),
                [],
                allow_human_intervention=True,
            ),
            "",
        )
        self.assertIn(
            "requires",
            runner.action_rejection_reason(
                {"action": "request_human", "final_answer": ""},
                frozenset(),
                [],
                allow_human_intervention=True,
            ),
        )
        parsed = runner.parse_decision(
            json.dumps(
                {
                    "action": "request_human",
                    "final_answer": "Complete the visible human verification.",
                }
            )
        )
        self.assertEqual(parsed["action"], "request_human")

    def test_human_prompt_records_resume_and_abort(self) -> None:
        output = io.StringIO()
        resumed = runner.prompt_for_human_intervention(
            "Solve the visible CAPTCHA.",
            "http://[::1]:39084/vnc.html",
            input_fn=lambda _prompt: "",
            output=output,
            require_tty=False,
        )
        self.assertEqual(resumed["status"], "resumed")
        self.assertIn("HUMAN INTERVENTION REQUIRED", output.getvalue())
        self.assertIn("39084", output.getvalue())

        aborted = runner.prompt_for_human_intervention(
            "Solve the visible CAPTCHA.",
            "http://[::1]:39084/vnc.html",
            input_fn=lambda _prompt: "abort",
            output=io.StringIO(),
            require_tty=False,
        )
        self.assertEqual(aborted["status"], "aborted")


if __name__ == "__main__":
    unittest.main()
